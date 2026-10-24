import ast
from datetime import datetime, timedelta
import hashlib
import io
from pathlib import Path
import types

import pytest

from security_support import ROOT, app_env, load_source, make_client, load_backup
from test_security_backup import make_backup


def logged_in(env):
    env.db.user.insert_one({'username': 'review', 'password': env.credentials.hash_password('fixture-long-password')})
    endpoint = load_source(env.monkeypatch, 'app.routes.user', 'app/routes/user.py')
    client = make_client(env, endpoint.ns)
    res = client.post('/api/user/login', json={'username': 'review', 'password': 'fixture-long-password'})
    assert res.json['code'] == 200
    return client, res.json['data']['token']


def test_header_only_session_expiry_logout_and_api_key(app_env):
    client, token = logged_in(app_env)
    assert client.get('/protected', headers={'Token': token}).status_code == 200
    assert client.get('/protected?token=' + token).status_code == 401
    app_env.db.user.update_one({'token': token}, {'$set': {'token_expire_at': datetime.utcnow() - timedelta(seconds=1)}})
    assert client.get('/protected', headers={'Token': token}).status_code == 401
    assert client.get('/protected', headers={'Token': 'fixture-api-key'}).status_code == 200
    assert client.post('/api/user/refresh_token', headers={'Token': token}).status_code == 401


def test_legacy_password_is_upgraded_only_after_success(app_env):
    legacy = hashlib.md5(b'arlsalt!@#fixture-old-password').hexdigest()
    app_env.db.user.insert_one({'username': 'review', 'password': legacy})
    endpoint = load_source(app_env.monkeypatch, 'app.routes.user', 'app/routes/user.py')
    client = make_client(app_env, endpoint.ns)
    assert client.post('/api/user/login', json={'username': 'review', 'password': 'wrong'}).json['code'] == 401
    assert app_env.db.user.find_one()['password'] == legacy
    response = client.post('/api/user/login', json={'username': 'review', 'password': 'fixture-old-password'})
    assert response.json['code'] == 200
    user = app_env.db.user.find_one()
    assert user['password'].startswith('scrypt:')
    assert user['token_expire_at'] > datetime.utcnow()


def test_login_rate_limit_shared_between_clients_and_expires(app_env):
    app_env.monkeypatch.setattr(app_env.user, 'time', types.SimpleNamespace(time=lambda: 1_800_000_000))
    endpoint = load_source(app_env.monkeypatch, 'app.routes.user', 'app/routes/user.py')
    client = make_client(app_env, endpoint.ns)
    for _ in range(10):
        assert client.post('/api/user/login', json={'username': 'review', 'password': 'wrong'}).json['code'] == 401
    response = client.post('/api/user/login', json={'username': 'review', 'password': 'wrong'})
    assert response.status_code == 429
    assert response.headers['Retry-After'] == '300'
    app_env.monkeypatch.setattr(app_env.user, 'time', types.SimpleNamespace(time=lambda: 1_800_000_301))
    assert client.post('/api/user/login', json={'username': 'review', 'password': 'wrong'}).json['code'] == 401


def test_refresh_and_password_change_revoke_prior_session(app_env):
    client, old = logged_in(app_env)
    new = client.post('/api/user/refresh_token', headers={'Token': old}).json['data']['token']
    assert client.get('/protected', headers={'Token': old}).status_code == 401
    bad = client.post('/api/user/change_pass', headers={'Token': new},
                      json={'old_password': 'fixture-long-password', 'new_password': 'short', 'check_password': 'short'})
    assert bad.status_code == 400
    good = client.post('/api/user/change_pass', headers={'Token': new}, json={
        'old_password': 'fixture-long-password', 'new_password': 'fixture-replacement-password',
        'check_password': 'fixture-replacement-password'})
    assert good.json['code'] == 200
    assert client.get('/protected', headers={'Token': new}).status_code == 401


