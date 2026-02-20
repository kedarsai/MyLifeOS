-- =====================================
-- Thought Areas (broad categories, ~10-20 total)
-- =====================================
CREATE TABLE IF NOT EXISTS thought_areas (
  area_id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE COLLATE NOCASE,
  description TEXT NOT NULL DEFAULT '',
  source_run_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_thought_areas_name ON thought_areas(name COLLATE NOCASE);

-- =====================================
-- Thought Topics (specific threads within areas)
-- =====================================
CREATE TABLE IF NOT EXISTS thought_topics (
  topic_id TEXT PRIMARY KEY,
  area_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  source_run_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(area_id, name COLLATE NOCASE),
  FOREIGN KEY (area_id) REFERENCES thought_areas(area_id) ON DELETE CASCADE,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_thought_topics_area ON thought_topics(area_id);

-- =====================================
-- Entry-Topic links (many-to-many)
-- =====================================
CREATE TABLE IF NOT EXISTS entry_topics (
  entry_id TEXT NOT NULL,
  topic_id TEXT NOT NULL,
  source_run_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (entry_id, topic_id),
  FOREIGN KEY (entry_id) REFERENCES entries_index(id) ON DELETE CASCADE,
  FOREIGN KEY (topic_id) REFERENCES thought_topics(topic_id) ON DELETE CASCADE,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_entry_topics_topic ON entry_topics(topic_id);

-- =====================================
-- Ideas (versioned, lifecycle tracking)
-- =====================================
CREATE TABLE IF NOT EXISTS ideas (
  idea_id TEXT PRIMARY KEY,
  logical_id TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'raw'
    CHECK (status IN ('raw', 'exploring', 'mature', 'converted', 'parked', 'dropped')),
  converted_to_type TEXT
    CHECK (converted_to_type IS NULL OR converted_to_type IN ('goal', 'project', 'task')),
  converted_to_id TEXT,
  source_entry_id TEXT,
  source_run_id TEXT NOT NULL,
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
  FOREIGN KEY (supersedes_id) REFERENCES ideas(idea_id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ideas_one_current
  ON ideas(logical_id) WHERE is_current = 1;
CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas(status);
CREATE INDEX IF NOT EXISTS idx_ideas_logical ON ideas(logical_id, version_no DESC);

-- =====================================
-- Idea-Entry links (captures that feed into an idea)
-- =====================================
CREATE TABLE IF NOT EXISTS idea_entries (
  idea_id TEXT NOT NULL,
  entry_id TEXT NOT NULL,
  link_type TEXT NOT NULL DEFAULT 'related'
    CHECK (link_type IN ('source', 'related', 'evidence', 'update')),
  source_run_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (idea_id, entry_id, link_type),
  FOREIGN KEY (idea_id) REFERENCES ideas(idea_id) ON DELETE CASCADE,
  FOREIGN KEY (entry_id) REFERENCES entries_index(id) ON DELETE CASCADE,
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_idea_entries_entry ON idea_entries(entry_id);

-- =====================================
-- Insight Cards (versioned, polymorphic entity link)
-- =====================================
CREATE TABLE IF NOT EXISTS insight_cards (
  card_id TEXT PRIMARY KEY,
  logical_id TEXT NOT NULL,
  source_run_id TEXT NOT NULL,
  entity_type TEXT NOT NULL
    CHECK (entity_type IN ('goal', 'thought_topic', 'idea')),
  entity_id TEXT NOT NULL,
  source_thread_id TEXT,
  title TEXT NOT NULL,
  body_md TEXT NOT NULL,
  action_taken TEXT,
  tags_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(tags_json)),
  payload_hash TEXT NOT NULL,
  payload_hash_version TEXT NOT NULL DEFAULT 'sha256-v1',
  version_no INTEGER NOT NULL DEFAULT 1 CHECK (version_no >= 1),
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  supersedes_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(source_run_id, payload_hash, payload_hash_version),
  UNIQUE(logical_id, version_no),
  FOREIGN KEY (source_run_id) REFERENCES artifact_runs(run_id) ON DELETE RESTRICT,
  FOREIGN KEY (supersedes_id) REFERENCES insight_cards(card_id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_insight_cards_one_current
  ON insight_cards(logical_id) WHERE is_current = 1;
CREATE INDEX IF NOT EXISTS idx_insight_cards_entity
  ON insight_cards(entity_type, entity_id, is_current);

-- =====================================
-- Chat threads: add polymorphic entity columns
-- =====================================
ALTER TABLE chat_threads ADD COLUMN entity_type TEXT
  CHECK (entity_type IS NULL OR entity_type IN ('goal', 'thought_topic', 'idea'));
ALTER TABLE chat_threads ADD COLUMN entity_id TEXT;

-- Back-fill existing goal-linked threads
UPDATE chat_threads SET entity_type = 'goal', entity_id = goal_id
  WHERE goal_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_chat_threads_entity
  ON chat_threads(entity_type, entity_id);

-- =====================================
-- Chat messages: add proposed actions
-- =====================================
ALTER TABLE chat_messages ADD COLUMN proposed_actions_json TEXT
  CHECK (proposed_actions_json IS NULL OR json_valid(proposed_actions_json));
