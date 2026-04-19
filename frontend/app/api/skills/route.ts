import { createClient } from '@/lib/supabase/server';
import { logError } from '@/lib/logger';

/**
 * Skill Graph API.
 * Returns the global skill graph and the user's current mastery for each node.
 */
export async function GET() {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return Response.json({ error: "Unauthorized" }, { status: 401 });

    // 1. Fetch all skills, dependencies, and user mastery in parallel
    const [skillsRes, depsRes, userSkillsRes] = await Promise.all([
      supabase.from('skills').select('id, name, description, category'),
      supabase.from('skill_dependencies').select('skill_id, depends_on'),
      supabase.from('user_skills').select('skill_id, mastery_score, last_updated_at, predicted_decay_at').eq('user_id', user.id)
    ]);

    if (skillsRes.error) throw skillsRes.error;
    if (depsRes.error) throw depsRes.error;

    const skills = skillsRes.data || [];
    const dependencies = depsRes.data || [];
    const userMastery = userSkillsRes.data || [];

    // 2. Map mastery to skills
    const skillNodes = skills.map(skill => {
      const mastery = userMastery.find(um => um.skill_id === skill.id);
      return {
        ...skill,
        mastery_score: mastery?.mastery_score || 0,
        last_updated: mastery?.last_updated_at || null,
        predicted_decay: mastery?.predicted_decay_at || null
      };
    });

    return Response.json({
      nodes: skillNodes,
      edges: dependencies.map(d => ({ source: d.depends_on, target: d.skill_id }))
    });

  } catch (error: any) {
    logError(error, "SKILLS_GRAPH_API");
    return Response.json({ error: "Failed to fetch skill graph" }, { status: 500 });
  }
}
