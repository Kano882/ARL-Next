import json
import os
import secrets
import tempfile
import time


def issue_updater_token(purpose='control'):
    paths = {'control': '/tmp/arl_update_token', 'status': '/tmp/arl_update_status_token'}
    if not isinstance(purpose, str) or purpose not in paths:
        raise ValueError('Invalid updater token purpose')
    token = secrets.token_urlsafe(32)
    fd, temporary = tempfile.mkstemp(prefix='arl_update_token_', dir='/tmp')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump({'token': token, 'expires_at': time.time() + 300, 'purpose': purpose}, stream)
        os.replace(temporary, paths[purpose])
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return token
