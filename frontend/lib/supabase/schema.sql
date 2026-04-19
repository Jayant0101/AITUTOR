-- SQL Setup for Enterprise-Grade High-Scale AI SaaS System

-- Enable necessary extensions
create extension if not exists "uuid-ossp";
create extension if not exists "vector"; -- Support for pgvector

-- 1. User Activity System (Analytics)
create table if not exists user_activity (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references auth.users(id) on delete cascade,
  action text not null,
  metadata jsonb default '{}'::jsonb,
  created_at timestamp with time zone default now()
);

-- 2. Background Job System (Enhanced)
create table if not exists jobs (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references auth.users(id) on delete cascade,
  type text not null,
  payload jsonb default '{}'::jsonb,
  status text default 'pending', -- 'pending', 'processing', 'completed', 'failed'
  retry_count int default 0,
  error_message text,
  last_attempt_at timestamp with time zone,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

-- 3. Dead Jobs Table (For permanently failed tasks)
create table if not exists dead_jobs (
  id uuid primary key,
  user_id uuid references auth.users(id) on delete cascade,
  type text not null,
  payload jsonb,
  error_message text,
  failed_at timestamp with time zone default now()
);

-- 4. Profile Table (Enterprise SaaS Core)
create table if not exists profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text unique not null,
  subscription_tier text default 'free', -- 'free', 'pro', 'enterprise'
  billing_status text default 'active', -- 'active', 'past_due', 'canceled'
  stripe_customer_id text,
  stripe_subscription_id text,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

-- 5. RAG System (Vector Search)
create table if not exists documents (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references auth.users(id) on delete cascade,
  content text not null,
  metadata jsonb default '{}'::jsonb,
  embedding vector(1536), -- Standard OpenAI dimension
  created_at timestamp with time zone default now()
);

-- 6. Critical Logs (Database Logging for Observability)
create table if not exists app_logs (
  id uuid primary key default uuid_generate_v4(),
  level text not null, -- 'INFO', 'ERROR', 'WARN'
  context text,
  message text not null,
  metadata jsonb default '{}'::jsonb,
  created_at timestamp with time zone default now()
);

-- --- SECURITY: ROW LEVEL SECURITY ---
alter table user_activity enable row level security;
alter table jobs enable row level security;
alter table dead_jobs enable row level security;
alter table profiles enable row level security;
alter table documents enable row level security;
-- app_logs are generally readable only by admins or system role

-- RLS Policies
create policy "Users can only view their own activity" on user_activity for select using (auth.uid() = user_id);
create policy "Users can only insert their own activity" on user_activity for insert with check (auth.uid() = user_id);

create policy "Users can only view their own jobs" on jobs for select using (auth.uid() = user_id);
create policy "Users can only insert their own jobs" on jobs for insert with check (auth.uid() = user_id);

create policy "Users can only view their own dead jobs" on dead_jobs for select using (auth.uid() = user_id);

create policy "Users can only view their own profile" on profiles for select using (auth.uid() = id);
create policy "Users can only update their own profile" on profiles for update using (auth.uid() = id);

create policy "Users can only manage their own documents" on documents for all using (auth.uid() = user_id);

-- --- TRIGGERS & FUNCTIONS ---

-- Automatic profile creation on signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email, subscription_tier)
  values (new.id, new.email, 'free');
  return new;
end;
$$;

create or replace trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Updated at timestamp trigger
create or replace function update_updated_at_column()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger update_jobs_updated_at before update on jobs for each row execute procedure update_updated_at_column();
create trigger update_profiles_updated_at before update on profiles for each row execute procedure update_updated_at_column();

-- Atomic job claiming for worker (Prevents race conditions)
create or replace function claim_jobs(worker_id text, batch_size int)
returns setof jobs
language plpgsql
security definer
as $$
begin
  return query
  update jobs
  set 
    status = 'processing',
    updated_at = now(),
    metadata = metadata || jsonb_build_object('worker_id', worker_id)
  where id in (
    select id from jobs
    where status = 'pending'
    order by created_at asc
    for update skip locked
    limit batch_size
  )
  returning id, user_id, type, payload, status, retry_count, error_message, last_attempt_at, created_at, updated_at;
end;
$$;

-- --- PERFORMANCE: INDEXING ---
create index if not exists idx_user_activity_user_id on user_activity(user_id);
create index if not exists idx_jobs_user_id_status on jobs(user_id, status);
create index if not exists idx_jobs_status_pending on jobs(status) where status = 'pending';
create index if not exists idx_documents_user_id on documents(user_id);
create index if not exists idx_documents_embedding on documents using hnsw (embedding vector_cosine_ops);

