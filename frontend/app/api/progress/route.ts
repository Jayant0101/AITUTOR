import { createClient } from '@/lib/supabase/server';
import { logError } from '@/lib/logger';

/**
 * Progress Visualization API.
 * Returns mastery scores, weak areas, and learning trends for the dashboard.
 */
export async function GET() {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return Response.json({ error: "Unauthorized" }, { status: 401 });

    const [profileRes, interactionsRes, srsRes] = await Promise.all([
      supabase.from('learning_profile').select('mastery_score, confidence_score, retention_score, xp_points, streak_count, learning_velocity, weaknesses, knowledge_gaps').eq('user_id', user.id).single(),
      supabase.from('learning_interactions')
        .select('created_at, user_response_quality')
        .eq('user_id', user.id)
        .order('created_at', { ascending: true })
        .limit(30),
      supabase.from('spaced_repetition')
        .select('topic, next_review')
        .eq('user_id', user.id)
        .lt('next_review', new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()) // Due in next 24h
        .order('next_review', { ascending: true })
    ]);

    const profile = profileRes.data;
    const interactions = interactionsRes.data || [];
    const reviews = srsRes.data || [];

    // Format data for visualization (e.g., charts)
    const trendData = interactions.map(i => ({
      date: i.created_at,
      quality: i.user_response_quality
    }));

    return Response.json({
      mastery: profile?.mastery_score || 0,
      confidence: profile?.confidence_score || 0,
      retention: profile?.retention_score || 0,
      xp: profile?.xp_points || 0,
      streak: profile?.streak_count || 0,
      velocity: profile?.learning_velocity || 1.0,
      weaknesses: profile?.weaknesses || [],
      knowledgeGaps: profile?.knowledge_gaps || [],
      upcomingReviews: reviews,
      trends: trendData
    });

  } catch (error) {
    logError(error, "PROGRESS_API");
    return Response.json({ error: "Failed to fetch progress data" }, { status: 500 });
  }
}
