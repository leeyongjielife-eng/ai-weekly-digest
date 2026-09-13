PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS articles (
  id TEXT PRIMARY KEY,
  canonical_url TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  author TEXT,
  source TEXT NOT NULL,
  source_type TEXT NOT NULL,
  published_at TEXT,
  email_received_at TEXT NOT NULL,
  summary_zh TEXT NOT NULL,
  why_it_matters TEXT NOT NULL,
  primary_category TEXT NOT NULL,
  value_score INTEGER NOT NULL CHECK (value_score BETWEEN 1 AND 5),
  content_status TEXT NOT NULL CHECK (content_status IN ('complete', 'email_only', 'failed')),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS article_tags (
  article_id TEXT NOT NULL,
  tag TEXT NOT NULL,
  position INTEGER NOT NULL CHECK (position >= 0),
  PRIMARY KEY (article_id, position),
  UNIQUE (article_id, tag),
  FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS article_key_points (
  article_id TEXT NOT NULL,
  point TEXT NOT NULL,
  position INTEGER NOT NULL CHECK (position >= 0),
  PRIMARY KEY (article_id, position),
  FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS article_content (
  article_id TEXT PRIMARY KEY,
  raw_text TEXT,
  extracted_title TEXT,
  extracted_author TEXT,
  extracted_published_at TEXT,
  extraction_status TEXT NOT NULL DEFAULT 'pending' CHECK (extraction_status IN ('pending', 'complete', 'failed')),
  extracted_at TEXT,
  error_message TEXT,
  FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_states (
  article_id TEXT PRIMARY KEY,
  is_read INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0, 1)),
  is_favorite INTEGER NOT NULL DEFAULT 0 CHECK (is_favorite IN (0, 1)),
  is_in_knowledge_base INTEGER NOT NULL DEFAULT 0 CHECK (is_in_knowledge_base IN (0, 1)),
  personal_note TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS processing_runs (
  run_id TEXT PRIMARY KEY,
  run_type TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  success_count INTEGER NOT NULL DEFAULT 0 CHECK (success_count >= 0),
  failed_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
  result TEXT NOT NULL CHECK (result IN ('success', 'partial', 'failed')),
  notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS processing_items (
  run_id TEXT NOT NULL,
  article_id TEXT,
  stage TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('success', 'skipped', 'failed')),
  error_message TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  PRIMARY KEY (run_id, article_id, stage),
  FOREIGN KEY (run_id) REFERENCES processing_runs(run_id) ON DELETE CASCADE,
  FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_articles_email_received_at ON articles(email_received_at);
CREATE INDEX IF NOT EXISTS idx_articles_primary_category ON articles(primary_category);
CREATE INDEX IF NOT EXISTS idx_article_tags_tag ON article_tags(tag);
CREATE INDEX IF NOT EXISTS idx_processing_items_article ON processing_items(article_id);
