from __future__ import annotations
import sqlite3, json
from pathlib import Path
from datetime import datetime, timezone

SCHEMA='''
CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, status TEXT NOT NULL, state_json TEXT, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents (document_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, filename TEXT NOT NULL, format TEXT NOT NULL, source_path TEXT, size_bytes INTEGER, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS raw_texts (document_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, method TEXT NOT NULL, pages INTEGER, characters_extracted INTEGER, text TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS policies (policy_id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT, run_id TEXT, policy_json TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS comparisons (comparison_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, comparison_json TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS reports (report_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, report_text TEXT, created_at TEXT);
'''
class Database:
    def __init__(self,path='data/insurminds_protetor.db'):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.init()
    def connect(self): return sqlite3.connect(self.path)
    def init(self):
        with self.connect() as c: c.executescript(SCHEMA)
    def save_run(self,state):
        now=datetime.now(timezone.utc).isoformat(); payload=state.model_dump_json()
        with self.connect() as c: c.execute('INSERT OR REPLACE INTO runs VALUES (?,?,?,?)',(state.run_id,state.status.value,payload,now))
    def save_document(self,run_id,d):
        now=datetime.now(timezone.utc).isoformat()
        with self.connect() as c: c.execute('INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?,?,?)',(d['document_id'],run_id,d['filename'],d['format'],d['source_path'],d['size_bytes'],d['status'],now))
    def save_raw_text(self,run_id,e):
        now=datetime.now(timezone.utc).isoformat()
        with self.connect() as c: c.execute('INSERT OR REPLACE INTO raw_texts VALUES (?,?,?,?,?,?,?)',(e['document_id'],run_id,e['method'],e['pages'],e['characters_extracted'],e['text'],now))
    def get_raw_text(self,document_id):
        with self.connect() as c:
            row=c.execute('SELECT text FROM raw_texts WHERE document_id=?',(document_id,)).fetchone()
        return row[0] if row else None
    def save_policy(self,run_id,policy):
        now=datetime.now(timezone.utc).isoformat(); payload=policy.model_dump_json()
        with self.connect() as c: c.execute('INSERT INTO policies (document_id,run_id,policy_json,created_at) VALUES (?,?,?,?)',(policy.document_id,run_id,payload,now))
    def get_latest_policy(self,document_id):
        with self.connect() as c:
            row=c.execute('SELECT policy_json FROM policies WHERE document_id=? ORDER BY policy_id DESC LIMIT 1',(document_id,)).fetchone()
        return json.loads(row[0]) if row else None


    def save_comparison(self,run_id,comparison):
        now=datetime.now(timezone.utc).isoformat(); payload=comparison.model_dump_json()
        with self.connect() as c: c.execute('INSERT INTO comparisons (run_id,comparison_json,created_at) VALUES (?,?,?)',(run_id,payload,now))
    def get_latest_comparison(self,run_id):
        with self.connect() as c:
            row=c.execute('SELECT comparison_json FROM comparisons WHERE run_id=? ORDER BY comparison_id DESC LIMIT 1',(run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_report(self,run_id,report_text):
        now=datetime.now(timezone.utc).isoformat()
        with self.connect() as c:
            c.execute('INSERT INTO reports (run_id,report_text,created_at) VALUES (?,?,?)',(run_id,report_text,now))

    def get_latest_report(self,run_id):
        with self.connect() as c:
            row=c.execute('SELECT report_text FROM reports WHERE run_id=? ORDER BY report_id DESC LIMIT 1',(run_id,)).fetchone()
        return row[0] if row else None

    def list_policies(self):
        """(document_id, run_id, policy_json, created_at) for every stored policy, newest first."""
        with self.connect() as c:
            return c.execute('SELECT document_id, run_id, policy_json, created_at FROM policies ORDER BY policy_id DESC').fetchall()
