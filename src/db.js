const fs = require('node:fs');
const path = require('node:path');
const Database = require('better-sqlite3');

const databasePath = process.env.DATABASE_PATH || './data/requests.sqlite';
fs.mkdirSync(path.dirname(path.resolve(databasePath)), { recursive: true });

const db = new Database(databasePath);
db.pragma('journal_mode = WAL');
db.exec(`
  CREATE TABLE IF NOT EXISTS access_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id TEXT NOT NULL,
    telegram_username TEXT,
    github_username TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT,
    reviewed_by TEXT,
    github_invitation_sent_at TEXT,
    UNIQUE(telegram_id, github_username)
  );
  CREATE INDEX IF NOT EXISTS idx_access_requests_telegram
    ON access_requests (telegram_id, created_at DESC);
`);

const insertRequest = db.prepare(`
  INSERT INTO access_requests (telegram_id, telegram_username, github_username)
  VALUES (@telegramId, @telegramUsername, @githubUsername)
  ON CONFLICT(telegram_id, github_username) DO UPDATE SET
    status = CASE
      WHEN access_requests.status IN ('rejected', 'cancelled') THEN 'pending'
      ELSE access_requests.status
    END
  RETURNING *
`);

module.exports = {
  createRequest(data) {
    return insertRequest.get(data);
  },
  getRequest(id) {
    return db.prepare('SELECT * FROM access_requests WHERE id = ?').get(id);
  },
  getLatestForTelegram(telegramId) {
    return db.prepare(
      'SELECT * FROM access_requests WHERE telegram_id = ? ORDER BY id DESC LIMIT 1'
    ).get(String(telegramId));
  },
  listPending(limit = 10) {
    return db.prepare(
      "SELECT * FROM access_requests WHERE status = 'pending' ORDER BY id ASC LIMIT ?"
    ).all(limit);
  },
  setStatus(id, status, reviewer, invitationSent = false) {
    const now = new Date().toISOString();
    return db.prepare(`
      UPDATE access_requests
      SET status = ?, reviewed_at = ?, reviewed_by = ?,
          github_invitation_sent_at = CASE WHEN ? THEN ? ELSE github_invitation_sent_at END
      WHERE id = ?
    `).run(status, now, String(reviewer), invitationSent ? 1 : 0, now, id);
  },
  close() {
    db.close();
  }
};
