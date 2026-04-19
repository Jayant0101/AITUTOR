import { createClient } from '@/lib/supabase/server';
import { logError, logInfo } from '@/lib/logger';
import { trackEvent } from '@/lib/analytics/tracker';
import { AIQuerySchema, sanitizeInput } from '@/lib/validation';

/**
 * AI Tutor Brain — Retention-Driven Mastery System.
 * Implements Active Recall, Spaced Repetition, and Forced Practice.
 */
export async function POST(req: Request) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 25000);

  try {
    const rawBody = await req.json();
    const validation = AIQuerySchema.safeParse(rawBody);
    if (!validation.success) {
      return Response.json({ error: "Invalid input", details: validation.error.format() }, { status: 400 });
    }

    const { prompt } = validation.data;
    const sanitizedPrompt = sanitizeInput(prompt);
    
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return Response.json({ error: "Unauthorized" }, { status: 401 });

    logInfo(`Mastery processing: ${sanitizedPrompt.substring(0, 50)}...`, "AI_TUTOR_MASTERY");

    // 1. Context Gathering (SRS + Profile + RAG + Knowledge Graph + System Analytics)
    const [profileRes, srsRes, documentsRes, pathRes, userSkillsRes, strategyRes] = await Promise.all([
      supabase.from('learning_profile').select('skill_level, mastery_score, weaknesses, retention_score, last_activity_at, streak_count, xp_points, knowledge_gaps').eq('user_id', user.id).single(),
      supabase.from('spaced_repetition')
        .select('topic')
        .eq('user_id', user.id)
        .lt('next_review', new Date().toISOString())
        .limit(5),
      fetchSimilarityDocs(sanitizedPrompt, user.id),
      supabase.from('learning_paths').select('ordered_skills, current_step_index').eq('user_id', user.id).single(),
      supabase.from('user_skills').select('skill_id, mastery_score, skills(name, id)').eq('user_id', user.id),
      supabase.from('teaching_effectiveness').select('skill_id, strategy, success_rate').order('success_rate', { ascending: false })
    ]);

    const profile = profileRes.data || { skill_level: 'beginner', mastery_score: 0, weaknesses: [] };
    const dueReviews = srsRes.data || [];
    const documents = documentsRes || [];
    const learningPath = pathRes.data;
    const userSkills = userSkillsRes.data || [];
    const globalStrategies = strategyRes.data || [];

    // 2. A/B Testing & Data-Driven Strategy Selection
    const testGroup = Math.random() > 0.5 ? 'A' : 'B';
    const currentSkillId = learningPath?.ordered_skills[learningPath.current_step_index];
    const bestStrategy = globalStrategies.find(s => s.skill_id === currentSkillId)?.strategy || 'socratic';
    
    // Experiment: 20% of the time, try a different strategy
    const activeStrategy = Math.random() > 0.2 ? bestStrategy : 'example-based';

    // 3. Predictive Failure Check
    const willLikelyFail = predictFailure(userSkills, learningPath);

    // 4. Build Mastery-Driven System Prompt (Enhanced for Self-Evolution)
    const systemPrompt = `
      You are an expert AI Mastery Tutor in a self-evolving learning network.
      
      CURRENT STRATEGY (A/B Test Group ${testGroup}): ${activeStrategy}
      
      KNOWLEDGE GRAPH STATE:
      - Current Skill Focus: ${currentSkillId || 'General'}
      - Skill Mastery: ${userSkills.map(s => `${(s.skills as any).name}: ${s.mastery_score * 100}%`).join(', ')}
      - Predictive Warning: ${willLikelyFail ? 'High risk of failure on next concept. Reinforce prerequisites.' : 'Normal progression.'}
      
      USER STATE:
      - Skill Level: ${profile.skill_level}
      - Mastery Score: ${profile.mastery_score}/100
      - Retention Score: ${profile.retention_score || 0}/100
      
      MODE INSTRUCTIONS:
      Apply the "${activeStrategy}" strategy. ${
        activeStrategy === 'socratic' ? 'Guide with questions.' : 
        activeStrategy === 'example-based' ? 'Use concrete real-world examples first.' : 
        'Break everything into atomic steps.'
      }
      
      EXPERIMENTAL FEEDBACK: Observe how the user reacts to this strategy. 
      The system will use your interaction to optimize global teaching effectiveness.
    `;

    // 5. Call AI Backend
    const response = await fetch(`${process.env.AI_BACKEND_URL || "http://localhost:8000"}/ai`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        prompt: sanitizedPrompt,
        system_prompt: systemPrompt,
        user_id: user.id,
        metadata: { 
          mode: activeStrategy, 
          test_group: testGroup,
          skill_id: currentSkillId 
        }
      }),
      signal: controller.signal
    });

    clearTimeout(timeoutId);
    if (!response.ok) throw new Error(`AI Backend responded with ${response.status}`);

    const data = await response.json();
    
    // 5. Update Learning Loop (Async)
    await updateLearningLoop(supabase, user.id, sanitizedPrompt, data.response, profile);

    return Response.json(data);

  } catch (error: any) {
    clearTimeout(timeoutId);
    logError(error, "AI_MASTERY_BRAIN");
    return Response.json({ error: "Mastery Engine failed" }, { status: 500 });
  }
}