-- 7. User Memory System (For AI Personalization)
create table if not exists user_memory (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references auth.users(id) on delete cascade,
  key text not null,
  value jsonb default '{}'::jsonb,
  created_at timestamp with time zone default now()
);

-- 8. Learning Profile Engine (Upgraded for Retention & Mastery)
create table if not exists learning_profile (
  user_id uuid primary key references auth.users(id) on delete cascade,
  skill_level text default 'beginner',
  mastery_score int default 0,
  confidence_score int default 0,
  retention_score int default 0, -- New: retention-driven metric
  xp_points int default 0, -- New: gamification
  streak_count int default 0, -- New: gamification
  last_activity_at timestamp with time zone default now(),
  learning_velocity float default 1.0,
  tutor_persona text default 'friendly mentor',
  explanation_style text default 'analogy-based',
  strengths jsonb default '[]'::jsonb,
  weaknesses jsonb default '[]'::jsonb,
  accuracy_stats jsonb default '{}'::jsonb,
  knowledge_gaps jsonb default '[]'::jsonb,
  study_plan jsonb default '{}'::jsonb,
  time_spent_seconds int default 0,
  last_topic text,
  updated_at timestamp with time zone default now()
);

-- 11. Spaced Repetition System (SRS)
create table if not exists spaced_repetition (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references auth.users(id) on delete cascade,
  topic text not null,
  next_review timestamp with time zone default now(),
  interval_days int default 1,
  ease_factor float default 2.5,
  mastery_level float default 0.0, -- 0-1 range for specific topic
  last_reviewed_at timestamp with time zone,
  created_at timestamp with time zone default now()
);

-- 12. Gamification: Badges & Achievements
create table if not exists achievements (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references auth.users(id) on delete cascade,
  badge_id text not null, -- 'streak_7', 'master_of_python', etc.
  unlocked_at timestamp with time zone default now()
);

-- 13. Skill Graph System (Knowledge Nodes)
create table if not exists skills (
  id uuid primary key default uuid_generate_v4(),
  name text unique not null,
  description text,
  category text, -- 'math', 'cs', 'physics', etc.
  created_at timestamp with time zone default now()
);

-- 14. Skill Dependencies (Prerequisite Relationships)
create table if not exists skill_dependencies (
  skill_id uuid references skills(id) on delete cascade,
  depends_on uuid references skills(id) on delete cascade,
  primary key (skill_id, depends_on)
);

-- 15. User Skill Mastery (Personal Knowledge Graph)
create table if not exists user_skills (
  user_id uuid references auth.users(id) on delete cascade,
  skill_id uuid references skills(id) on delete cascade,
  mastery_score float default 0.0, -- 0.0 - 1.0
  predicted_decay_at timestamp with time zone,
  last_updated_at timestamp with time zone default now(),
  primary key (user_id, skill_id)
);

-- 16. Learning Paths (Optimized Sequences)
create table if not exists learning_paths (
  user_id uuid primary key references auth.users(id) on delete cascade,
  ordered_skills jsonb not null, -- Array of skill IDs in optimal order
  current_step_index int default 0,
  updated_at timestamp with time zone default now()
);

-- Enable RLS for graph tables
alter table skills enable row level security;
alter table skill_dependencies enable row level security;
alter table user_skills enable row level security;
alter table learning_paths enable row level security;

-- RLS Policies
create policy "Skills are readable by all" on skills for select using (true);
create policy "Dependencies are readable by all" on skill_dependencies for select using (true);
create policy "Users can manage their own skills" on user_skills for all using (auth.uid() = user_id);
create policy "Users can manage their own paths" on learning_paths for all using (auth.uid() = user_id);

-- Indices for graph performance
create index if not exists idx_user_skills_mastery on user_skills(user_id, mastery_score);
create index if not exists idx_skill_dependencies_child on skill_dependencies(skill_id);
create index if not exists idx_skill_dependencies_parent on skill_dependencies(depends_on);

-- 17. Global Learning Analytics (System-Wide Intelligence)
create table if not exists learning_analytics (
  id uuid primary key default uuid_generate_v4(),
  skill_id uuid references skills(id) on delete cascade,
  avg_mastery float default 0.0,
  failure_rate float default 0.0,
  avg_time_to_mastery_seconds float default 0.0,
  difficulty_score float default 0.5, -- 0.0 (easy) - 1.0 (hard), auto-adjusted
  updated_at timestamp with time zone default now()
);

-- 18. Teaching Effectiveness (Strategy Optimization)
create table if not exists teaching_effectiveness (
  skill_id uuid references skills(id) on delete cascade,
  strategy text not null, -- 'socratic', 'example-based', 'step-by-step', etc.
  success_rate float default 0.0,
  total_interactions int default 0,
  primary key (skill_id, strategy)
);

