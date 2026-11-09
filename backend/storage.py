"""Per-project SQLite persistence and content-addressed local ROM artifacts."""
from __future__ import annotations
import hashlib, json, os, re, sqlite3, threading, uuid
from pathlib import Path

ROOT=Path(os.environ.get('UMK3_STUDIO_HOME',str(Path.home()/'.umk3-re-studio')))
_LOCK=threading.RLock()

def safe_name(name):
    name=re.sub(r'[^\w. -]','_',name,flags=re.UNICODE).strip(' .')
    return name[:100] or 'Projeto'

class Store:
    def __init__(self,root=None):
        self.root=Path(root) if root else ROOT
        self.root.mkdir(parents=True,exist_ok=True)
        self.artifacts=self.root/'artifacts';self.artifacts.mkdir(exist_ok=True)
        self.db=self.root/'studio.sqlite3'
        with self.connection() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    rom_sha TEXT, comparison_sha TEXT, cdl_sha TEXT);
                CREATE TABLE IF NOT EXISTS artifacts(sha TEXT PRIMARY KEY, size INTEGER NOT NULL, filename TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS symbols(id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
                    memtype TEXT NOT NULL, address INTEGER NOT NULL, label TEXT NOT NULL, comment TEXT DEFAULT '',
                    confidence TEXT DEFAULT 'unknown', provenance TEXT DEFAULT 'manual',
                    UNIQUE(project_id,memtype,address,label), FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
                    char_id INTEGER NOT NULL, name TEXT NOT NULL, address INTEGER NOT NULL, value INTEGER NOT NULL,
                    source TEXT NOT NULL, evidence TEXT NOT NULL DEFAULT 'dump', confidence TEXT NOT NULL DEFAULT 'observed',
                    UNIQUE(project_id,char_id,address,source));
                CREATE INDEX IF NOT EXISTS idx_symbols_project ON symbols(project_id);
                CREATE INDEX IF NOT EXISTS idx_obs_project ON observations(project_id);
            ''')
    def connection(self):
        conn=sqlite3.connect(self.db,timeout=15)
        conn.row_factory=sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn
    def projects(self):
        with _LOCK,self.connection() as c:return [dict(x) for x in c.execute('SELECT * FROM projects ORDER BY created_at DESC,id')]
    def create(self,name):
        pid=uuid.uuid4().hex[:12]
        with _LOCK,self.connection() as c:c.execute('INSERT INTO projects(id,name) VALUES(?,?)',(pid,safe_name(name)))
        return self.get(pid)
    def get(self,pid):
        with self.connection() as c:
            row=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
            return dict(row) if row else None
    def save_artifact(self,pid,field,raw,filename):
        if field not in ('rom_sha','comparison_sha','cdl_sha'):raise ValueError('Invalid artifact slot')
        if not self.get(pid):raise KeyError(pid)
        sha=hashlib.sha256(raw).hexdigest(); target=self.artifacts/sha
        if not target.exists():
            tmp=self.artifacts/(sha+'.tmp'+uuid.uuid4().hex)
            tmp.write_bytes(raw);tmp.replace(target)
        with _LOCK,self.connection() as c:
            c.execute('INSERT OR IGNORE INTO artifacts(sha,size,filename) VALUES(?,?,?)',(sha,len(raw),safe_name(filename)))
            c.execute(f'UPDATE projects SET {field}=? WHERE id=?',(sha,pid))
        return sha
    def load_artifact(self,sha):
        if not sha or not re.fullmatch(r'[a-f0-9]{64}',sha):return None
        p=self.artifacts/sha
        return p.read_bytes() if p.exists() else None
    def symbols(self,pid,q='',limit=500):
        with self.connection() as c:
            rows=c.execute('SELECT id,memtype AS type,address,label,comment,confidence,provenance FROM symbols WHERE project_id=? AND (label LIKE ? OR printf("%X",address) LIKE ?) ORDER BY address,id LIMIT ?', (pid,'%'+q+'%','%'+q.upper()+'%',min(max(1,limit),2000))).fetchall()
            return [dict(x) for x in rows]
    def add_symbol(self,pid,memtype,address,label,comment='',confidence='unknown',provenance='manual'):
        if not self.get(pid):raise KeyError(pid)
        with _LOCK,self.connection() as c:
            c.execute('INSERT OR IGNORE INTO symbols(project_id,memtype,address,label,comment,confidence,provenance) VALUES(?,?,?,?,?,?,?)', (pid,memtype,address,label,comment,confidence,provenance))
        return {'type':memtype,'address':address,'label':label,'comment':comment,'confidence':confidence,'provenance':provenance}
    def replace_imported_symbols(self,pid,symbols):
        with _LOCK,self.connection() as c:
            for s in symbols:
                c.execute('INSERT OR IGNORE INTO symbols(project_id,memtype,address,label,comment,confidence,provenance) VALUES(?,?,?,?,?,?,?)',(pid,s['type'],s['address'],s['label'],s.get('comment',''),'known-hardware' if s['type'] in ('SnesRegister','SpcRam') else 'unknown','mlb-import'))
    def observations(self,pid):
        with self.connection() as c:return [dict(x) for x in c.execute('SELECT char_id,name,address,value,source,evidence,confidence FROM observations WHERE project_id=? ORDER BY char_id,address',(pid,))]
    def observe(self,pid,char_id,name,address,value,source,evidence='dump',confidence='observed'):
        with _LOCK,self.connection() as c:
            c.execute('INSERT OR REPLACE INTO observations(project_id,char_id,name,address,value,source,evidence,confidence) VALUES(?,?,?,?,?,?,?,?)',(pid,char_id,name,address,value,source,evidence,confidence))
