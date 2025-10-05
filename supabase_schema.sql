-- Production-ready Supabase schema for LiveKit AI Agent
-- This schema is designed to work without Supabase Auth dependencies

-- ========================
-- USER_PROFILES (main user info)
-- ========================
create table user_profiles (
  user_id uuid primary key default gen_random_uuid(),
  profile_text text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- ====================
-- MEMORY (user memory)
-- ====================
create table memory (
  id bigserial primary key,
  user_id uuid not null references user_profiles(user_id) on delete cascade,
  category varchar not null,
  key varchar not null,
  value text not null,
  created_at timestamptz default now(),
  constraint uq_memory_user_key unique (user_id, category, key) -- prevents duplicates
);

-- ====================
-- USER_STATE (SPT directive layer)
-- ====================
create table user_state (
  user_id uuid primary key references user_profiles(user_id) on delete cascade,
  stage text default 'ORIENTATION',
  trust_score int default 2,
  updated_at timestamptz default now()
);

-- ====================
-- CHAT_HISTORY (conversation history)
-- ====================
create table chat_history (
  id bigserial primary key,
  user_id uuid not null references user_profiles(user_id) on delete cascade,
  user_message text not null,
  user_message_roman text,
  ai_message text not null,
  ai_message_roman text,
  created_at timestamptz default now()
);

-- =====================
-- Indexes for performance
-- =====================
create index idx_memory_user_id on memory(user_id);
create index idx_memory_category on memory(category);
create index idx_chat_history_user_id on chat_history(user_id);
create index idx_chat_history_created_at on chat_history(created_at);

-- =====================
-- Row Level Security (RLS) Policies
-- =====================
-- Enable RLS on all tables
alter table user_profiles enable row level security;
alter table memory enable row level security;
alter table user_state enable row level security;
alter table chat_history enable row level security;

-- Create policies that allow all operations (since we're not using auth.users)
-- In production, you might want to implement proper user-based policies
create policy "Allow all operations on user_profiles" on user_profiles
  for all using (true);

create policy "Allow all operations on memory" on memory
  for all using (true);

create policy "Allow all operations on user_state" on user_state
  for all using (true);

create policy "Allow all operations on chat_history" on chat_history
  for all using (true);
