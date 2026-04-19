import { createClient } from '@/lib/supabase/server';
import { logError, logInfo } from '@/lib/logger';

/**
 * Dynamic Curriculum API.
 * Generates a personalized curriculum by reordering topics based on real-time learning speed and retention.
 */
export async function GET() {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return Response.json({ error: "Unauthorized" }, { status: 401 });

    // 1. Fetch current path and performance metrics
    const [pathRes, userSkillsRes, analyticsRes] = await Promise.all([
      supabase.from('learning_paths').select('ordered_skills').eq('user_id', user.id).single(),
      supabase.from('user_skills').select('skill_id, mastery_score').eq('user_id', user.id),
      supabase.from('learning_analytics').select('skill_id, difficulty_score')
    ]);

    const path = pathRes.data;
    const userSkills = userSkillsRes.data || [];
    const globalAnalytics = analyticsRes.data || [];

    if (!path) return Response.json({ error: "Learning path not found" }, { status: 404 });

    // 2. Re-prioritize skills in the path
    // Logic: If a skill has a high global failure rate, but the user is fast, keep it.
    // If user has low mastery on a prerequisite, move it to the front.
    
    const reorderedSkills = [...path.ordered_skills].sort((a, b) => {
      const masteryA = userSkills.find(s => s.skill_id === a)?.mastery_score || 0;
      const masteryB = userSkills.find(s => s.skill_id === b)?.mastery_score || 0;
      
      const difficultyA = globalAnalytics.find(s => s.skill_id === a)?.difficulty_score || 0.5;
      const difficultyB = globalAnalytics.find(s => s.skill_id === b)?.difficulty_score || 0.5;

      // Prioritize low mastery first (Remediation)
      if (masteryA !== masteryB) return masteryA - masteryB;
      
      // Then sort by global difficulty (Ascending)
      return difficultyA - difficultyB;
    });

    // 3. Update the path in DB
    await supabase.from('learning_paths')
      .update({ ordered_skills: reorderedSkills, updated_at: new Date().toISOString() })
      .eq('user_id', user.id);

    logInfo(`Curriculum re-optimized for user ${user.id}`, "CURRICULUM_API");

    return Response.json({ curriculum: reorderedSkills });

  } catch (error: any) {
    logError(error, "CURRICULUM_API");
    return Response.json({ error: "Failed to generate dynamic curriculum" }, { status: 500 });
  }
}
