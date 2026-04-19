import { createClient } from '@supabase/supabase-js';

/**
 * Global Improvement Loop — Nightly Optimization Job.
 * Aggregates user data to update skill difficulty, teaching strategies, and suggest graph improvements.
 */

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function optimizeSystem() {
  console.log('Optimization: Starting global improvement loop...');

  try {
    // 1. Aggregate Skill Analytics
    await updateSkillAnalytics();

    // 2. Optimize Teaching Strategies
    await optimizeTeachingStrategies();

    // 3. Detect Knowledge Graph Gaps
    await suggestGraphImprovements();

    console.log('Optimization: System-wide improvements applied.');
  } catch (error) {
    console.error('Optimization: Failed', error);
  }
}

async function updateSkillAnalytics() {
  const { data: skills } = await supabase.from('skills').select('id');
  if (!skills) return;

  for (const skill of skills) {
    // Calculate avg mastery and failure rate from user_skills
    const { data: userSkills } = await supabase
      .from('user_skills')
      .select('mastery_score')
      .eq('skill_id', skill.id);

    if (!userSkills || userSkills.length === 0) continue;

    const avgMastery = userSkills.reduce((acc, curr) => acc + curr.mastery_score, 0) / userSkills.length;
    const failureRate = userSkills.filter(s => s.mastery_score < 0.3).length / userSkills.length;

    // Adjust difficulty_score: higher failure rate = higher difficulty
    const difficultyScore = Math.min(1.0, failureRate * 1.5);

    await supabase.from('learning_analytics').upsert({
      skill_id: skill.id,
      avg_mastery: avgMastery,
      failure_rate: failureRate,
      difficulty_score: difficultyScore,
      updated_at: new Date().toISOString()
    });
  }
}

interface Interaction {
  topic: string;
  tutor_strategy_used: string;
  user_response_quality: number;
}

async function optimizeTeachingStrategies() {
  // Aggregate success rates of different strategies per skill from learning_interactions
  const { data } = await supabase
    .from('learning_interactions')
    .select('topic, tutor_strategy_used, user_response_quality');

  const interactions = data as Interaction[] | null;

  if (!interactions) return;

  // Simple aggregation logic (in production, use a more complex statistical model)
  const strategyStats = new Map<string, { total: number; success: number }>();

  interactions.forEach(i => {
    const key = `${i.topic}:${i.tutor_strategy_used}`;
    const stats = strategyStats.get(key) || { total: 0, success: 0 };
    stats.total += 1;
    stats.success += i.user_response_quality > 0.7 ? 1 : 0;
    strategyStats.set(key, stats);
  });

  // Update teaching_effectiveness table
  for (const [key, stats] of strategyStats.entries()) {
    const [topic, strategy] = key.split(':');
    const successRate = stats.success / stats.total;

    await supabase.from('teaching_effectiveness').upsert({
      skill_id: topic, // Assuming topic matches skill_id for now
      strategy: strategy,
      success_rate: successRate,
      total_interactions: stats.total
    });
  }
}

async function suggestGraphImprovements() {
  // If many users fail Skill B but have mastered its prerequisites,
  // suggest that an intermediate skill might be missing.
  const { data: strugglingSkills } = await supabase
    .from('learning_analytics')
    .select('skill_id')
    .gt('failure_rate', 0.4);

  if (!strugglingSkills) return;

  for (const { skill_id } of strugglingSkills) {
    await supabase.from('suggested_edges').insert({
      skill_id,
      reason: "High failure rate detected. Prerequisite chain might be incomplete.",
      confidence: 0.7,
      status: 'pending'
    });
  }
}
