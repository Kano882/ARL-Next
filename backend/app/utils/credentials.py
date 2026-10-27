"""Password hashing with verification-only compatibility for legacy MD5 hashes."""

import hashlib
import hmac
import re

from werkzeug.security import check_password_hash, generate_password_hash


def is_legacy_password(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{32}', value) is not None


def hash_password(password):
    return generate_password_hash(password, method='scrypt')


def verify_password(stored, password):
    if not isinstance(stored, str) or not isinstance(password, str) or len(password) > 1024:
        return False
    if is_legacy_password(stored):
        candidate = hashlib.md5(('arlsalt!@#' + password).encode()).hexdigest()
        return hmac.compare_digest(stored, candidate)
    try:
        return check_password_hash(stored, password)
    except (ValueError, TypeError):
        return False


def validate_new_password(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        raise ValueError('新密码长度必须在 12 到 1024 个字符之间')
