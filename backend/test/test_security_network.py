import ast
import importlib.util
import logging
from pathlib import Path
import socket
import sys
import types
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('favicon_http_test', ROOT / 'app/utils/favicon_http.py')
favicon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(favicon)


@pytest.fixture
def policy(monkeypatch):
    utils = types.ModuleType('app.utils')
    utils.get_logger = lambda: logging.getLogger('security-test')
    security = types.ModuleType('app.utils.security_policy')
    security.get_security_policy = lambda: (['192.0.2.20/32', '127.0.0.0/8', '2001:db8::/32'], [])
    monkeypatch.setitem(sys.modules, 'app.utils', utils)
    monkeypatch.setitem(sys.modules, 'app.utils.security_policy', security)
    tree = ast.parse((ROOT / 'app/utils/ip.py').read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'not_in_black_ips']
    env = {'__package__': 'app.utils'}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'ip-policy', 'exec'), env)
    return env['not_in_black_ips'], security


@pytest.mark.parametrize('target', ['192.0.2.20', '192.0.2.10-30', '192.0.2.0/24',
                                   '192.0.2.10-192.0.2.30', '::ffff:127.0.0.1',
                                   '2001:db8::1', '2001:db8::/31', 'bad', '192.0.2.30-10'])
def test_blocked_or_invalid_target_never_passes(policy, target):
    check, _ = policy
    assert not check(target)


def test_allowed_ranges_and_fail_closed_policy(policy):
    check, security = policy
    assert check('192.0.2.1-19')
    assert check('198.51.100.0/24')
    security.get_security_policy = Mock(side_effect=RuntimeError('database unavailable'))
    assert not check('198.51.100.1')


def test_corrupted_black_ips_entry_does_not_block_valid_targets(policy):
    check, security = policy
    security.get_security_policy = lambda: (['bad-rule-value', '192.0.2.20/32'], [])
    assert check('198.51.100.1')
    assert not check('192.0.2.20')


@pytest.mark.parametrize('address', ['127.0.0.1', '::1', '::ffff:127.0.0.1', '169.254.169.254',
                                    '0.0.0.0', '224.0.0.1', '172.18.0.2'])
def test_favicon_forbidden_addresses_rejected_before_transport(monkeypatch, address):
    monkeypatch.setattr(favicon.socket, 'getaddrinfo', lambda *a, **k: [(0, 0, 0, '', (address, 80))])
    transport = Mock(side_effect=AssertionError('Transport must not run'))
    monkeypatch.setattr(favicon.urllib3, 'PoolManager', transport)
    with pytest.raises(ValueError):
        favicon.fetch_favicon_response('http://scan.example.test/icon',
                                       allowed_ip=lambda ip: ip != '172.18.0.2', forbidden_domain=lambda _: False)
    transport.assert_not_called()


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'http://user:pass@scan.example/icon',
                                'http://scan.example\\@127.0.0.1/', 'http://scan.example:0/icon'])
def test_favicon_invalid_urls_rejected(url):
    with pytest.raises(ValueError):
        favicon.fetch_favicon_response(url, allowed_ip=lambda _: True, forbidden_domain=lambda _: False)


def test_mixed_public_and_private_dns_answers_fail_closed(monkeypatch):
    monkeypatch.setattr(favicon.socket, 'getaddrinfo', lambda *a, **k: [
        (0, 0, 0, '', ('192.0.2.1', 80)), (0, 0, 0, '', ('127.0.0.1', 80)),
    ])
    factory = Mock(side_effect=AssertionError('No transport allowed'))
    monkeypatch.setattr(favicon.urllib3, 'PoolManager', factory)
    with pytest.raises(ValueError):
        favicon.fetch_favicon_response('http://scan.example/icon', allowed_ip=lambda _: True,
                                       forbidden_domain=lambda _: False)
    factory.assert_not_called()


@pytest.mark.parametrize('proxy', ['', 'http://proxy.example:8080'])
def test_favicon_uses_pinned_ip_preserves_host_and_disables_redirects(monkeypatch, proxy):
    resolver = Mock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.0.2.1', 443))])
    monkeypatch.setattr(favicon.socket, 'getaddrinfo', resolver)
    response = Mock(status=302, headers={'Location': 'http://127.0.0.1/'})
    response.read.return_value = b''
    manager = Mock()
    manager.request.return_value = response
    factory = Mock(return_value=manager)
    monkeypatch.setattr(favicon.urllib3, 'ProxyManager' if proxy else 'PoolManager', factory)
    result = favicon.fetch_favicon_response('https://scan.example/icon', allowed_ip=lambda _: True,
                                            forbidden_domain=lambda _: False, proxy_url=proxy)
    assert result.status_code == 302
    resolver.assert_called_once()
    assert manager.request.call_args.args[1] == 'https://192.0.2.1:443/icon'
    assert manager.request.call_args.kwargs['headers']['Host'] == 'scan.example:443'
    assert manager.request.call_args.kwargs['redirect'] is False
    assert factory.call_args.kwargs['server_hostname'] == 'scan.example'
    response.close.assert_called_once()
    manager.clear.assert_called_once()
