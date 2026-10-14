"""python3 -m unittest discover -s mcp-server -p 'test_*.py' -v"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('arl_mcp_server', Path(__file__).with_name('server.py'))
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.auth = patch.object(server, '_get_auth', return_value=('https://arl.example', 'fixture-token'))
        self.auth.start()
        self.addCleanup(self.auth.stop)

    def call_tool(self):
        return server.handle_request({'id': 1, 'method': 'tools/call', 'params': {
            'name': 'get_asset_profile', 'arguments': {'target': 'alpha.example'}}})['result']

    def fallback_api(self, status, data, failing_endpoint=None):
        def api(endpoint, params=None):
            if endpoint == '/mcp/asset_profile':
                return 404, {}
            if failing_endpoint is None or endpoint == failing_endpoint:
                return status, data
            return 200, {'code': 200, 'items': []}
        return api

    def test_body_auth_error_is_tool_error(self):
        for code in (401, 403, '401'):
            with self.subTest(code=code), patch.object(server, '_request_api', self.fallback_api(200, {'code': code})):
                result = self.call_tool()
                self.assertTrue(result['isError'])
                self.assertEqual(json.loads(result['content'][0]['text'])['status'], 'auth_error')

    def test_one_failed_dimension_does_not_look_empty(self):
        with patch.object(server, '_request_api', self.fallback_api(503, {}, '/vuln/')):
            result = self.call_tool()
        self.assertTrue(result['isError'])
        self.assertEqual(json.loads(result['content'][0]['text'])['status'], 'error')

    def test_successful_empty_queries_still_return_not_found(self):
        with patch.object(server, '_request_api', self.fallback_api(200, {'code': 200, 'items': []})):
            result = self.call_tool()
        self.assertFalse(result['isError'])
        self.assertEqual(json.loads(result['content'][0]['text'])['status'], 'not_found')

    def test_ip_detail_errors_are_checked(self):
        def api(endpoint, params=None):
            if endpoint == '/ip/':
                return 200, {'code': 401}
            return 200, {'items': []}
        with patch.object(server, '_request_api', api):
            self.assertEqual(server._fallback_aggregate_profile('192.0.2.1')['status'], 'auth_error')

    def test_malformed_success_response_is_error(self):
        for data in ({'code': 200}, {'items': None}, ['unexpected']):
            with self.subTest(data=data), patch.object(server, '_request_api', return_value=(200, data)):
                self.assertEqual(server._request_items('/site/', {})[0], 502)

    def test_invalid_ca_path_returns_error_without_request(self):
        with patch.dict(os.environ, {'ARL_CA_BUNDLE': '/nonexistent/fixture-ca.pem', 'ARL_TLS_VERIFY': 'true'}), \
                patch.object(server.urllib.request, 'urlopen') as request:
            self.assertEqual(server._request_api('/site/')[0], 500)
            request.assert_not_called()

    def test_downloadable_client_matches_server(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual((root / 'mcp-server/server.py').read_bytes(),
                         (root / 'frontend/public/mcp/server.py').read_bytes())

    @unittest.skipUnless(shutil.which('openssl'), 'openssl is required for the loopback TLS fixture')
    def test_loopback_tls_default_rejects_self_signed_and_explicit_ca_works(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"code":200,"items":[]}')
            def log_message(self, *args):
                pass

        with tempfile.TemporaryDirectory() as directory:
            cert, key = str(Path(directory) / 'cert.pem'), str(Path(directory) / 'key.pem')
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                            '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost',
                            '-keyout', key, '-out', cert], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            httpd = HTTPServer(('127.0.0.1', 0), Handler)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                host = 'https://localhost:{}'.format(httpd.server_port)
                with patch.object(server, '_get_auth', return_value=(host, 'fixture-token')), \
                        patch.dict(os.environ, {'NO_PROXY': 'localhost', 'no_proxy': 'localhost',
                                               'ARL_CA_BUNDLE': '', 'ARL_TLS_VERIFY': 'true'}):
                    code, error = server._request_api('/site/')
                    self.assertEqual(code, 500)
                    self.assertIn('CERTIFICATE_VERIFY_FAILED', error['message'])
                    with patch.dict(os.environ, {'ARL_CA_BUNDLE': cert}):
                        self.assertEqual(server._request_api('/site/')[0], 200)
                    # A trusted certificate must still match the requested hostname.
                    with patch.object(server, '_get_auth', return_value=(host.replace('localhost', '127.0.0.1'), 'fixture-token')), \
                            patch.dict(os.environ, {'ARL_CA_BUNDLE': cert, 'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}):
                        self.assertEqual(server._request_api('/site/')[0], 500)
                    with patch.dict(os.environ, {'ARL_TLS_VERIFY': 'false'}):
                        self.assertEqual(server._request_api('/site/')[0], 200)
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
