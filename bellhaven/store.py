"""Durable decisions and write checkpoints; SQLite lives outside source control."""
import json
import sqlite3
from pathlib import Path
from .source import now


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'review.sqlite3'
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY, state TEXT NOT NULL, payload TEXT NOT NULL,
                    actor TEXT, reason TEXT, decided_at TEXT, result TEXT,
                    phase TEXT, created_id TEXT, error TEXT
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY, at TEXT NOT NULL, summary TEXT NOT NULL,
                    snapshot TEXT NOT NULL, accounts TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, at TEXT NOT NULL, proposal_id TEXT,
                    action TEXT NOT NULL, detail TEXT NOT NULL
                );
            ''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def event(self, proposal_id, action, detail):
        with self.connect() as db:
            db.execute('INSERT INTO events(at,proposal_id,action,detail) VALUES(?,?,?,?)',
                       (now(), proposal_id, action, json.dumps(detail)))

    def save_run(self, snapshot, accounts, result):
        added = 0
        with self.connect() as db:
            # A failed preflight with no write intent can be replaced by a fresh
            # review. Interrupted remote writes retain their recovery checkpoints.
            db.execute("UPDATE proposals SET state='superseded' WHERE state='pending' OR (state='failed' AND phase IS NULL)")
            for p in result['proposals']:
                row = db.execute('SELECT state FROM proposals WHERE id=?', (p['id'],)).fetchone()
                if not row:
                    db.execute('INSERT INTO proposals(id,state,payload) VALUES(?,?,?)',
                               (p['id'],'pending',json.dumps(p)))
                    added += 1
                elif row['state'] in ('pending','superseded'):
                    db.execute("UPDATE proposals SET state='pending',payload=?,error=NULL,actor=NULL,reason=NULL,decided_at=NULL,result=NULL WHERE id=?",
                               (json.dumps(p),p['id']))
            summary = dict(at=snapshot['at'], website_count=len(snapshot['locations']),
                           crm_count=len(accounts), directory_count=snapshot['directory_count'],
                           pages=len(snapshot['pages']), added=added, matches=result['matches'],
                           parent_id=result['parent_id'])
            db.execute('INSERT INTO runs(at,summary,snapshot,accounts) VALUES(?,?,?,?)',
                       (now(),json.dumps(summary),json.dumps(snapshot),json.dumps(accounts)))
        self.event(None,'scan_completed',summary)
        return summary

    def latest(self):
        with self.connect() as db:
            row = db.execute('SELECT summary FROM runs ORDER BY id DESC LIMIT 1').fetchone()
        return json.loads(row['summary']) if row else None

    @staticmethod
    def decode(row):
        if not row:
            return None
        row = dict(row)
        row['payload'] = json.loads(row['payload'])
        if row['result']:
            row['result'] = json.loads(row['result'])
        return row

    def all(self):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM proposals ORDER BY rowid').fetchall()
        return [self.decode(row) for row in rows]

    def get(self, proposal_id):
        with self.connect() as db:
            return self.decode(db.execute('SELECT * FROM proposals WHERE id=?', (proposal_id,)).fetchone())

    def update(self, proposal_id, **fields):
        allowed = {'state','actor','reason','decided_at','result','phase','created_id','error'}
        if not fields or set(fields) - allowed:
            raise ValueError('Invalid ledger fields')
        if isinstance(fields.get('result'), dict):
            fields['result'] = json.dumps(fields['result'])
        with self.connect() as db:
            db.execute('UPDATE proposals SET ' + ','.join(k+'=?' for k in fields) + ' WHERE id=?',
                       (*fields.values(),proposal_id))
