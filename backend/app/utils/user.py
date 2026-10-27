import functools
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

from flask import request
from pymongo import ReturnDocument

from app.config import Config
from .conn import conn_db
from .credentials import hash_password, is_legacy_password, validate_new_password, verify_password


SESSION_TTL = timedelta(hours=24)


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LoginRateLimited(Exception):
    def __init__(self, retry_after):
        self.retry_after = retry_after
        super().__init__('登录尝试过多，请稍后重试')


def request_token():
    # Full account credentials are accepted only in headers, never in URLs.
    return request.headers.get('Token', '').strip()


def _login_attempts(username):
    now = time.time()
    account_key = None
    # MongoDB makes counters shared and atomic across Gunicorn workers.
    for kind, identity, maximum, window in (
        ('address', request.remote_addr or 'unknown', 60, 60),
        ('account', username, 10, 300),
    ):
        bucket = int(now) // window
        digest = hashlib.sha256(identity.encode()).hexdigest()
        key = f'{kind}:{digest}:{bucket}'
        end = (bucket + 1) * window
        item = conn_db('auth_attempts').find_one_and_update(
            {'_id': key},
            {'$inc': {'count': 1}, '$setOnInsert': {'expire_at': datetime.fromtimestamp(end + 60, timezone.utc)}},
            upsert=True, return_document=ReturnDocument.AFTER,
        )
        if item['count'] > maximum:
            raise LoginRateLimited(max(1, int(end - now)))
        if kind == 'account':
            account_key = key
    return account_key


def _new_session():
    return {'token': secrets.token_urlsafe(32), 'token_expire_at': utc_now() + SESSION_TTL}


def _session_user(token):
    if not token:
        return None
    return conn_db('user').find_one({'token': token, 'token_expire_at': {'$gt': utc_now()}})


def user_login(username=None, password=None):
    if (not isinstance(username, str) or not 1 <= len(username) <= 128
            or not isinstance(password, str) or not 1 <= len(password) <= 1024):
        return None
    attempt_key = _login_attempts(username)
    user = conn_db('user').find_one({'username': username})
    if not user or not verify_password(user.get('password'), password):
        return None
    session = _new_session()
    if is_legacy_password(user['password']):
        session['password'] = hash_password(password)
    result = conn_db('user').update_one({'_id': user['_id'], 'password': user['password']}, {'$set': session})
    if not result.matched_count:
        return None
    conn_db('auth_attempts').delete_one({'_id': attempt_key})
    return {'username': username, 'token': session['token'], 'type': 'login'}


def user_login_header():
    if not Config.AUTH:
        return True
    token = request_token()
    if not token:
        return False
    api_key = Config.API_KEY
    if isinstance(api_key, str) and api_key and hmac.compare_digest(token.encode(), api_key.encode()):
        return {'username': 'ARL-API', 'token': token, 'type': 'api'}
    user = _session_user(token)
    if user:
        return {'username': user.get('username'), 'token': token, 'type': 'login'}
    return False


def user_logout(token):
    if token:
        conn_db('user').update_one({'token': token}, {'$set': {'token': None}, '$unset': {'token_expire_at': ''}})


def user_refresh_token(token):
    user = _session_user(token)
    if not user:
        return None
    session = _new_session()
    result = conn_db('user').update_one({'_id': user['_id'], 'token': token}, {'$set': session})
    return session['token'] if result.matched_count else None


def change_pass(token, old_password, new_password):
    user = _session_user(token)
    if not user or not verify_password(user.get('password'), old_password):
        return False
    validate_new_password(new_password)
    result = conn_db('user').update_one(
        {'_id': user['_id'], 'token': token, 'password': user['password']},
        {'$set': {'password': hash_password(new_password), 'token': None}, '$unset': {'token_expire_at': ''}},
    )
    return bool(result.matched_count)


def auth(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if Config.AUTH and not user_login_header():
            return {'message': 'not login', 'code': 401, 'data': {}}, 401
        return func(*args, **kwargs)
    return wrapper
