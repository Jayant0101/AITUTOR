import { createClient } from '@/lib/supabase/server';
import { logError } from '@/lib/logger';

/**
 * AI Vector Search Service — High-scale SaaS ready.
 * Integrates with Supabase pgvector for semantic search.
 */
export async function searchSimilar(embedding: number[], matchThreshold: number = 0.5, matchCount: number = 10) {
  const supabase = await createClient();

  try {
    const { data, error } = await supabase.rpc('match_documents', {
      query_embedding: embedding,
      match_threshold: matchThreshold,
      match_count: matchCount,
    });

    if (error) throw error;
    return data;
  } catch (err) {
    logError(err, "VECTOR_SEARCH");
    return [];
  }
}

/**
 * SQL for pgvector documents table (Run this in Supabase SQL Editor):
 * 
 * -- Enable the pgvector extension to work with embeddings
 * create extension if not exists vector;
 * 
 * -- Create the documents table
 * create table if not exists documents (
 *   id bigserial primary key,
 *   content text,
 *   metadata jsonb,
 *   embedding vector(1536) -- Match OpenAI embedding dimension
 * );
 * 
 * -- Create a function for similarity search
 * create or replace function match_documents (
 *   query_embedding vector(1536),
 *   match_threshold float,
 *   match_count int
 * )
 * returns table (
 *   id bigint,
 *   content text,
 *   metadata jsonb,
 *   similarity float
 * )
 * language plpgsql
 * as $$
 * begin
 *   return query
 *   select
 *     documents.id,
 *     documents.content,
 *     documents.metadata,
 *     1 - (documents.embedding <=> query_embedding) as similarity
 *   from documents
 *   where 1 - (documents.embedding <=> query_embedding) > match_threshold
 *   order by similarity desc
 *   limit match_count;
 * end;
 * $$;
 */
