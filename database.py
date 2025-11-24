import os
import sqlite3
import threading
import time
import queue
from contextlib import contextmanager
from typing import Optional, Tuple, Any, Dict

# Optional encryption
try:
    from cryptography.fernet import Fernet, InvalidToken
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False

DB_PATH_DEFAULT = "flood_app.db"
POOL_SIZE = 4  # small pool, sufficient for light desktop/mobile use

# Read encryption key from environment (base64 urlsafe key for Fernet)
_ENC_KEY = os.getenv("DB_ENCRYPTION_KEY", None)
if _ENC_KEY and not _HAS_CRYPTO:
    # cryptography missing; prefer library installation
    print("[WARN] DB_ENCRYPTION_KEY provided but 'cryptography' package is not installed. Install 'cryptography' to enable encryption.")
if _HAS_CRYPTO and _ENC_KEY:
    _FERNET = Fernet(_ENC_KEY.encode() if isinstance(_ENC_KEY, str) else _ENC_KEY)
else:
    _FERNET = None

_lock = threading.Lock()


class Database:
    def __init__(self, path: str = DB_PATH_DEFAULT, pool_size: int = POOL_SIZE):
        self.path = path
        self.pool_size = pool_size
        self._conn_pool = queue.Queue(maxsize=pool_size)
        # Pre-create connections
        for _ in range(pool_size):
            self._conn_pool.put(self._make_conn())
        # Ensure schema present
        self._init_schema()

    def _make_conn(self):
        conn = sqlite3.connect(
            self.path,
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
            timeout=30  # <--- ✅ wait up to 30s before throwing "database locked"
        )
        conn.row_factory = sqlite3.Row

        # Foreign keys and WAL for concurrency
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")   # ✅ improves write performance while safe
        conn.execute("PRAGMA busy_timeout = 30000;")   # ✅ this is the key fix (30 seconds wait)

        return conn


    @contextmanager
    def get_conn(self):
        """Context manager to get a connection from the pool safely."""
        conn = None
        try:
            conn = self._conn_pool.get(timeout=5)
        except Exception:
            # fallback: create a temporary connection
            conn = self._make_conn()
        try:
            yield conn
            # commit only if not in a manual transaction
            try:
                conn.commit()
            except Exception:
                pass
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            # Return to pool if applicable
            try:
                if conn and self._conn_pool.full() is False:
                    self._conn_pool.put(conn)
                else:
                    # close extra connection if pool already full
                    if conn:
                        conn.close()
            except Exception:
                pass

    # -----------------------
    # Schema initialization
    # -----------------------
    def _init_schema(self):
        with self.get_conn() as conn:
            cur = conn.cursor()
            # Users table stores salted hash, salt, failed attempts & lock timestamp
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    full_name TEXT,
                    failed_attempts INTEGER DEFAULT 0,
                    lock_until REAL DEFAULT 0,
                    created_at REAL NOT NULL
                );
                """
            )
            # Audit trail for security & data changes
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_trail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    event_type TEXT NOT NULL,
                    event_data TEXT,
                    created_at REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
                );
                """
            )
            # Generic application data (can store encrypted blobs)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value BLOB,
                    encrypted INTEGER DEFAULT 0,
                    updated_at REAL NOT NULL
                );
                """
            )
            conn.commit()

    # -----------------------
    # Encryption helpers
    # -----------------------
    def _encrypt(self, plaintext: str) -> Tuple[bytes, int]:
        """Return (ciphertext, encrypted_flag). If encryption not enabled, return plaintext bytes and 0."""
        if _FERNET:
            token = _FERNET.encrypt(plaintext.encode("utf-8"))
            return token, 1
        else:
            return plaintext.encode("utf-8"), 0

    def _decrypt(self, ciphertext: bytes, encrypted_flag: int) -> str:
        """Decrypt if encrypted_flag==1 and cryptography available."""
        if encrypted_flag and _FERNET:
            try:
                return _FERNET.decrypt(ciphertext).decode("utf-8")
            except Exception as e:
                raise RuntimeError("Decryption failed") from e
        else:
            # assume stored as UTF-8 bytes
            return ciphertext.decode("utf-8") if isinstance(ciphertext, (bytes, bytearray)) else str(ciphertext)

    # -----------------------
    # User CRUD & auth helpers
    # -----------------------
    def create_user(self, username: str, password_hash: str, salt: str, full_name: Optional[str] = None) -> int:
        """Insert a new user and write an audit entry in the SAME transaction (prevents DB lock)."""
        ts = time.time()
        with self.get_conn() as conn:
            cur = conn.cursor()
            try:
                # Insert user
                cur.execute(
                    "INSERT INTO users (username, password_hash, salt, full_name, created_at) VALUES (?, ?, ?, ?, ?)",
                    (username, password_hash, salt, full_name, ts),
                )
                uid = cur.lastrowid

                # ✅ Audit insert in same transaction (no nested get_conn call)
                cur.execute(
                    "INSERT INTO audit_trail (user_id, event_type, event_data, created_at) VALUES (?, ?, ?, ?)",
                    (uid, "user_registered", f"username={username}", ts),
                )

                return uid

            except sqlite3.IntegrityError:
                raise ValueError("username_exists")


    def get_user_by_username(self, username: str) -> Optional[Tuple[int, str, str, str, int, float]]:
        """
        Return tuple (id, username, password_hash, salt, failed_attempts, lock_until)
        or None if not found.
        """
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, username, password_hash, salt, failed_attempts, lock_until FROM users WHERE username = ?",
                (username,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return (row["id"], row["username"], row["password_hash"], row["salt"], row["failed_attempts"], row["lock_until"])

    def reset_failed_attempts(self, user_id: int):
        ts = time.time()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET failed_attempts = 0, lock_until = 0 WHERE id = ?", (user_id,))
            cur.execute(
                "INSERT INTO audit_trail (user_id, event_type, event_data, created_at) VALUES (?, ?, ?, ?)",
                (user_id, "reset_failed_attempts", "reset by successful login", ts),
            )


    def increment_failed_attempt(self, user_id: int, max_attempts: int, lock_seconds: int):
        """
        Increment the failed login counter and apply lock if needed.
        Handles audit in SAME transaction to avoid nested DB locks.
        """
        ts = time.time()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT failed_attempts FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            if not row:
                return

            attempts = (row["failed_attempts"] or 0) + 1
            lock_until = ts + lock_seconds if attempts >= max_attempts else 0

            # Update user record
            cur.execute("UPDATE users SET failed_attempts = ?, lock_until = ? WHERE id = ?", (attempts, lock_until, user_id))

            # ✅ Audit event written here in SAME transaction
            cur.execute(
                "INSERT INTO audit_trail (user_id, event_type, event_data, created_at) VALUES (?, ?, ?, ?)",
                (user_id, "failed_login", f"attempts={attempts}, lock_until={lock_until}", ts),
            )


    # -----------------------
    # App data storage (optional encrypted)
    # -----------------------
    def upsert_app_data(self, key: str, value: str, encrypt: bool = False):
        ts = time.time()
        blob, enc_flag = (None, 0)
        if encrypt:
            blob, enc_flag = self._encrypt(value)
        else:
            blob, enc_flag = (value.encode("utf-8"), 0)
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO app_data (key, value, encrypted, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, encrypted = excluded.encrypted, updated_at = excluded.updated_at",
                (key, blob, enc_flag, ts),
            )
            self.create_audit(None, "upsert_app_data", f"key={key}, encrypted={enc_flag}")

    def get_app_data(self, key: str) -> Optional[Dict[str, Any]]:
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT value, encrypted, updated_at FROM app_data WHERE key = ?", (key,))
            row = cur.fetchone()
            if not row:
                return None
            val = self._decrypt(row["value"], row["encrypted"])
            return {"key": key, "value": val, "updated_at": row["updated_at"], "encrypted": row["encrypted"]}

    # -----------------------
    # Audit trail
    # -----------------------
    def create_audit(self, user_id: Optional[int], event_type: str, event_data: Optional[str] = None):
        if event_type in ("user_registered", "failed_login", "reset_failed_attempts"):
            return

        ts = time.time()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO audit_trail (user_id, event_type, event_data, created_at) VALUES (?, ?, ?, ?)",
                        (user_id, event_type, event_data, ts))

    # -----------------------
    # Utilities
    # -----------------------
    def close(self):
        """Close all pooled connections."""
        while not self._conn_pool.empty():
            try:
                c = self._conn_pool.get_nowait()
                try:
                    c.close()
                except Exception:
                    pass
            except Exception:
                break