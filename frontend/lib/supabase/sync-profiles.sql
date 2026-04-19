-- SQL Trigger to automatically create a profile row when a new user signs up.
-- Run this in the Supabase SQL Editor.

-- 1. Create the function
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email, subscription)
  values (new.id, new.email, 'free');
  return new;
end;
$$;

-- 2. Create the trigger
create or replace trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- 3. Initial sync (if users already exist)
insert into public.profiles (id, email, subscription)
select id, email, 'free'
from auth.users
on conflict (id) do nothing;
