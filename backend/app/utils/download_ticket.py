"""Single-use, resource-scoped tickets for native browser backup downloads."""

from datetime import timedelta
import hashlib
import hmac
import secrets

from app.config import Config
from .conn import conn_db
from .user import user_login_header, utc_now


def _digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def issue_download_ticket(filename):
    principal = user_login_header()
    if not principal:
        raise ValueError('not login')
    ticket = secrets.token_urlsafe(32)
    conn_db('download_ticket').insert_one({
        '_id': _digest(ticket), 'filename': filename,
        'expire_at': utc_now() + timedelta(seconds=60),
        'principal': principal.get('type') if isinstance(principal, dict) else 'disabled',
        'username': principal.get('username') if isinstance(principal, dict) else '',
        'session_hash': _digest(principal['token']) if isinstance(principal, dict) else '',
    })
    return ticket


def consume_download_ticket(ticket, filename):
    if not isinstance(ticket, str) or not 20 <= len(ticket) <= 128:
        return False
    item = conn_db('download_ticket').find_one_and_delete({
        '_id': _digest(ticket), 'filename': filename, 'expire_at': {'$gt': utc_now()},
    })
    if not item:
        return False
    if item['principal'] == 'api':
        current_token = Config.API_KEY
    elif item['principal'] == 'login':
        user = conn_db('user').find_one({'username': item['username'],
                                       'token_expire_at': {'$gt': utc_now()}})
        current_token = user.get('token') if user else None
    else:
        return False
    return bool(current_token and hmac.compare_digest(_digest(current_token), item['session_hash']))