def test_legacy_session_migration_is_bounded_and_idempotent(app_env):
    tree = ast.parse((ROOT / 'app/utils/arlupdate.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'migrate_user_sessions')
    env = {'conn_db': lambda name: app_env.db[name]}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'auth-migration', 'exec'), env)
    app_env.db.user.insert_one({'username': 'review', 'token': 'legacy-token'})
    env['migrate_user_sessions']()
    expires = app_env.db.user.find_one()['token_expire_at']
    assert datetime.utcnow() < expires < datetime.utcnow() + timedelta(hours=25)
    env['migrate_user_sessions']()
    assert app_env.db.user.find_one()['token_expire_at'] == expires
    assert all('expireAfterSeconds' not in index for index in app_env.db.user.index_information().values())


def test_screenshot_requires_auth_and_disables_caching(app_env):
    endpoint = load_source(app_env.monkeypatch, 'app.routes.image', 'app/routes/image.py')
    path = Path(app_env.cfg.Config.SCREENSHOT_DIR) / 'fixture-task' / 'fixture.jpg'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'private screenshot')
    client = make_client(app_env, endpoint.ns)
    url = '/api/image/fixture-task/fixture.jpg'
    assert client.get(url).status_code == 401
    response = client.get(url, headers={'Token': 'fixture-api-key'})
    assert response.data == b'private screenshot'
    assert response.headers['Cache-Control'] == 'private, no-store'


def test_backup_download_ticket_is_scoped_single_use_and_revocable(app_env):
    service, directory = load_backup(app_env)
    route = load_source(app_env.monkeypatch, 'app.routes.backup', 'app/routes/backup.py')
    client = make_client(app_env, route.ns)
    filename = 'arl_backup_fixture.tar.gz'
    (directory / filename).write_bytes(b'backup bytes')
    assert client.get('/api/backup/download/' + filename).status_code == 401
    ticket = client.post('/api/backup/download_ticket', json={'filename': filename},
                         headers={'Token': 'fixture-api-key'}).json['data']['ticket']
    assert client.get('/protected?ticket=' + ticket).status_code == 401
    assert client.get('/api/backup/download/arl_backup_other.tar.gz?ticket=' + ticket).status_code == 401
    assert client.get('/api/backup/download/' + filename + '?ticket=' + ticket).data == b'backup bytes'
    assert client.get('/api/backup/download/' + filename + '?ticket=' + ticket).status_code == 401
    ticket = client.post('/api/backup/download_ticket', json={'filename': filename},
                         headers={'Token': 'fixture-api-key'}).json['data']['ticket']
    app_env.cfg.Config.API_KEY = 'rotated-api-key'
    assert client.get('/api/backup/download/' + filename + '?ticket=' + ticket).status_code == 401


def test_expired_download_ticket_rejected(app_env):
    _, directory = load_backup(app_env)
    route = load_source(app_env.monkeypatch, 'app.routes.backup', 'app/routes/backup.py')
    client = make_client(app_env, route.ns)
    filename = 'arl_backup_fixture.tar.gz'
    (directory / filename).write_bytes(b'backup')
    ticket = client.post('/api/backup/download_ticket', json={'filename': filename},
                         headers={'Token': 'fixture-api-key'}).json['data']['ticket']
    app_env.db.download_ticket.update_many({}, {'$set': {'expire_at': datetime.utcnow() - timedelta(seconds=1)}})
    assert client.get('/api/backup/download/' + filename + '?ticket=' + ticket).status_code == 401


def test_invalid_upload_cannot_destroy_existing_backup(app_env):
    _, directory = load_backup(app_env)
    route = load_source(app_env.monkeypatch, 'app.routes.backup', 'app/routes/backup.py')
    client = make_client(app_env, route.ns)
    filename = 'arl_backup_fixture.tar.gz'
    existing = directory / filename
    existing.write_bytes(b'existing backup')
    response = client.post('/api/backup/upload', headers={'Token': 'fixture-api-key'},
                           data={'file': (io.BytesIO(b'not a tar archive'), filename)})
    assert response.json['code'] == 400
    assert existing.read_bytes() == b'existing backup'


def test_bad_inner_archive_never_reaches_mongorestore(app_env):
    service, directory = load_backup(app_env)
    path = make_backup(directory, [('routes/user.py', b'bad')])
    with pytest.raises(ValueError):
        service.restore_backup_archive(path)
    service.run_command_streaming.assert_not_called()
