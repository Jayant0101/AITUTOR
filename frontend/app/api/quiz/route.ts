import { createClient } from '@/lib/supabase/server';
import { logError, logInfo } from '@/lib/logger';

/**
 * Quiz Generation API.
 * Generates adaptive questions from the user's weak topics or SRS reviews.
 */
export async function POST(req: Request) {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return Response.json({ error: "Unauthorized" }, { status: 401 });

    // 1. Fetch Weak Topics & Due Reviews
    const { data: profile } = await supabase.from('learning_profile').select('weaknesses').eq('user_id', user.id).single();
    const { data: dueReviews } = await supabase.from('spaced_repetition')
      .select('topic')
      .eq('user_id', user.id)
      .lt('next_review', new Date().toISOString())
      .limit(3);

    const topicsToQuiz = [...(profile?.weaknesses || []), ...(dueReviews?.map(r => r.topic) || [])];
    if (topicsToQuiz.length === 0) {
      return Response.json({ message: "No topics currently need quizing. Keep exploring!" });
    }

    logInfo(`Generating quiz for topics: ${topicsToQuiz.join(', ')}`, "QUIZ_API");

    // 2. Call AI Backend to Generate Questions
    const aiRes = await fetch(`${process.env.AI_BACKEND_URL || "http://localhost:8000"}/generate-quiz`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        topics: topicsToQuiz,
        count: 5,
        difficulty: 'adaptive'
      })
    });

    if (!aiRes.ok) throw new Error("AI Quiz Generation failed");
    const quizData = await aiRes.json();

    return Response.json({
      quiz_id: crypto.randomUUID(),
      questions: quizData.questions,
      topics: topicsToQuiz
    });

  } catch (error: any) {
    logError(error, "QUIZ_API");
    return Response.json({ error: "Failed to generate quiz" }, { status: 500 });
  }
}

/**
 * Submit Quiz Results.
 */
export async function PATCH(req: Request) {
  try {
    const { results } = await req.json(); // { topic: string, correct: boolean }[]
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return Response.json({ error: "Unauthorized" }, { status: 401 });

    // Update SRS and Profile for each result
    for (const result of results) {
      const { topic, correct } = result;
      
      // Update SRS
      const { data: currentSrs } = await supabase.from('spaced_repetition')
        .select('id, interval_days, ease_factor')
        .eq('user_id', user.id)
        .eq('topic', topic)
        .single();

      if (currentSrs) {
        const newInterval = correct ? currentSrs.interval_days * 2 : 1;
        const newEase = correct ? currentSrs.ease_factor : Math.max(1.3, currentSrs.ease_factor - 0.2);
        
        await supabase.from('spaced_repetition')
          .update({
            interval_days: newInterval,
            ease_factor: newEase,
            next_review: new Date(Date.now() + newInterval * 24 * 60 * 60 * 1000).toISOString(),
            last_reviewed_at: new Date().toISOString()
          })
          .eq('id', currentSrs.id);
      }
    }

    return Response.json({ success: true, message: "Progress updated based on quiz results" });

  } catch (error: any) {
    logError(error, "QUIZ_SUBMIT_API");
    return Response.json({ error: "Failed to submit quiz" }, { status: 500 });
  }
}
