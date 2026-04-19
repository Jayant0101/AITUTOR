import { createClient } from '@/lib/supabase/server';
import { logError, logInfo } from '@/lib/logger';

/**
 * Learning Path Optimizer API.
 * Generates an optimized sequence of skills based on prerequisites and user mastery.
 */
export async function GET() {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return Response.json({ error: "Unauthorized" }, { status: 401 });

    // 1. Fetch graph data
    const [skillsRes, depsRes, userSkillsRes] = await Promise.all([
      supabase.from('skills').select('id, name'),
      supabase.from('skill_dependencies').select('skill_id, depends_on'),
      supabase.from('user_skills').select('skill_id, mastery_score').eq('user_id', user.id)
    ]);

    const skills = skillsRes.data || [];
    const dependencies = depsRes.data || [];
    const mastery = userSkillsRes.data || [];

    // 2. Build adjacency list for topological sort
    const adj = new Map<string, string[]>();
    const inDegree = new Map<string, number>();
    
    skills.forEach(s => {
      adj.set(s.id, []);
      inDegree.set(s.id, 0);
    });

    dependencies.forEach(d => {
      adj.get(d.depends_on)?.push(d.skill_id);
      inDegree.set(d.skill_id, (inDegree.get(d.skill_id) || 0) + 1);
    });

    // 3. Kahn's Algorithm for Topological Sort
    const queue: string[] = [];
    inDegree.forEach((degree, id) => {
      if (degree === 0) queue.push(id);
    });

    const orderedSkills: string[] = [];
    while (queue.length > 0) {
      const u = queue.shift()!;
      orderedSkills.push(u);
      
      adj.get(u)?.forEach(v => {
        inDegree.set(v, inDegree.get(v)! - 1);
        if (inDegree.get(v) === 0) queue.push(v);
      });
    }

    // 4. Update or Create User Path
    const { error: pathError } = await supabase.from('learning_paths').upsert({
      user_id: user.id,
      ordered_skills: orderedSkills,
      updated_at: new Date().toISOString()
    });

    if (pathError) throw pathError;

    logInfo(`Generated optimized learning path for user ${user.id}`, "PATH_OPTIMIZER");

    return Response.json({
      path: orderedSkills.map(id => ({
        id,
        name: skills.find(s => s.id === id)?.name,
        mastery: mastery.find(m => m.skill_id === id)?.mastery_score || 0
      }))
    });

  } catch (error: any) {
    logError(error, "PATH_OPTIMIZER_API");
    return Response.json({ error: "Failed to optimize learning path" }, { status: 500 });
  }
}
