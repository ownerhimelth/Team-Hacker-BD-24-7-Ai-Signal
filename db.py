import sqlite3, os
from datetime import datetime, timedelta, timezone

class Database:
    def __init__(self, path="data/bot.sqlite3"):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with self.conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, banned INTEGER DEFAULT 0, live INTEGER DEFAULT 0, cooldown_until TEXT, session_wins INTEGER DEFAULT 0, entry_level INTEGER DEFAULT 1, last_source_issue TEXT);
            CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS signals(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, source_issue TEXT, target_period TEXT, side TEXT, numbers TEXT, level INTEGER, result TEXT DEFAULT 'PENDING', result_number INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP, resolved_at TEXT);
            """)
    def conn(self): return sqlite3.connect(self.path, timeout=30)
    def add_user(self, uid):
        with self.conn() as c: c.execute("INSERT OR IGNORE INTO users(id) VALUES(?)", (uid,))
    def users(self):
        with self.conn() as c: return [r[0] for r in c.execute("SELECT id FROM users")]
    def is_banned(self, uid):
        with self.conn() as c:
            r=c.execute("SELECT banned FROM users WHERE id=?", (uid,)).fetchone()
            return bool(r and r[0])
    def set_banned(self, uid, val):
        self.add_user(uid)
        with self.conn() as c: c.execute("UPDATE users SET banned=? WHERE id=?", (int(val),uid))
    def add_admin(self, uid):
        with self.conn() as c: c.execute("INSERT OR IGNORE INTO admins(id) VALUES(?)",(uid,))
    def is_admin(self, uid):
        with self.conn() as c: return c.execute("SELECT 1 FROM admins WHERE id=?",(uid,)).fetchone() is not None
    def set_setting(self, key, value):
        with self.conn() as c: c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,str(value)))
    def get_setting(self, key, default=""):
        with self.conn() as c:
            r=c.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
            return r[0] if r else default
    def is_live(self, uid):
        with self.conn() as c:
            r=c.execute("SELECT live FROM users WHERE id=?",(uid,)).fetchone()
            return bool(r and r[0])
    def live_users(self):
        with self.conn() as c: return [r[0] for r in c.execute("SELECT id FROM users WHERE live=1")]
    def can_start(self, uid):
        self.add_user(uid)
        with self.conn() as c:
            r=c.execute("SELECT cooldown_until FROM users WHERE id=?",(uid,)).fetchone()
        if r and r[0]:
            until=datetime.fromisoformat(r[0])
            now=datetime.now(timezone.utc)
            if now < until:
                mins=max(1,int((until-now).total_seconds()/60)+1)
                return False, mins
        return True, 0
    def start_session(self, uid):
        self.add_user(uid)
        with self.conn() as c:
            c.execute("UPDATE users SET live=1, session_wins=0, entry_level=1, cooldown_until=NULL, last_source_issue=NULL WHERE id=?",(uid,))
            c.execute("DELETE FROM signals WHERE user_id=? AND result='PENDING'",(uid,))
    def stop_live(self, uid, cooldown=False):
        until=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat() if cooldown else None
        with self.conn() as c: c.execute("UPDATE users SET live=0, cooldown_until=COALESCE(?,cooldown_until) WHERE id=?",(until,uid))
    def entry_level(self, uid):
        with self.conn() as c:
            r=c.execute("SELECT entry_level FROM users WHERE id=?",(uid,)).fetchone()
            return r[0] if r else 1
    def last_signal_source(self, uid):
        with self.conn() as c:
            r=c.execute("SELECT source_issue FROM signals WHERE user_id=? ORDER BY id DESC LIMIT 1",(uid,)).fetchone()
            return r[0] if r else None
    def create_signal(self, uid, source, target, side, numbers, level):
        with self.conn() as c:
            c.execute("INSERT INTO signals(user_id,source_issue,target_period,side,numbers,level) VALUES(?,?,?,?,?,?)",
                      (uid,source,target,side,",".join(map(str,numbers)),level))
            c.execute("UPDATE users SET last_source_issue=? WHERE id=?",(source,uid))
    def pending_signal(self, uid):
        with self.conn() as c:
            r=c.execute("SELECT id,target_period,side,numbers,level FROM signals WHERE user_id=? AND result='PENDING' ORDER BY id DESC LIMIT 1",(uid,)).fetchone()
        if not r: return None
        return {"id":r[0],"target_period":r[1],"side":r[2],"numbers":[int(x) for x in r[3].split(",")],"level":r[4]}
    def resolve_signal(self, uid, result_number, result_side):
        pending=self.pending_signal(uid)
        if not pending: return "LOSS"
        if result_side != pending["side"]:
            status="LOSS"
        elif result_number in pending["numbers"]:
            status="JACKPOT"
        else:
            status="WIN"
        with self.conn() as c:
            c.execute("UPDATE signals SET result=?,result_number=?,resolved_at=CURRENT_TIMESTAMP WHERE id=?",
                      (status,result_number,pending["id"]))
            if status in ("WIN","JACKPOT"):
                c.execute("UPDATE users SET session_wins=session_wins+1,entry_level=1 WHERE id=?",(uid,))
            else:
                c.execute("UPDATE users SET entry_level=entry_level+1 WHERE id=?",(uid,))
        return status
    def session_wins(self, uid):
        with self.conn() as c:
            r=c.execute("SELECT session_wins FROM users WHERE id=?",(uid,)).fetchone()
            return r[0] if r else 0
    def signal_values(self, uid, result_row, status):
        pending=self.pending_signal(uid)
        # pending has already been resolved, so fetch latest completed signal
        with self.conn() as c:
            r=c.execute("SELECT target_period,side,numbers,level FROM signals WHERE user_id=? ORDER BY id DESC LIMIT 1",(uid,)).fetchone()
        side, nums, level = r[1], [int(x) for x in r[2].split(",")], r[3]
        n=int(result_row["number"])
        return {"brand":self.get_setting("brand","𝐓𝐄𝐀𝐌 𝐇𝐀𝐂𝐊𝐄𝐑 𝐁𝐃 𝐀𝐈 𝐒𝐈𝐆𝐍𝐀𝐋🤩"),
                "market":"⏰𝐖𝐈𝐍 𝐆𝐨 𝟏 𝐌𝐢𝐧⏰","period":r[0],
                "entry":f"{side} {nums[0]}•{nums[1]}",
                "result":f"{'Big' if n>=5 else 'Small'} {n}",
                "status":{"WIN":"𝐖𝐈𝐍","LOSS":"𝐋𝐨𝐬𝐬","JACKPOT":"𝐍𝐮𝐦𝐛𝐞𝐫 𝐉𝐚𝐜𝐤𝐩𝐨𝐭"}[status],"level":level}
    def make_report(self, uid):
        with self.conn() as c:
            rows=c.execute("SELECT target_period,side,numbers,result,result_number FROM signals WHERE user_id=? AND result!='PENDING' ORDER BY id DESC LIMIT 4",(uid,)).fetchall()
            totals=c.execute("SELECT COUNT(*),SUM(result IN ('WIN','JACKPOT')),SUM(result='LOSS'),SUM(result='JACKPOT') FROM signals WHERE user_id=?",(uid,)).fetchone()
        lines=["📊 𝐓𝐎𝐓𝐀𝐋 𝐒𝐈𝐆𝐍𝐀𝐋 𝐑𝐄𝐏𝐎𝐑𝐓",f"Total Signals: {totals[0] or 0}",f"Total WIN: {totals[1] or 0}",f"Total LOSS: {totals[2] or 0}",f"Number Jackpot: {totals[3] or 0}","", "Last 4 Periods:"]
        for p,side,nums,res,n in rows:
            lines.append(f"{p} | {side} {nums.replace(',', '•')} | Result {n} | {res}")
        return "\n".join(lines)
    def stats(self):
        with self.conn() as c:
            users=c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            signals=c.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
            wins=c.execute("SELECT COUNT(*) FROM signals WHERE result IN ('WIN','JACKPOT')").fetchone()[0]
            losses=c.execute("SELECT COUNT(*) FROM signals WHERE result='LOSS'").fetchone()[0]
            jackpots=c.execute("SELECT COUNT(*) FROM signals WHERE result='JACKPOT'").fetchone()[0]
            live=c.execute("SELECT COUNT(*) FROM users WHERE live=1").fetchone()[0]
        return dict(users=users,signals=signals,wins=wins,losses=losses,jackpots=jackpots,live=live)

DB=Database(os.getenv("DB_PATH","data/bot.sqlite3"))
