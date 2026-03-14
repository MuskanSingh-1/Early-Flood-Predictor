import os
import hashlib
import secrets
import time
from typing import Optional
from database import Database

# ---------------------------------------------------------------------------
# SECURITY CONSTANTS
# ---------------------------------------------------------------------------

MAX_FAILED_ATTEMPTS = 5          # Lock user after 5 failed logins
LOCK_DURATION_SEC = 300          # 5-minute lockout period
SALT_BYTES = 16                  # 128-bit random salt
SESSION_TIMEOUT_SEC = 1800       # 30 minutes

# ---------------------------------------------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------------------------------------------

def generate_salt() -> str:
    """Generate a cryptographically secure random salt."""
    return secrets.token_hex(SALT_BYTES)

def hash_password(password: str, salt: str) -> str:
    """Return a SHA-256 salted hash."""
    pwd_bytes = (password + salt).encode("utf-8")
    return hashlib.sha256(pwd_bytes).hexdigest()

# ---------------------------------------------------------------------------
# USER CLASS — registration, authentication, session handling
# ---------------------------------------------------------------------------

class User:
    def __init__(self, db_path: str = "flood_app.db"):
        self.db = Database(db_path)
        self.sessions = {}  # user_id → {token, expiry}

    # -----------------------------------------------------------------------
    # REGISTRATION
    # -----------------------------------------------------------------------
    def register(self, username: str, password: str, full_name: str) -> bool:
        """
        Register a new user with salted SHA-256 password hash.
        Returns True on success, False if username already exists.
        """
        if self.db.get_user_by_username(username):
            return False  # duplicate
        salt = generate_salt()
        hashed = hash_password(password, salt)
        self.db.create_user(username, hashed, salt, full_name)
        return True

    # -----------------------------------------------------------------------
    # VERIFICATION
    # -----------------------------------------------------------------------
    def verify_credentials(self, username: str, password: str) -> bool:
        """
        Verify credentials with brute-force protection.
        Returns True if valid; False otherwise.
        """
        record = self.db.get_user_by_username(username)
        if not record:
            return False

        user_id, _, stored_hash, salt, failed_attempts, lock_until = record

        # Check lock status
        now = time.time()
        if lock_until and now < lock_until:
            print(f"[SECURITY] Account {username} locked until {lock_until}")
            return False

        # Verify hash
        hashed_input = hash_password(password, salt)
        if secrets.compare_digest(hashed_input, stored_hash):
            self.db.reset_failed_attempts(user_id)
            return True
        else:
            self.db.increment_failed_attempt(user_id, MAX_FAILED_ATTEMPTS, LOCK_DURATION_SEC)
            return False

    # -----------------------------------------------------------------------
    # SESSION MANAGEMENT
    # -----------------------------------------------------------------------
    def create_session(self, username: str) -> str:
        """Create session token with expiry."""
        record = self.db.get_user_by_username(username)
        if not record:
            return ""
        user_id = record[0]
        token = secrets.token_urlsafe(32)
        expiry = time.time() + SESSION_TIMEOUT_SEC
        self.sessions[user_id] = {"token": token, "expiry": expiry}
        return token

    def validate_session(self, token: str) -> Optional[int]:
        """Validate token and return user_id if valid."""
        for uid, sess in self.sessions.items():
            if sess["token"] == token and time.time() < sess["expiry"]:
                return uid
        return None

    def logout(self, user_id: int):
        """Terminate active session."""
        if user_id in self.sessions:
            del self.sessions[user_id]