function determineMode(profile: any, dueReviews: any[], prompt: string) {
  if (profile.weaknesses?.length > 0 && Math.random() > 0.7) return 'FORCED_PRACTICE';
  if (dueReviews.length > 0) return 'ACTIVE_RECALL';
  return 'SOCRATIC_MASTERY';
}

function predictFailure(userSkills: any[], learningPath: any) {
  if (!learningPath || userSkills.length === 0) return false;
  
  const currentSkillId = learningPath.ordered_skills[learningPath.current_step_index];
  const prerequisites = userSkills.filter(s => s.mastery_score < 0.6);
  
  // If many prerequisites have low mastery, predict high risk of failure
  return prerequisites.length >= 2;
}

async function updateLearningLoop(supabase: any, userId: string, prompt: string, response: string, profile: any) {
  try {
    // 1. Mastery Decay & XP Logic
    const lastActivity = new Date(profile.last_activity_at || 0).getTime();
    const now = Date.now();
    const daysSince = (now - lastActivity) / (1000 * 60 * 60 * 24);
    
    let masteryDecay = 0;
    if (daysSince > 2) masteryDecay = Math.floor(daysSince * 2);

    // 2. Update Profile with XP and Streak
    const isNewDay = daysSince >= 1;
    const newStreak = isNewDay ? (profile.streak_count || 0) + 1 : (profile.streak_count || 1);

    await supabase.from('learning_profile')
      .update({
        mastery_score: Math.max(0, (profile.mastery_score || 0) - masteryDecay + 5),
        xp_points: (profile.xp_points || 0) + 10,
        streak_count: newStreak,
        last_activity_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })
      .eq('user_id', userId);

    // 3. Schedule SRS for the topic
    const topic = prompt.substring(0, 30);
    await supabase.from('spaced_repetition').upsert({
      user_id: userId,
      topic: topic,
      next_review: new Date(now + 1000 * 60 * 60 * 24).toISOString(), // 1 day initially
      interval_days: 1,
      ease_factor: 2.5
    }, { onConflict: 'user_id, topic' });

  } catch (err) {
    logError(err, "LEARNING_LOOP_UPDATE");
  }
}

/**
 * Ranks memory by relevance to the current prompt.
 * Simple keyword matching for high performance.
 */
function rankMemory(prompt: string, memory: any[]) {
  const words = prompt.toLowerCase().split(' ');
  return memory
    .map(m => {
      let score = 0;
      const key = m.key.toLowerCase();
      if (words.some(w => key.includes(w))) score += 5;
      return { ...m, score };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);
}

function determineStrategy(profile: any) {
  if (profile.mastery_score < 30) return 'Scaffolded Explanations';
  if (profile.knowledge_gaps.length > 2) return 'Gap Remediation';
  return 'Socratic Challenging';
}

async function processFeedbackLoop(supabase: any, userId: string, prompt: string, response: string, profile: any) {
  try {
    // 1. Log Interaction
    await supabase.from('learning_interactions').insert({
      user_id: userId,
      topic: prompt.substring(0, 50),
      interaction_type: 'chat',
      tutor_strategy_used: determineStrategy(profile),
      metadata: { prompt, response }
    });

    // 2. Simple Knowledge Gap Detection (Simulated)
    if (prompt.includes('don\'t understand') || prompt.includes('confused')) {
      const newGaps = [...(profile.knowledge_gaps || []), prompt.substring(0, 30)];
      await supabase.from('learning_profile')
        .update({ 
          knowledge_gaps: newGaps.slice(-5),
          updated_at: new Date().toISOString() 
        })
        .eq('user_id', userId);
    }
  } catch (err) {
    logError(err, "FEEDBACK_LOOP");
  }
}

async function fetchSimilarityDocs(query: string, userId: string) {
  try {
    // Re-using our internal search API logic
    const res = await fetch(`${process.env.NEXT_PUBLIC_APP_URL}/api/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit: 3 })
    });
    if (!res.ok) return [];
    const { documents } = await res.json();
    return documents;
  } catch {
    return [];
  }
}