-- 19. Curriculum Versioning & Graph Updates
create table if not exists curriculum_versions (
  id uuid primary key default uuid_generate_v4(),
  changes jsonb not null, -- { "added_edges": [], "removed_edges": [], "difficulty_updates": {} }
  description text,
  created_at timestamp with time zone default now()
);

-- 20. Suggested Graph Edges (AI/Data-Driven Recommendations)
create table if not exists suggested_edges (
  id uuid primary key default uuid_generate_v4(),
  skill_id uuid references skills(id) on delete cascade,
  depends_on uuid references skills(id) on delete cascade,
  reason text,
  confidence float default 0.0,
  status text default 'pending', -- 'pending', 'applied', 'rejected'
  created_at timestamp with time zone default now()
);

-- Enable RLS for analytics tables (Admin only for most)
alter table learning_analytics enable row level security;
alter table teaching_effectiveness enable row level security;
alter table curriculum_versions enable row level security;
alter table suggested_edges enable row level security;

-- RLS Policies
create policy "Analytics are readable by all" on learning_analytics for select using (true);
create policy "Teaching effectiveness is readable by all" on teaching_effectiveness for select using (true);

-- Indices for analytics performance
create index idx_learning_analytics_skill on learning_analytics(skill_id);
create index idx_teaching_effectiveness_success on teaching_effectiveness(success_rate desc);
create index idx_suggested_edges_status on suggested_edges(status);

-- Enable RLS
alter table spaced_repetition enable row level security;
alter table achievements enable row level security;

-- RLS Policies
create policy "Users can manage their own SRS" on spaced_repetition for all using (auth.uid() = user_id);
create policy "Users can view their own achievements" on achievements for select using (auth.uid() = user_id);

-- Indices for SRS performance
create index idx_srs_user_next_review on spaced_repetition(user_id, next_review);
create index idx_srs_topic on spaced_repetition(topic);

-- 9. Learning Interactions (For Feedback Loop)
create table if not exists learning_interactions (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references auth.users(id) on delete cascade,
  topic text not null,
  interaction_type text not null, -- 'question', 'explanation', 'quiz'
  user_response_quality float, -- 0-1 (e.g., accuracy or depth)
  tutor_strategy_used text, -- 'socratic', 'direct', 'hint'
  test_group text, -- 'A', 'B', 'control'
  interaction_duration_seconds int,
  metadata jsonb default '{}'::jsonb,
  created_at timestamp with time zone default now()
);

-- 10. Study Plans (Persistent Recommendations)
create table if not exists study_plans (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references auth.users(id) on delete cascade,
  title text not null,
  goals jsonb not null,
  milestones jsonb default '[]'::jsonb,
  current_step int default 0,
  is_active boolean default true,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

-- Enable RLS
alter table learning_interactions enable row level security;
alter table study_plans enable row level security;

-- RLS Policies
create policy "Users can view their own interactions" on learning_interactions for select using (auth.uid() = user_id);
create policy "Users can insert their own interactions" on learning_interactions for insert with check (auth.uid() = user_id);
create policy "Users can manage their own study plans" on study_plans for all using (auth.uid() = user_id);

-- System Logs RLS
alter table app_logs enable row level security;
create policy "System logs are readable by admins" on app_logs for select using (auth.jwt() ->> 'email' like '%@admin.com');
create policy "Authenticated users can insert logs" on app_logs for insert with check (auth.uid() is not null);

-- Enable RLS for new tables
alter table user_memory enable row level security;
alter table learning_profile enable row level security;

-- RLS Policies for new tables
create policy "Users can manage their own memory" on user_memory for all using (auth.uid() = user_id);
create policy "Users can view their own learning profile" on learning_profile for select using (auth.uid() = user_id);

-- Trigger for automatic learning profile creation
create or replace function public.handle_new_user_learning()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.learning_profile (user_id)
  values (new.id);
  return new;
end;
$$;

create or replace trigger on_auth_user_created_learning
  after insert on auth.users
  for each row execute procedure public.handle_new_user_learning();

-- Performance indexing for memory
create index idx_user_memory_user_id_key on user_memory(user_id, key);
create index idx_learning_profile_skill_level on learning_profile(skill_level);

-- Function for similarity search with user isolation
create or replace function match_documents (
  query_embedding vector(1536),
  match_threshold float,
  match_count int,
  filter_user_id uuid
)
returns table (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    documents.id,
    documents.content,
    documents.metadata,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where documents.user_id = filter_user_id
    and 1 - (documents.embedding <=> query_embedding) > match_threshold
  order by similarity desc
  limit match_count;
end;
$$;
