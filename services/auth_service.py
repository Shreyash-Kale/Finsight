import hashlib
import hmac
import secrets
from typing import Any, Dict, Optional


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored_password: str) -> bool:
    if not stored_password:
        return False

    if stored_password.startswith("pbkdf2_sha256$"):
        try:
            _, salt, stored_digest = stored_password.split("$", 2)
            computed = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                100000,
            ).hex()
            return hmac.compare_digest(computed, stored_digest)
        except ValueError:
            return False

    return hmac.compare_digest(password, stored_password)


def verify_login(user_data_collection, email: str, password: str) -> Optional[Dict[str, Any]]:
    user = user_data_collection.find_one({"email": email})
    if not user:
        return None

    stored_password = user.get("password", "")
    if not verify_password(password, stored_password):
        return None

    # Seamless migration for existing plain-text passwords.
    if not stored_password.startswith("pbkdf2_sha256$"):
        user_data_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"password": hash_password(password)}},
        )

    return user
