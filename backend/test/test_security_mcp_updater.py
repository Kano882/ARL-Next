import ast
import csv
import importlib.util
import io
import json
from pathlib import Path
import threading
import time
import types
from unittest.mock import Mock
from http.server import ThreadingHTTPServer

import pytest
import requests

from security_support import ROOT, app_env, load_source, make_client


@pytest.mark.parametrize('value', ['=1+1', '+SUM(1,1)', '-1+1', '@SUM(1)', '\t=1+1', '\r=1+1', '\n=1+1', '  =1+1'])
def test_csv_formula_prefixes_are_literal(app_env, value):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    app_env.db.site.insert_one({'task_id': '0' * 24, 'title': value})
    client = make_client(app_env, route.ns)
    response = client.get('/api/mcp/task_detail_export', headers={'Token': 'fixture-api-key'},
                          query_string={'task_id': '0' * 24, 'tab': 'site', 'columns': 'title'})
    assert list(csv.reader(io.StringIO(response.get_data(as_text=True)))) == [['title'], ["'" + value]]


@pytest.mark.parametrize('host', ['https://example.test"; MARKER=True #', 'javascript:alert(1)',
                                 'https://user:pass@example.test', 'https://example.test/path',
                                 'https://example.test:0', 'https://example.test/?query=1'])
def test_mcp_unsafe_host_is_rejected(app_env, host):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    response = make_client(app_env, route.ns).get('/api/mcp/export_server',
                                                headers={'Token': 'fixture-api-key'}, query_string={'host': host})
    assert response.status_code == 400


def test_mcp_export_serializes_custom_api_key_as_data(app_env):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    token = 'fixture"; MARKER=True #\\tail'
    app_env.cfg.Config.API_KEY = token
    response = make_client(app_env, route.ns).get('/api/mcp/export_server', headers={'Token': token},
                                                query_string={'host': 'https://example.test:5173'})
    assert response.status_code == 200
    tree = ast.parse(response.get_data(as_text=True))
    constants = {n.targets[0].id: n.value.value for n in tree.body
                 if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                 and isinstance(n.value, ast.Constant)}
    assert constants['DEFAULT_HOST'] == 'https://example.test:5173'
    assert constants['DEFAULT_TOKEN'] == token
    assert 'MARKER' not in constants


def test_csv_formula_headers_are_literal(app_env):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    app_env.db.site.insert_one({'task_id': '0' * 24, 'title': 'ordinary title'})
    response = make_client(app_env, route.ns).get('/api/mcp/task_detail_export',
        headers={'Token': 'fixture-api-key'}, query_string={'task_id': '0' * 24, 'columns': '=1+1,title'})
    rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
    assert rows == [["'=1+1", 'title'], ['', 'ordinary title']]


@pytest.fixture
def updater(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location('security_updater', ROOT.parent / 'updater/updater.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.READ_TOKEN_FILE = str(tmp_path / 'state/read_token.json')
    module.LOG_FILE = str(tmp_path / 'update.log')
    Path(module.LOG_FILE).write_text('private log fixture\n')
    return module


def test_updater_read_token_expiry_rotation_and_persistence(updater):
    token = updater.issue_log_token()
    assert updater.verify_log_token(token)
    assert token not in Path(updater.READ_TOKEN_FILE).read_text()
    assert Path(updater.READ_TOKEN_FILE).stat().st_mode & 0o777 == 0o600
    newer = updater.issue_log_token()
    assert not updater.verify_log_token(token)
    assert updater.verify_log_token(newer)
    record = json.loads(Path(updater.READ_TOKEN_FILE).read_text())
    record['expires_at'] = time.time() - 1
    Path(updater.READ_TOKEN_FILE).write_text(json.dumps(record))
    assert not updater.verify_log_token(newer)


def test_updater_control_status_scopes_and_expiry(updater, monkeypatch):
    handler = object.__new__(updater.PollingHandler)
    token = 'fixture-' + 'x' * 40
    record = {'token': token, 'purpose': 'status', 'expires_at': time.time() + 300}
    runner = Mock(return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(record)))
    monkeypatch.setattr(updater.subprocess, 'run', runner)
    assert handler.verify_token(token, purpose='status')
    assert not handler.verify_token(token, purpose='control')
    record['expires_at'] = time.time() - 1
    runner.return_value.stdout = json.dumps(record)
    assert not handler.verify_token(token, purpose='status')
    assert not handler._authorize_token('')


def test_updater_public_log_and_get_mutations_are_denied(updater, monkeypatch):
    # Any unexpected Docker/host command fails the test.
    monkeypatch.setattr(updater.subprocess, 'run', Mock(side_effect=AssertionError('No host commands allowed')))
    server = ThreadingHTTPServer(('127.0.0.1', 0), updater.PollingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f'http://127.0.0.1:{server.server_port}'
        assert requests.get(base + '/update/log?offset=0', timeout=3).status_code == 403
        assert requests.get(base + '/update/trigger?token=ignored', timeout=3).status_code == 405
        assert requests.get(base + '/update/auth_status', timeout=3).status_code == 403
        token = updater.issue_log_token()
        response = requests.get(base + '/update/log?offset=0', headers={'X-Update-Read-Token': token}, timeout=3)
        assert response.status_code == 200
        assert response.json()['chunk'] == 'private log fixture\n'
        assert 'Access-Control-Allow-Origin' not in response.headers
        assert requests.get(base + '/update/log?token=' + token, timeout=3).status_code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_bootstrap_password_random_private_and_existing_accounts_preserved(app_env, capsys):
    module = load_source(app_env.monkeypatch, 'security_bootstrap', 'inject_user.py')
    path = app_env.tmp / 'initial-password'
    module.ensure_admin(app_env.db.user, password_file=str(path))
    password = path.read_text().strip()
    assert len(password) >= 24
    assert password not in capsys.readouterr().out
    assert path.stat().st_mode & 0o777 == 0o600
    user = app_env.db.user.find_one({'username': 'admin'})
    assert app_env.credentials.verify_password(user['password'], password)
    module.ensure_admin(app_env.db.user, password='ignored-password', password_file=str(path))
    assert app_env.db.user.find_one()['password'] == user['password']
    app_env.db.user.update_one({'username': 'admin'}, {'$set': {'token': 'old-session'}})
    module.ensure_admin(app_env.db.user, reset=True, password='new-fixture-password', password_file=str(path))
    assert app_env.db.user.find_one()['token'] is None
    assert app_env.credentials.verify_password(app_env.db.user.find_one()['password'], 'new-fixture-password')
