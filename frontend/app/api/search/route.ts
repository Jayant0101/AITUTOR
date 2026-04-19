import { createClient } from '@/lib/supabase/server';
import { logError, logInfo } from '@/lib/logger';
import { trackEvent } from '@/lib/analytics/tracker';
import { SearchQuerySchema, sanitizeInput } from '@/lib/validation';

/**
 * RAG Search API — Enterprise-Grade Vector Search.
 * Performs similarity search using pgvector on the documents table.
 */
export async function POST(req: Request) {
  try {
    const rawBody = await req.json();
    
    // 1. Validation
    const validation = SearchQuerySchema.safeParse(rawBody);
    if (!validation.success) {
      return Response.json({ error: "Invalid input", details: validation.error.format() }, { status: 400 });
    }

    const { query, limit } = validation.data;
    const sanitizedQuery = sanitizeInput(query);

    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return Response.json({ error: "Unauthorized" }, { status: 401 });

    logInfo(`Vector search: ${sanitizedQuery}`, "RAG_SEARCH");

    // 2. Generate Embedding via AI Backend (Proxy)
    const embeddingRes = await fetch(`${process.env.AI_BACKEND_URL || "http://localhost:8000"}/embed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: sanitizedQuery })
    });

    if (!embeddingRes.ok) throw new Error("Failed to generate embedding");
    const { embedding } = await embeddingRes.json();

    // 2. Perform Similarity Search in Supabase
    // Note: 'match_documents' is a Postgres function defined in schema.sql
    const { data: documents, error } = await supabase.rpc('match_documents', {
      query_embedding: embedding,
      match_threshold: 0.5,
      match_count: limit,
      filter_user_id: user.id // Ensure multi-user isolation
    });

    if (error) throw error;

    await trackEvent('vector_search_success', { results_count: documents.length });

    return Response.json({ documents });

  } catch (error: any) {
    logError(error, "RAG_SEARCH_API");
    return Response.json({ error: "Search failed", details: error.message }, { status: 500 });
  }
}
