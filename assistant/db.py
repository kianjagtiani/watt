import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  phone      TEXT PRIMARY KEY,
  name       TEXT NOT NULL DEFAULT '',
  is_admin   INTEGER NOT NULL DEFAULT 0,
  timezone   TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_phone   TEXT NOT NULL,
  text         TEXT NOT NULL,
  category     TEXT NOT NULL DEFAULT 'General',
  status       TEXT NOT NULL DEFAULT 'open',
  source       TEXT NOT NULL DEFAULT 'text',
  created_at   TEXT NOT NULL,
  completed_at TEXT
);
CREATE TABLE IF NOT EXISTS reminders (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_phone   TEXT NOT NULL,
  text         TEXT NOT NULL,
  next_fire_at TEXT NOT NULL,
  recurrence   TEXT NOT NULL DEFAULT 'none',
  active       INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS messages (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_phone TEXT NOT NULL,
  role       TEXT NOT NULL,
  content    TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS processed (message_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS refused (phone TEXT PRIMARY KEY);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn
