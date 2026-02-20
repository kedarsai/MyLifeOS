PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- =====================================
-- Run provenance (required for all writes)
-- =====================================
CREATE TABLE IF NOT EXISTS artifact_runs (
  run_id TEXT PRIMARY KEY,
  run_kind TEXT NOT NULL CHECK (
    run_kind IN ('llm', 'manual', 'system', 'import', 'rebuild')
  ),
  actor TEXT NOT NULL DEFAULT 'local_user',
  parent_run_id TEXT,
  notes_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(notes_json)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (parent_run_id) REFERENCES artifact_runs(run_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_artifact_runs_kind_created
  ON artifact_runs(run_kind, created_at DESC);

-- =====================================
-- Core entries
-- =====================================
CREATE TABLE IF NOT EXISTS entries_index (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  captured_tz TEXT,
  type TEXT NOT NULL CHECK (
    type IN ('activity', 'sleep', 'food', 'thought', 'idea', 'todo', 'goal', 'note', 'chat')
  ),
  status TEXT NOT NULL CHECK (status IN ('inbox', 'processed', 'archived')),
  summary TEXT,
  raw_text TEXT NOT NULL,
  details_md TEXT,
  actions_md TEXT,
  tags_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(tags_json)),
  goals_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(goals_json)),
  source_run_id TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  content_hash_version TEXT NOT NULL DEFAULT 'sha256-v1',
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_entries_created_at ON entries_index(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_entries_type ON entries_index(type);
CREATE INDEX IF NOT EXISTS idx_entries_status ON entries_index(status);

CREATE TABLE IF NOT EXISTS entry_versions (
  version_id TEXT PRIMARY KEY,
  logical_id TEXT NOT NULL,
  entry_id TEXT NOT NULL,
  source_run_id TEXT NOT NULL,
  version_no INTEGER NOT NULL CHECK (version_no >= 1),
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  supersedes_version_id TEXT,
  summary TEXT,
  details_md TEXT,
  actions_md TEXT,
  tags_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(tags_json)),
  goals_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(goals_json)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(logical_id, version_no),
  FOREIGN KEY (entry_id) REFERENCES entries_index(id) ON DELETE CASCADE,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT,
  FOREIGN KEY (supersedes_version_id) REFERENCES entry_versions(version_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_entry_versions_entry_id ON entry_versions(entry_id);
CREATE INDEX IF NOT EXISTS idx_entry_versions_logical_current
  ON entry_versions(logical_id, is_current, updated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_entry_versions_one_current
  ON entry_versions(logical_id) WHERE is_current = 1;

-- =====================================
-- Prompt registry and LLM run audit
-- =====================================
CREATE TABLE IF NOT EXISTS prompt_templates (
  prompt_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
  prompt_id TEXT NOT NULL,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  params_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(params_json)),
  system_text TEXT NOT NULL,
  user_text TEXT NOT NULL,
  schema_json TEXT NOT NULL CHECK (json_valid(schema_json)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(prompt_id, version)
);

CREATE TABLE IF NOT EXISTS prompt_runs (
  run_id TEXT PRIMARY KEY,
  prompt_id TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  model TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  completed_at TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (
    status IN ('pending', 'success', 'failed')
  ),
  input_refs_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(input_refs_json)),
  output_json TEXT CHECK (output_json IS NULL OR json_valid(output_json)),
  parse_ok INTEGER NOT NULL DEFAULT 0 CHECK (parse_ok IN (0, 1)),
  error_text TEXT,
  FOREIGN KEY (run_id) REFERENCES artifact_runs(run_id) ON DELETE CASCADE,
  FOREIGN KEY (prompt_id, prompt_version) REFERENCES prompt_templates(prompt_id, version)
);

CREATE INDEX IF NOT EXISTS idx_prompt_runs_created_at ON prompt_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_prompt_runs_status ON prompt_runs(status);

-- =====================================
-- Goals and links
-- =====================================
CREATE TABLE IF NOT EXISTS goals (
  goal_id TEXT PRIMARY KEY,
  path TEXT UNIQUE,
  name TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT,
  rules_md TEXT NOT NULL DEFAULT '',
  metrics_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(metrics_json)),
  status TEXT NOT NULL CHECK (status IN ('active', 'paused', 'completed', 'archived')),
  review_cadence_days INTEGER NOT NULL DEFAULT 7 CHECK (review_cadence_days >= 1),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);

CREATE TABLE IF NOT EXISTS goal_links (
  goal_id TEXT NOT NULL,
  entry_id TEXT NOT NULL,
  link_type TEXT NOT NULL CHECK (
    link_type IN ('related', 'evidence', 'blocker', 'milestone')
  ),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (goal_id, entry_id, link_type),
  FOREIGN KEY (goal_id) REFERENCES goals(goal_id) ON DELETE CASCADE,
  FOREIGN KEY (entry_id) REFERENCES entries_index(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_goal_links_entry_id ON goal_links(entry_id);

-- =====================================
-- Observations (typed facts, versioned)
-- Strict idempotency: UNIQUE(source_run_id, payload_hash, payload_hash_version)
-- Chain integrity: UNIQUE(logical_id, version_no) + one current per logical_id
-- =====================================
CREATE TABLE IF NOT EXISTS obs_activity (
  observation_id TEXT PRIMARY KEY,
  logical_id TEXT NOT NULL,
  entry_id TEXT NOT NULL,
  source_run_id TEXT NOT NULL,
  observed_at TEXT,
  steps INTEGER CHECK (steps IS NULL OR steps >= 0),
  duration_min REAL CHECK (duration_min IS NULL OR duration_min >= 0),
  distance_km REAL CHECK (distance_km IS NULL OR distance_km >= 0),
  location TEXT,
  calories REAL CHECK (calories IS NULL OR calories >= 0),
  pace TEXT,
  notes TEXT,
  payload_hash TEXT NOT NULL,
  payload_hash_version TEXT NOT NULL DEFAULT 'sha256-v1',
  version_no INTEGER NOT NULL DEFAULT 1 CHECK (version_no >= 1),
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  supersedes_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(source_run_id, payload_hash, payload_hash_version),
  UNIQUE(logical_id, version_no),
  FOREIGN KEY (entry_id) REFERENCES entries_index(id) ON DELETE CASCADE,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT,
  FOREIGN KEY (supersedes_id) REFERENCES obs_activity(observation_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_obs_activity_entry_id ON obs_activity(entry_id);
CREATE INDEX IF NOT EXISTS idx_obs_activity_logical_current
  ON obs_activity(logical_id, is_current, updated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_obs_activity_one_current
  ON obs_activity(logical_id) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS obs_sleep (
  observation_id TEXT PRIMARY KEY,
  logical_id TEXT NOT NULL,
  entry_id TEXT NOT NULL,
  source_run_id TEXT NOT NULL,
  sleep_start TEXT,
  sleep_end TEXT,
  duration_min REAL CHECK (duration_min IS NULL OR duration_min >= 0),
  quality INTEGER CHECK (quality IS NULL OR quality BETWEEN 1 AND 5),
  notes TEXT,
  payload_hash TEXT NOT NULL,
  payload_hash_version TEXT NOT NULL DEFAULT 'sha256-v1',
  version_no INTEGER NOT NULL DEFAULT 1 CHECK (version_no >= 1),
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  supersedes_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(source_run_id, payload_hash, payload_hash_version),
  UNIQUE(logical_id, version_no),
  FOREIGN KEY (entry_id) REFERENCES entries_index(id) ON DELETE CASCADE,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT,
  FOREIGN KEY (supersedes_id) REFERENCES obs_sleep(observation_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_obs_sleep_entry_id ON obs_sleep(entry_id);
CREATE INDEX IF NOT EXISTS idx_obs_sleep_logical_current
  ON obs_sleep(logical_id, is_current, updated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_obs_sleep_one_current
  ON obs_sleep(logical_id) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS obs_food (
  observation_id TEXT PRIMARY KEY,
  logical_id TEXT NOT NULL,
  entry_id TEXT NOT NULL,
  source_run_id TEXT NOT NULL,
  meal_type TEXT CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack', 'other')),
  items_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(items_json)),
  notes TEXT,
  payload_hash TEXT NOT NULL,
  payload_hash_version TEXT NOT NULL DEFAULT 'sha256-v1',
  version_no INTEGER NOT NULL DEFAULT 1 CHECK (version_no >= 1),
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  supersedes_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(source_run_id, payload_hash, payload_hash_version),
  UNIQUE(logical_id, version_no),
  FOREIGN KEY (entry_id) REFERENCES entries_index(id) ON DELETE CASCADE,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT,
  FOREIGN KEY (supersedes_id) REFERENCES obs_food(observation_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_obs_food_entry_id ON obs_food(entry_id);
CREATE INDEX IF NOT EXISTS idx_obs_food_logical_current
  ON obs_food(logical_id, is_current, updated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_obs_food_one_current
  ON obs_food(logical_id) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS obs_weight (
  observation_id TEXT PRIMARY KEY,
  logical_id TEXT NOT NULL,
  entry_id TEXT NOT NULL,
  source_run_id TEXT NOT NULL,
  measured_at TEXT,
  weight_kg REAL NOT NULL CHECK (weight_kg > 0),
  payload_hash TEXT NOT NULL,
  payload_hash_version TEXT NOT NULL DEFAULT 'sha256-v1',
  version_no INTEGER NOT NULL DEFAULT 1 CHECK (version_no >= 1),
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  supersedes_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(source_run_id, payload_hash, payload_hash_version),
  UNIQUE(logical_id, version_no),
  FOREIGN KEY (entry_id) REFERENCES entries_index(id) ON DELETE CASCADE,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT,
  FOREIGN KEY (supersedes_id) REFERENCES obs_weight(observation_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_obs_weight_entry_id ON obs_weight(entry_id);
CREATE INDEX IF NOT EXISTS idx_obs_weight_logical_current
  ON obs_weight(logical_id, is_current, updated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_obs_weight_one_current
  ON obs_weight(logical_id) WHERE is_current = 1;

-- =====================================
-- Tasks, improvements, insights (versioned)
-- =====================================
CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  logical_id TEXT NOT NULL,
  path TEXT UNIQUE,
  source_entry_id TEXT,
  source_run_id TEXT NOT NULL,
  goal_id TEXT,
  title TEXT NOT NULL,
  due_date TEXT,
  priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high')),
  status TEXT NOT NULL DEFAULT 'open' CHECK (
    status IN ('open', 'in_progress', 'done', 'cancelled')
  ),
  rationale TEXT,
  payload_hash TEXT NOT NULL,
  payload_hash_version TEXT NOT NULL DEFAULT 'sha256-v1',
  version_no INTEGER NOT NULL DEFAULT 1 CHECK (version_no >= 1),
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  supersedes_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(source_run_id, payload_hash, payload_hash_version),
  UNIQUE(logical_id, version_no),
  FOREIGN KEY (source_entry_id) REFERENCES entries_index(id) ON DELETE SET NULL,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT,
  FOREIGN KEY (goal_id) REFERENCES goals(goal_id) ON DELETE SET NULL,
  FOREIGN KEY (supersedes_id) REFERENCES tasks(task_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_due ON tasks(status, due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_goal_id ON tasks(goal_id);
CREATE INDEX IF NOT EXISTS idx_tasks_logical_current
  ON tasks(logical_id, is_current, updated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_one_current
  ON tasks(logical_id) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS improvements (
  improvement_id TEXT PRIMARY KEY,
  logical_id TEXT NOT NULL,
  path TEXT UNIQUE,
  source_entry_id TEXT,
  source_run_id TEXT NOT NULL,
  goal_id TEXT,
  title TEXT NOT NULL,
  rationale TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open' CHECK (
    status IN ('open', 'in_progress', 'adopted', 'dismissed')
  ),
  last_nudged_at TEXT,
  payload_hash TEXT NOT NULL,
  payload_hash_version TEXT NOT NULL DEFAULT 'sha256-v1',
  version_no INTEGER NOT NULL DEFAULT 1 CHECK (version_no >= 1),
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  supersedes_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(source_run_id, payload_hash, payload_hash_version),
  UNIQUE(logical_id, version_no),
  FOREIGN KEY (source_entry_id) REFERENCES entries_index(id) ON DELETE SET NULL,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT,
  FOREIGN KEY (goal_id) REFERENCES goals(goal_id) ON DELETE SET NULL,
  FOREIGN KEY (supersedes_id) REFERENCES improvements(improvement_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_improvements_goal_id ON improvements(goal_id);
CREATE INDEX IF NOT EXISTS idx_improvements_status ON improvements(status);
CREATE INDEX IF NOT EXISTS idx_improvements_logical_current
  ON improvements(logical_id, is_current, updated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_improvements_one_current
  ON improvements(logical_id) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS insights (
  insight_id TEXT PRIMARY KEY,
  logical_id TEXT NOT NULL,
  path TEXT UNIQUE,
  source_entry_id TEXT,
  source_run_id TEXT NOT NULL,
  goal_id TEXT,
  title TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(evidence_json)),
  payload_hash TEXT NOT NULL,
  payload_hash_version TEXT NOT NULL DEFAULT 'sha256-v1',
  version_no INTEGER NOT NULL DEFAULT 1 CHECK (version_no >= 1),
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  supersedes_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(source_run_id, payload_hash, payload_hash_version),
  UNIQUE(logical_id, version_no),
  FOREIGN KEY (source_entry_id) REFERENCES entries_index(id) ON DELETE SET NULL,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT,
  FOREIGN KEY (goal_id) REFERENCES goals(goal_id) ON DELETE SET NULL,
  FOREIGN KEY (supersedes_id) REFERENCES insights(insight_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_insights_goal_id ON insights(goal_id);
CREATE INDEX IF NOT EXISTS idx_insights_logical_current
  ON insights(logical_id, is_current, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_insights_one_current
  ON insights(logical_id) WHERE is_current = 1;

-- =====================================
-- Chat (versioned thread metadata + message log)
-- =====================================
CREATE TABLE IF NOT EXISTS chat_threads (
  thread_id TEXT PRIMARY KEY,
  logical_id TEXT NOT NULL,
  path TEXT UNIQUE,
  source_run_id TEXT NOT NULL,
  goal_id TEXT,
  title TEXT NOT NULL,
  version_no INTEGER NOT NULL DEFAULT 1 CHECK (version_no >= 1),
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  supersedes_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(logical_id, version_no),
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT,
  FOREIGN KEY (goal_id) REFERENCES goals(goal_id) ON DELETE SET NULL,
  FOREIGN KEY (supersedes_id) REFERENCES chat_threads(thread_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_threads_goal_id ON chat_threads(goal_id);
CREATE INDEX IF NOT EXISTS idx_chat_threads_logical_current
  ON chat_threads(logical_id, is_current, updated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_threads_one_current
  ON chat_threads(logical_id) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS chat_messages (
  message_id TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
  content TEXT NOT NULL,
  source_run_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (thread_id) REFERENCES chat_threads(thread_id) ON DELETE CASCADE,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_created
  ON chat_messages(thread_id, created_at);

-- =====================================
-- Weekly reviews and conflicts
-- =====================================
CREATE TABLE IF NOT EXISTS weekly_reviews (
  review_id TEXT PRIMARY KEY,
  goal_id TEXT NOT NULL,
  path TEXT UNIQUE,
  week_start TEXT NOT NULL,
  week_end TEXT NOT NULL,
  snapshot_json TEXT NOT NULL CHECK (json_valid(snapshot_json)),
  review_json TEXT NOT NULL CHECK (json_valid(review_json)),
  source_run_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(goal_id, week_start, week_end),
  FOREIGN KEY (goal_id) REFERENCES goals(goal_id) ON DELETE CASCADE,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_weekly_reviews_goal_week
  ON weekly_reviews(goal_id, week_start DESC);

CREATE TABLE IF NOT EXISTS sync_conflicts (
  conflict_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  logical_id TEXT,
  path TEXT NOT NULL,
  app_run_id TEXT NOT NULL,
  vault_content_hash TEXT,
  vault_hash_version TEXT NOT NULL DEFAULT 'sha256-v1',
  db_content_hash TEXT,
  db_hash_version TEXT NOT NULL DEFAULT 'sha256-v1',
  conflict_status TEXT NOT NULL DEFAULT 'open' CHECK (
    conflict_status IN ('open', 'resolved_keep_vault', 'resolved_keep_app', 'resolved_merged')
  ),
  details_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(details_json)),
  created_at TEXT NOT NULL,
  resolved_at TEXT,
  FOREIGN KEY (app_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_sync_conflicts_status
  ON sync_conflicts(conflict_status, created_at DESC);

CREATE TABLE IF NOT EXISTS sync_conflict_events (
  event_id TEXT PRIMARY KEY,
  conflict_id TEXT NOT NULL,
  action TEXT NOT NULL CHECK (
    action IN ('opened', 'resolved_keep_vault', 'resolved_keep_app', 'resolved_merged', 'reopened')
  ),
  actor TEXT NOT NULL DEFAULT 'local_user',
  source_run_id TEXT,
  notes TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (conflict_id) REFERENCES sync_conflicts(conflict_id) ON DELETE CASCADE,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sync_conflict_events_conflict_created
  ON sync_conflict_events(conflict_id, created_at DESC);

-- =====================================
-- Search (FTS5 on current entry records)
-- =====================================
CREATE VIRTUAL TABLE IF NOT EXISTS fts_entries USING fts5(
  summary,
  raw_text,
  details_md,
  tags,
  goals,
  content='',
  tokenize='unicode61'
);

CREATE TABLE IF NOT EXISTS fts_entries_map (
  entry_id TEXT PRIMARY KEY,
  fts_rowid INTEGER NOT NULL UNIQUE,
  FOREIGN KEY (entry_id) REFERENCES entries_index(id) ON DELETE CASCADE
);

-- Rebuild helper:
-- 1) DELETE FROM fts_entries;
-- 2) DELETE FROM fts_entries_map;
-- 3) INSERT rows from entries_index WHERE status != 'archived' (or your app policy).
