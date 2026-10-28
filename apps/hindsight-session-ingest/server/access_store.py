"""Accounts, bank grants, API tokens, console sessions and the auth switch (SQLite, 0600).

Secrets are never stored: passwords use scrypt, tokens and session ids are SHA-256 hashed.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3
import time

LEVELS = {"read": 1, "write": 2, "manage": 3}
ROLES = ("admin", "user")
USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,47}$")
BANK = re.compile(r"^[^\s/\\?#]{1,200}$")
SESSION_SECONDS = 12 * 3600
TOKEN_PREFIX = "hs_"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$" + salt.hex() + "$" + key.hex()


def check_password(password, stored):
    try:
        _, salt, key = stored.split("$")
        return hmac.compare_digest(hash_password(password, bytes.fromhex(salt)).split("$")[2], key)
    except (ValueError, AttributeError):
        return False


def valid_password(password):
    if not isinstance(password, str) or len(password) < 10:
        raise ValueError("密码至少 10 位")
    return password


class AccessStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
                role TEXT NOT NULL, disabled INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
                created REAL NOT NULL, last_login REAL);
            CREATE TABLE IF NOT EXISTS grants (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                bank_id TEXT NOT NULL, permission TEXT NOT NULL, created REAL NOT NULL,
                PRIMARY KEY (user_id, bank_id));
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL, hash TEXT UNIQUE NOT NULL, prefix TEXT NOT NULL, cap TEXT,
                created REAL NOT NULL, expires REAL, last_used REAL, revoked REAL);
            CREATE TABLE IF NOT EXISTS sessions (
                hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                csrf TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY, time REAL NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
                target TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '');
            """)
            db.execute("INSERT OR IGNORE INTO settings VALUES ('auth_enabled', '1')")
        finally:
            db.close()
        self.path.chmod(0o600)
        self._switch = (0.0, True)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    # ---- switch -------------------------------------------------------------------------
    def auth_enabled(self):
        checked, value = self._switch
        if time.monotonic() - checked > 2:
            with self.connect() as db:
                value = db.execute("SELECT value FROM settings WHERE key='auth_enabled'").fetchone()[0] == "1"
            self._switch = (time.monotonic(), value)
        return value

    def set_auth_enabled(self, actor, enabled):
        with self.connect() as db:
            db.execute("UPDATE settings SET value=? WHERE key='auth_enabled'", ("1" if enabled else "0",))
        self._switch = (0.0, enabled)
        self.log(actor, "auth_switch", "api", "on" if enabled else "off")

    # ---- audit --------------------------------------------------------------------------
    def log(self, actor, action, target="", detail=""):
        with self.connect() as db:
            db.execute("INSERT INTO audit (time, actor, action, target, detail) VALUES (?,?,?,?,?)",
                       (time.time(), actor, action, str(target), str(detail)[:500]))

    def audit(self, limit=200):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,))]

    # ---- users --------------------------------------------------------------------------
    @staticmethod
    def public_user(row):
        return {key: row[key] for key in ("id", "username", "role", "disabled", "note", "created", "last_login")}

    def create_user(self, actor, username, password, role="user", note=""):
        if not USERNAME.match(username or ""):
            raise ValueError("用户名需为 2-48 位字母、数字、点、下划线或连字符")
        if role not in ROLES:
            raise ValueError("未知角色")
        valid_password(password)
        try:
            with self.connect() as db:
                cursor = db.execute("INSERT INTO users (username, password, role, note, created) VALUES (?,?,?,?,?)",
                                    (username, hash_password(password), role, note[:200], time.time()))
        except sqlite3.IntegrityError as error:
            raise ValueError("用户名已存在") from error
        self.log(actor, "user_create", username, role)
        return self.user(cursor.lastrowid)

    def user(self, user_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return self.public_user(row) if row else None

    def users(self):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM users ORDER BY role, username").fetchall()
            counts = {row["user_id"]: row["n"] for row in db.execute(
                "SELECT user_id, count(*) n FROM tokens WHERE revoked IS NULL GROUP BY user_id")}
        return [dict(self.public_user(row), active_tokens=counts.get(row["id"], 0),
                     grants=self.grants(row["id"])) for row in rows]

    def admins_left(self, db, excluding):
        return db.execute("SELECT count(*) FROM users WHERE role='admin' AND disabled=0 AND id<>?",
                          (excluding,)).fetchone()[0]

    def update_user(self, actor, user_id, *, role=None, disabled=None, note=None, password=None):
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if row is None:
                raise KeyError(user_id)
            demoting = (role is not None and role != "admin") or disabled
            if row["role"] == "admin" and demoting and not self.admins_left(db, user_id):
                raise ValueError("至少需要保留一个可用的管理员")
            if role is not None:
                if role not in ROLES:
                    raise ValueError("未知角色")
                db.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
            if disabled is not None:
                db.execute("UPDATE users SET disabled=? WHERE id=?", (int(bool(disabled)), user_id))
                if disabled:
                    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            if note is not None:
                db.execute("UPDATE users SET note=? WHERE id=?", (note[:200], user_id))
            if password is not None:
                db.execute("UPDATE users SET password=? WHERE id=?", (hash_password(valid_password(password)), user_id))
                db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        changes = {k: v for k, v in (("role", role), ("disabled", disabled), ("note", note)) if v is not None}
        if password is not None:
            changes["password"] = "reset"
        self.log(actor, "user_update", row["username"], json.dumps(changes, ensure_ascii=False))
        return self.user(user_id)

    def delete_user(self, actor, user_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if row is None:
                raise KeyError(user_id)
            if row["role"] == "admin" and not self.admins_left(db, user_id):
                raise ValueError("至少需要保留一个可用的管理员")
            db.execute("DELETE FROM users WHERE id=?", (user_id,))
        self.log(actor, "user_delete", row["username"])

    # ---- grants -------------------------------------------------------------------------
    def grants(self, user_id):
        with self.connect() as db:
            rows = db.execute("SELECT bank_id, permission, created FROM grants WHERE user_id=? ORDER BY bank_id",
                              (user_id,)).fetchall()
        return [dict(row) for row in rows]

    def set_grant(self, actor, user_id, bank_id, permission):
        if permission not in LEVELS:
            raise ValueError("权限必须是 read、write 或 manage")
        if not BANK.match(bank_id or ""):
            raise ValueError("无效的数据仓 ID")
        user = self.user(user_id)
        if user is None:
            raise KeyError(user_id)
        with self.connect() as db:
            db.execute("INSERT INTO grants VALUES (?,?,?,?) ON CONFLICT(user_id, bank_id) DO UPDATE SET permission=excluded.permission",
                       (user_id, bank_id, permission, time.time()))
        self.log(actor, "grant_set", user["username"], bank_id + ":" + permission)

    def remove_grant(self, actor, user_id, bank_id):
        user = self.user(user_id)
        with self.connect() as db:
            db.execute("DELETE FROM grants WHERE user_id=? AND bank_id=?", (user_id, bank_id))
        self.log(actor, "grant_remove", user["username"] if user else user_id, bank_id)

    # ---- tokens -------------------------------------------------------------------------
    def issue_token(self, actor, user_id, name, days=None, cap=None):
        """Return the plaintext token once; only its hash is kept."""
        user = self.user(user_id)
        if user is None:
            raise KeyError(user_id)
        if cap not in (None, "", *LEVELS):
            raise ValueError("权限上限必须是 read、write 或 manage")
        name = (name or "").strip()[:80] or "token"
        token = TOKEN_PREFIX + secrets.token_urlsafe(32)
        expires = time.time() + float(days) * 86400 if days else None
        with self.connect() as db:
            cursor = db.execute("""INSERT INTO tokens (user_id, name, hash, prefix, cap, created, expires)
                VALUES (?,?,?,?,?,?,?)""", (user_id, name, digest(token), token[:10], cap or None, time.time(), expires))
        self.log(actor, "token_issue", user["username"], name)
        return {"id": cursor.lastrowid, "token": token, "name": name, "expires": expires, "cap": cap or None}

    def tokens(self, user_id=None):
        query = """SELECT t.id, t.user_id, u.username, t.name, t.prefix, t.cap, t.created, t.expires,
                   t.last_used, t.revoked FROM tokens t JOIN users u ON u.id=t.user_id"""
        args = ()
        if user_id is not None:
            query, args = query + " WHERE t.user_id=?", (user_id,)
        with self.connect() as db:
            return [dict(row) for row in db.execute(query + " ORDER BY t.created DESC", args)]

    def revoke_token(self, actor, token_id, user_id=None):
        with self.connect() as db:
            query, args = "UPDATE tokens SET revoked=? WHERE id=? AND revoked IS NULL", [time.time(), token_id]
            if user_id is not None:
                query, args = query + " AND user_id=?", args + [user_id]
            cursor = db.execute(query, args)
        if cursor.rowcount != 1:
            raise KeyError(token_id)
        self.log(actor, "token_revoke", str(token_id))

    def principal_for_token(self, token):
        """Resolve a bearer token to an access principal, or None."""
        if not token or not token.startswith(TOKEN_PREFIX):
            return None
        now = time.time()
        with self.connect() as db:
            row = db.execute("""SELECT t.id token_id, t.cap, t.expires, t.revoked, t.last_used, u.* FROM tokens t
                JOIN users u ON u.id=t.user_id WHERE t.hash=?""", (digest(token),)).fetchone()
            if row is None or row["revoked"] or row["disabled"] or (row["expires"] and row["expires"] < now):
                return None
            if not row["last_used"] or now - row["last_used"] > 60:
                db.execute("UPDATE tokens SET last_used=? WHERE id=?", (now, row["token_id"]))
        return self.principal(row, cap=row["cap"], via="token:" + str(row["token_id"]))

    def principal(self, row, cap=None, via="session"):
        return Principal(user_id=row["id"], username=row["username"], role=row["role"],
                         grants={g["bank_id"]: g["permission"] for g in self.grants(row["id"])}, cap=cap, via=via)

    # ---- sessions -----------------------------------------------------------------------
    def login(self, username, password):
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (username or "",)).fetchone()
        stored = row["password"] if row else hash_password("decoy-password")
        if not check_password(password or "", stored) or row is None or row["disabled"]:
            self.log(username or "?", "login_failed")
            return None
        session, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        now = time.time()
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires<?", (now,))
            db.execute("INSERT INTO sessions VALUES (?,?,?,?,?)", (digest(session), row["id"], csrf, now, now + SESSION_SECONDS))
            db.execute("UPDATE users SET last_login=? WHERE id=?", (now, row["id"]))
        self.log(row["username"], "login")
        return session

    def session(self, session):
        """Return (principal, csrf) for a live console session, or (None, None)."""
        if not session:
            return None, None
        with self.connect() as db:
            row = db.execute("""SELECT s.csrf, s.expires, u.* FROM sessions s JOIN users u ON u.id=s.user_id
                WHERE s.hash=?""", (digest(session),)).fetchone()
        if row is None or row["disabled"] or row["expires"] < time.time():
            return None, None
        return self.principal(row), row["csrf"]

    def logout(self, session):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE hash=?", (digest(session or ""),))

    def verify_password(self, user_id, password):
        with self.connect() as db:
            row = db.execute("SELECT password FROM users WHERE id=?", (user_id,)).fetchone()
        return bool(row) and check_password(password, row["password"])

    def bootstrap_admin(self, password_file):
        """Create the first administrator with a random password written to a 0600 file."""
        with self.connect() as db:
            if db.execute("SELECT 1 FROM users WHERE role='admin' LIMIT 1").fetchone():
                return None
        password = secrets.token_urlsafe(15)
        self.create_user("system", "admin", password, "admin", "初始管理员")
        path = Path(password_file)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text("username: admin\npassword: " + password + "\n")
        path.chmod(0o600)
        return path


class Principal:
    """Who is calling and what they may touch. Admins see every bank."""

    def __init__(self, user_id, username, role, grants, cap=None, via="session"):
        self.user_id, self.username, self.role, self.grants, self.cap, self.via = user_id, username, role, grants, cap, via

    @property
    def is_admin(self):
        return self.role == "admin"

    def level(self, bank_id):
        level = LEVELS["manage"] if self.is_admin else LEVELS.get(self.grants.get(bank_id), 0)
        return min(level, LEVELS[self.cap]) if self.cap else level

    def allows(self, bank_id, needed):
        return self.level(bank_id) >= LEVELS[needed]

    def admin_allows(self, needed="manage"):
        """Non-bank operations (multi-bank MCP, metrics) are for administrators only."""
        return self.is_admin and (not self.cap or LEVELS[self.cap] >= LEVELS[needed])

    def visible(self, bank_id):
        return self.level(bank_id) >= LEVELS["read"]
