# -*- coding: utf-8 -*-
"""
test_wih_full_coverage.py
=========================
Comprehensive 100% Coverage Test Suite for WIH (Web Info Hunter) Engine.
Covers all statements, branches, edge cases, error fallbacks, and boundary conditions for:
  - backend/app/services/wih/fnv1a.py
  - backend/app/services/wih/verifier.py
  - backend/app/services/wih/rule_engine.py
  - backend/app/services/wih/chunk_parser.py
  - backend/app/services/wih/hunter.py
  - backend/app/services/infoHunter.py
"""

import os
import sys
import time
import json
import base64
import tempfile
import threading
from unittest.mock import patch, MagicMock
from http.server import BaseHTTPRequestHandler

try:
    from http.server import ThreadingHTTPServer
except ImportError:
    from http.server import HTTPServer as ThreadingHTTPServer

# Setup sys.path
CUR_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(CUR_DIR) == "test" and os.path.basename(os.path.dirname(CUR_DIR)) == "backend":
    BACKEND_DIR = os.path.dirname(CUR_DIR)
elif os.path.exists(os.path.join(CUR_DIR, "backend")):
    BACKEND_DIR = os.path.join(CUR_DIR, "backend")
elif os.path.exists(os.path.join(os.path.dirname(CUR_DIR), "backend")):
    BACKEND_DIR = os.path.join(os.path.dirname(CUR_DIR), "backend")
else:
    BACKEND_DIR = os.path.abspath("backend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Bypass mongo timeout in Config properties
from app.config import _config_cache, Config
_config_cache["data"] = {}
_config_cache["last_update"] = time.time() + 99999999

from app.modules import WihRecord
from app.services.wih.fnv1a import fnv1a_64, fnv1a_64_int
from app.services.wih.verifier import parse_jwt_payload, verify_alicloud_ak, verify_tencentcloud_ak
from app.services.wih.rule_engine import (
    WihRuleEngine,
    ExcludeRuleMatcher,
    _get_default_rule_path,
    BUILTIN_DOMAIN_PATTERN,
    BUILTIN_SECRET_KEY_PATTERN
)
from app.services.wih.chunk_parser import WebpackChunkParser
from app.services.wih.hunter import PyInfoHunter, run_wih_python, _get_proxy
from app.services import run_wih


# ============================================================================
# 1. FNV-1a 64-bit Tests (fnv1a.py)
# ============================================================================
def test_fnv1a_complete():
    # String and Bytes parity
    test_data = [
        ("hello world", "8618312879776256743", 8618312879776256743),
        (b"hello world", "8618312879776256743", 8618312879776256743),
        ("", "14695981039346656037", 14695981039346656037),
        (b"", "14695981039346656037", 14695981039346656037),
        ("中文测试", "8491584761721039823", 8491584761721039823),
        (b"\xe4\xb8\xad\xe6\x96\x87\xe6\xb5\x8b\xe8\xaf\x95", "8491584761721039823", 8491584761721039823),
    ]
    for inp, expected_str, expected_int in test_data:
        assert fnv1a_64(inp) == expected_str
        assert fnv1a_64_int(inp) == expected_int


# ============================================================================
# 2. Verifier Tests (verifier.py)
# ============================================================================
def test_verifier_jwt():
    # Empty
    assert parse_jwt_payload("") is None
    assert parse_jwt_payload("invalid") is None
    assert parse_jwt_payload("a.b") is None

    # Valid JWT
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').decode().rstrip("=")
    payload_data = {"user": "admin", "role": "root", "id": 12345}
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
    jwt_token = f"{header}.{payload}.signature"
    decoded = parse_jwt_payload(jwt_token)
    assert decoded is not None
    assert decoded["user"] == "admin"
    assert decoded["id"] == 12345

    # Malformed base64 / json in JWT payload
    assert parse_jwt_payload("abc.!!!invalid_base64!!!.def") is None


def test_verifier_cloud_aks():
    # AliCloud AK
    assert verify_alicloud_ak("")["valid"] is False
    assert verify_alicloud_ak("INVALID")["valid"] is False
    assert verify_alicloud_ak("LTAI123")["valid"] is False  # too short
    v_ali = verify_alicloud_ak("LTAI5t7eX1234567890abcdef")
    assert v_ali.get("format_valid") is True
    assert v_ali["provider"] == "alicloud"

    # Tencent Cloud AK
    assert verify_tencentcloud_ak("")["valid"] is False
    assert verify_tencentcloud_ak("INVALID")["valid"] is False
    assert verify_tencentcloud_ak("AKID123")["valid"] is False  # too short
    v_tx = verify_tencentcloud_ak("AKIDz1234567890abcdef1234567890abcdef")
    assert v_tx.get("format_valid") is True
    assert v_tx["provider"] == "tencentcloud"


# ============================================================================
# 3. Rule Engine & Exclude Rules Tests (rule_engine.py)
# ============================================================================
def test_rule_engine_exclude_rules_and_matching():
    # Test ExcludeRuleMatcher all dimensions
    ex1 = ExcludeRuleMatcher({
        "name": "test_disabled",
        "enabled": False,
        "id": "domain",
        "target": "example.com"
    })
    assert ex1.matches("domain", "test.com", "example.com", "http://example.com") is False

    # Regex target & content & source & source_tag
    ex2 = ExcludeRuleMatcher({
        "name": "full_exclude",
        "enabled": True,
        "id": "secret_key",
        "target": "regex:test\\.internal",
        "content": "regex:dummy_secret_[0-9]+",
        "source": "regex:vendor\\.js",
        "source_tag": "script"
    })
    assert ex2.matches("secret_key", "dummy_secret_1234567890123456", "https://test.internal", "https://test.internal/vendor.js", "script") is True
    assert ex2.matches("secret_key", "other_secret", "https://test.internal", "https://test.internal/vendor.js", "script") is False
    assert ex2.matches("secret_key", "dummy_secret_1234567890123456", "https://other.internal", "https://test.internal/vendor.js", "script") is False
    assert ex2.matches("secret_key", "dummy_secret_1234567890123456", "https://test.internal", "https://test.internal/app.js", "script") is False
    assert ex2.matches("secret_key", "dummy_secret_1234567890123456", "https://test.internal", "https://test.internal/vendor.js", "page") is False
    assert ex2.matches("Aliyun_AK_ID", "dummy_secret_1234567890123456", "https://test.internal", "https://test.internal/vendor.js", "script") is False

    # Plain string matches
    ex3 = ExcludeRuleMatcher({
        "name": "str_match",
        "enabled": True,
        "target": "test.com",
        "content": "ignore_me",
        "source": "static/js"
    })
    assert ex3.matches("any_type", "ignore_me", "https://test.com/login", "https://test.com/static/js/app.js") is True
    assert ex3.matches("any_type", "keep_me", "https://test.com/login", "https://test.com/static/js/app.js") is False

    # Invalid regex in exclude rule
    ex_invalid = ExcludeRuleMatcher({
        "target": "regex:[[[invalid("
    })
    assert ex_invalid.target_pattern is None


def test_rule_engine_fallback_yaml_and_error_handling():
    engine = WihRuleEngine()
    
    # Test _parse_yaml_fallback
    yaml_sample = """
    # Comments
    rules:
      - id: custom_rule_1
        enabled: true
        pattern: "FOO_[A-Z0-9]{10}"
      - id: custom_rule_2
        enabled: false
        pattern: "BAR_[0-9]+"
    exclude_rules:
      - name: "ex1"
        id: custom_rule_1
        target: "example.com"
        enabled: true
    """
    parsed = engine._parse_yaml_fallback(yaml_sample)
    assert len(parsed["rules"]) == 2
    assert parsed["rules"][0]["id"] == "custom_rule_1"
    assert parsed["rules"][0]["enabled"] is True
    assert len(parsed["exclude_rules"]) == 1

    # Test loading from non-existent path
    non_existent = WihRuleEngine("/non/existent/path/rules.yml")
    assert len(non_existent.rules) >= 4  # Default fallback rules loaded

    # Test malformed regex in rule YAML
    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as tf:
        tf.write("""
        rules:
          - id: bad_regex
            enabled: true
            pattern: "(?P<invalid"
          - id: good_regex
            enabled: true
            pattern: "MYKEY_[0-9]{5}"
        """)
        tf_path = tf.name

    try:
        temp_engine = WihRuleEngine(tf_path)
        assert any(r["id"] == "good_regex" for r in temp_engine.rules)
    finally:
        if os.path.exists(tf_path):
            os.unlink(tf_path)

    # Test default rule path resolver
    default_p = _get_default_rule_path()
    assert os.path.exists(default_p)


def test_rule_engine_all_rule_types():
    engine = WihRuleEngine()
    
    # Text with all kinds of credentials
    sample_text = """
    // All Rule Categories
    var id_card = "110101199003072345";
    var jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c";
    var aliyun_ak = "LTAI5t7eX9876543210zyxwvu";
    var qcloud_ak = "AKIDz1234567890abcdef1234567890abcdef";
    var jdcloud_ak = "JDC_1234567890ABCDEF1234567890";
    var aws_ak = "AKIAIOSFODNN7EXAMPLE";
    var volcano_ak = "AKLT1234567890abcdef1234567890abcdef12345";
    var kingsoft_ak = "AKLT1234567890abcdef1234";
    var gcp_ak = "AIzaSyD1234567890abcdef1234567890abcdef";
    var secret_k = "secret_key = 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6'";
    var bearer = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9abcdef1234567890";
    var basic = "Basic YWRtaW46cGFzc3dvcmQxMjM0NTY=";
    var auth = "Authorization: Token abcdef1234567890abcdef1234567890";
    var priv_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA01234567890abcdef1234567890abcdef\n-----END RSA PRIVATE KEY-----";
    var gitlab_tok = "glpat-1234567890abcdefghij";
    var github_tok = "ghp_1234567890abcdefghijklmnopqrstuvwxyz12";
    var qcloud_gw = "APID1234567890abcdef1234567890abcdef12";
    var wx_appid = "wx1234567890abcdef";
    var wx_corpid = "ww1234567890abcdef";
    var wx_id = "gh_1234567890ab";
    var pass = "admin_password = 'MySecretPass123!'";
    var wx_hook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=12345678-1234-1234-1234-123456789012";
    var dt_hook = "https://oapi.dingtalk.com/robot/send?access_token=1234567890123456789012345678901234567890123456789012345678901234";
    var fs_hook = "https://open.feishu.cn/open-apis/bot/v2/hook/12345678-1234-1234-1234-123456789012";
    var sl_hook = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX";
    var grafana_key = "eyJrIjoiaW52YWxpZF9ncmFmYW5hX2tleV9mb3JfdGVzdF9kZXRlY3Rpb25fMTIzNDU2Nzg5MDEyMzQ1Njc4OTA=";
    var grafana_tok = "glc_1234567890abcdef1234567890abcdef1234567890=";
    var grafana_sa = "glsa_12345678901234567890123456789012_12345678";
    var app_key = 'VUE_APP_APIKEY="1234567890abcdef1234567890"';
    var domain = "https://api.internal-cloud.corp.com/v1/data";
    """
    matches = engine.extract_from_text(sample_text)
    types_found = {m[0] for m in matches}
    
    assert "id_card" in types_found
    assert "jwt_token" in types_found
    assert "Aliyun_AK_ID" in types_found
    assert "QCloud_AK_ID" in types_found
    assert "JDCloud_AK_ID" in types_found
    assert "AWS_AK_ID" in types_found
    assert "VolcanoEngine_AK_ID" in types_found
    assert "Kingsoft_AK_ID" in types_found
    assert "GCP_AK_ID" in types_found
    assert "secret_key" in types_found
    assert "bearer_token" in types_found
    assert "basic_token" in types_found
    assert "auth_token" in types_found
    assert "private_key" in types_found
    assert "gitlab_v2_token" in types_found
    assert "github_token" in types_found
    assert "qcloud_api_gateway_appkey" in types_found
    assert "wechat_appid" in types_found
    assert "wechat_corpid" in types_found
    assert "wechat_id" in types_found
    assert "password" in types_found
    assert "wechat_webhookurl" in types_found
    assert "dingtalk_webhookurl" in types_found
    assert "feishu_webhookurl" in types_found
    assert "slack_webhookurl" in types_found
    assert "grafana_api_key" in types_found
    assert "grafana_cloud_api_token" in types_found
    assert "grafana_service_account_token" in types_found
    assert "app_key" in types_found
    assert "domain" in types_found

    # Test empty text and large text block splitting
    assert engine.extract_from_text("") == []
    large_text = ("var a = 1;\n" * 10000) + 'var secret_key = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6";\n'
    blocks = engine._split_text_blocks(large_text, block_size=1024, overlap=64)
    assert len(blocks) > 1
    large_matches = engine.extract_from_text(large_text)
    assert any(m[0] == "secret_key" for m in large_matches)

    # Test ignored domains and ignored domain extensions
    dummy_ignored = "Visit https://google.com or https://w3.org or image.png or asset.css"
    ignored_matches = [m for m in engine.extract_from_text(dummy_ignored) if m[0] == "domain"]
    assert len(ignored_matches) == 0


# ============================================================================
# 4. Chunk Parser Tests (chunk_parser.py)
# ============================================================================
def test_chunk_parser_all_scenarios():
    parser = WebpackChunkParser(max_chunks_per_site=50)

    # Empty inputs
    assert parser.extract_from_html("", "https://example.com") == {"scripts": set(), "inline_scripts": [], "next_manifest_urls": set()}
    assert parser.extract_chunks_from_js("", "https://example.com/app.js") == set()
    assert parser.extract_chunks_from_js("short", "https://example.com/app.js") == set()

    # 1. HTML parsing with inline, modulepreload, preload, Next.js __NEXT_DATA__
    html = """
    <!DOCTYPE html>
    <html>
      <head>
        <script src="/static/js/main.js"></script>
        <script src="//cdn.example.com/lib.js"></script>
        <link rel="preload" as="script" href="/static/js/preload.js">
        <link rel="modulepreload" href="/static/js/module.js">
        <link rel="stylesheet" href="/static/css/app.css">
        <script>
          console.log('inline code 1');
        </script>
        <script id="__NEXT_DATA__" type="application/json">
          {"buildId": "BUILD_777", "page": "/user/profile"}
        </script>
        <script id="__NEXT_DATA_CORRUPT__" type="application/json">
          {invalid json}
        </script>
      </head>
      <body><h1>App</h1></body>
    </html>
    """
    html_res = parser.extract_from_html(html, "https://example.com/sub/index.html")
    assert "https://example.com/static/js/main.js" in html_res["scripts"]
    assert "https://cdn.example.com/lib.js" in html_res["scripts"]
    assert "https://example.com/static/js/preload.js" in html_res["scripts"]
    assert "https://example.com/static/js/module.js" in html_res["scripts"]
    assert "https://example.com/_next/static/BUILD_777/_buildManifest.js" in html_res["scripts"]
    assert "https://example.com/_next/static/chunks/pages/user/profile.js" in html_res["scripts"]
    assert len(html_res["inline_scripts"]) >= 1

    # 2. JS parsing: Webpack 3/4/5, Ternary, Vite, Dynamic Import, Next.js manifest, Generic
    js_code = """
    __webpack_require__.p = "/static/js/";
    // Webpack dictionary
    {0: "vendor_chunk", 1: "login_chunk", "admin": "admin_chunk", 3: ""};
    // Webpack 5 ternary
    var x = 101 === e ? "chunk_alpha" : 202 === e ? "chunk_beta" : "chunk_gamma";
    // Vite preload
    __vitePreload(() => ["assets/chunk-vite1.js", "assets/chunk-vite2.js"], true);
    // Dynamic import
    import("./dynamic-report.js");
    importScripts('/workers/sync.js');
    import("data:text/javascript;base64,xxxx");
    // Generic chunks
    var chunk_file = "dashboard.chunk.js";
    var pages_file = "settings.pages.js";
    """
    chunks = parser.extract_chunks_from_js(js_code, "https://example.com/static/js/app.js")
    assert any("vendor_chunk" in c for c in chunks)
    assert any("login_chunk" in c for c in chunks)
    assert any("chunk_alpha" in c for c in chunks)
    assert any("chunk-vite1.js" in c for c in chunks)
    assert any("dynamic-report.js" in c for c in chunks)
    assert any("workers/sync.js" in c for c in chunks)
    assert any("dashboard.chunk.js" in c for c in chunks)
    assert not any("data:" in c for c in chunks)

    # 3. Next.js _buildManifest.js parsing
    manifest_js = """
    self.__BUILD_MANIFEST = {
      "/": ["static/chunks/pages/index-123.js", "static/chunks/main-456.js"],
      "/about": ["static/chunks/pages/about-789.js"]
    };
    """
    next_chunks = parser.extract_chunks_from_js(manifest_js, "https://example.com/_next/static/BUILD_777/_buildManifest.js")
    assert any("index-123.js" in c for c in next_chunks)
    assert any("about-789.js" in c for c in next_chunks)

    # 4. Filter validation: vendor scripts and non-code files
    assert parser._is_valid_script_url("https://example.com/vue.min.js") is False
    assert parser._is_valid_script_url("https://example.com/react-dom.production.min.js") is False
    assert parser._is_valid_script_url("https://example.com/app.js.map") is False
    assert parser._is_valid_script_url("https://example.com/style.css") is False
    assert parser._is_valid_script_url("javascript:void(0)") is False
    assert parser._is_valid_script_url("") is False
    assert parser._is_valid_script_url("https://example.com/app.12345.js") is True


# ============================================================================
# 5. Hunter & Streaming Tests (hunter.py)
# ============================================================================
class FullMockWebHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def do_GET(self):
        self.send_response(200)
        if self.path in ("/", "/index.html"):
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            body = """
            <!DOCTYPE html>
            <html>
            <head>
              <script src="/static/js/app.js"></script>
              <script src="/static/js/latin1.js"></script>
              <script>
                var inline_key = "LTAI5t7eXinline1234567890";
              </script>
            </head>
            <body>
              <p>JWT inline: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c</p>
            </body>
            </html>
            """
            self.wfile.write(body.encode("utf-8"))

        elif self.path in ("/simple1", "/simple2"):
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<html><body><p>LTAI5t7eXsimple12345678</p></body></html>")

        elif self.path == "/static/js/app.js":
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            body = """
            __webpack_require__.p = "/static/js/";
            {10: "auth_chunk", 20: "pay_chunk"};
            var ak = "LTAI5t7eX9876543210zyxwvu";
            """
            self.wfile.write(body.encode("utf-8"))

        elif "auth_chunk" in self.path or "pay_chunk" in self.path:
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            body = 'var qcloud_key = "AKIDa1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6";'
            self.wfile.write(body.encode("utf-8"))

        elif self.path == "/static/js/latin1.js":
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            self.wfile.write(b'var x = "\xe9\xe8\xe0"; var key = "LTAI5t7eXlatin1validkey123";')

        elif self.path == "/static/img/logo.png":
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            self.wfile.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...")

        else:
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            self.wfile.write(b"console.log('empty chunk');")

    def log_message(self, format, *args):
        pass


def test_hunter_full_features_and_concurrency():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FullMockWebHandler)
    server.daemon_threads = True
    port = server.server_address[1]
    server_thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    server_thread.start()

    site_url = f"http://127.0.0.1:{port}"

    try:
        # Test empty input
        assert PyInfoHunter(sites=[]).run() == []
        assert run_wih_python([]) == []

        # Single site scan
        hunter_single = PyInfoHunter(sites=[site_url], concurrency=1)
        records_single = hunter_single.run()
        assert len(records_single) >= 2
        assert any(r.recordType == "Aliyun_AK_ID" for r in records_single)

        # Multi-site scan with proxy emulation
        with patch("app.services.wih.hunter._get_proxy", return_value=None):
            hunter_multi = PyInfoHunter(sites=[f"{site_url}/simple1", f"{site_url}/simple2"], concurrency=2)
            records_multi = hunter_multi.run()
            assert len(records_multi) >= 1

        # Test proxy config getter & exceptions
        with patch("app.services.wih.hunter._get_proxy", return_value="http://127.0.0.1:8080"):
            h_proxy = PyInfoHunter(sites=[f"{site_url}/simple1"])
            assert h_proxy.proxy == "http://127.0.0.1:8080"
            s = h_proxy._create_session()
            assert "http" in s.proxies
            s.close()

        with patch.dict("sys.modules", {"app.config": None}):
            assert _get_proxy() is None

        # Test worker exception in ThreadPoolExecutor
        with patch.object(PyInfoHunter, "_scan_single_site", side_effect=RuntimeError("Worker failed")):
            h_fail = PyInfoHunter(sites=[f"{site_url}/simple1", f"{site_url}/simple2"], concurrency=2)
            assert h_fail.run() == []

        # Direct run_wih_python wrapper
        res_wrapper = run_wih_python([f"{site_url}/simple1"])
        assert len(res_wrapper) >= 1

        # Test _safe_stream_get edge cases (binary types, huge content-length, network exception)
        mock_sess = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "audio/mp3"}
        mock_sess.get.return_value = mock_resp
        assert hunter_single._safe_stream_get(mock_sess, "https://test.com/audio.mp3") is None

        mock_resp.headers = {"Content-Length": str(20 * 1024 * 1024), "Content-Type": "application/javascript"}
        assert hunter_single._safe_stream_get(mock_sess, "https://test.com/huge.js") is None

        mock_sess.get.side_effect = Exception("network down")
        assert hunter_single._safe_stream_get(mock_sess, "https://test.com/error.js") is None

    finally:
        server.shutdown()
        server.server_close()


def test_chunk_parser_extra_branches():
    parser = WebpackChunkParser(max_chunks_per_site=10)
    
    # Webpack dict with ignored keywords or too long
    assert parser._extract_webpack_dict_chunks('{function() { return 1; }}') == set()
    assert parser._extract_webpack_dict_chunks('{window: "123"}') == set()
    assert parser._extract_webpack_dict_chunks('{' + 'a: "1", ' * 1000 + '}') == set()

    # Public path resolution with and without pattern
    assert parser._extract_public_path('__webpack_require__.p = "/custom/path/";', "https://example.com/app.js") == "https://example.com/custom/path/"
    assert parser._extract_public_path('console.log(1);', "https://example.com/static/js/app.js") == "https://example.com/static/js/"

    # Next.js build manifest without page & corrupted JSON
    html_no_page = '<script id="__NEXT_DATA__" type="application/json">{"buildId": "B123"}</script>'
    res1 = parser.extract_from_html(html_no_page, "https://example.com")
    assert "https://example.com/_next/static/B123/_buildManifest.js" in res1["scripts"]

    html_corrupt = '<script id="__NEXT_DATA__" type="application/json">{corrupted}</script>'
    res2 = parser.extract_from_html(html_corrupt, "https://example.com")
    assert len(res2["next_manifest_urls"]) == 0

    # Non-code extensions filtering
    assert parser._is_valid_script_url("https://example.com/file.wasm") is False
    assert parser._is_valid_script_url("https://example.com/file.zip") is False

    # HTML parser exception handling
    assert parser.extract_from_html(12345, "https://example.com")["scripts"] == set()


def test_rule_engine_extra_branches():
    engine = WihRuleEngine()

    # ExcludeRule with string source mismatch
    ex_src = ExcludeRuleMatcher({
        "enabled": True,
        "source": "specific_vendor.js"
    })
    assert ex_src.matches("secret_key", "sec1234567890123456", "https://test.com", "https://test.com/other.js") is False
    assert ex_src.matches("secret_key", "sec1234567890123456", "https://test.com", "https://test.com/specific_vendor.js") is True

    # Builtin secret key varieties
    text_keys = """
    var app_secret = "secret_12345678901234567890";
    var access_secret = "access_12345678901234567890";
    var private_key_str = "privkey_12345678901234567890";
    """
    matches = engine.extract_from_text(text_keys)
    found_keys = {m[1] for m in matches if m[0] == "secret_key"}
    assert "secret_12345678901234567890" in found_keys

    # _get_default_rule_path exception handling
    with patch("app.config.Config", side_effect=Exception("No config")):
        assert os.path.exists(_get_default_rule_path())

    # File open exception during load_rules
    with patch("builtins.open", side_effect=PermissionError("denied")):
        e_err = WihRuleEngine()
        assert len(e_err.rules) >= 4


# ============================================================================
# 6. services.run_wih Entrypoint Tests
# ============================================================================
def test_services_run_wih_entrypoint():
    # 1. Empty sites
    assert run_wih([]) == []

    # 2. Mock success path for run_wih via app.services
    dummy_rec = WihRecord(
        record_type="Aliyun_AK_ID",
        content="LTAI5t7eXtest1234567890",
        source="https://test.com/app.js",
        site="https://test.com",
        fnv_hash="1234567890"
    )
    with patch("app.services.wih.hunter.PyInfoHunter.run", return_value=[dummy_rec]):
        results = run_wih(["https://test.com"])
        assert len(results) == 1
        assert results[0].content == "LTAI5t7eXtest1234567890"
        assert results[0].recordType == "Aliyun_AK_ID"


def test_hunter_exact_lines():
    hunter = PyInfoHunter(sites=["https://example.com"])
    
    # 1. resp.status_code >= 400 (line 81)
    mock_s = MagicMock()
    mock_r = MagicMock()
    mock_r.status_code = 404
    mock_s.get.return_value.__enter__.return_value = mock_r
    assert hunter._safe_stream_get(mock_s, "https://example.com/404") is None

    # 2. Binary / image content-type (line 86)
    mock_r.status_code = 200
    mock_r.headers = {"Content-Type": "image/png"}
    assert hunter._safe_stream_get(mock_s, "https://example.com/logo.png") is None

    # 3. Huge Content-Length (lines 90-91)
    mock_r.headers = {"Content-Type": "application/javascript", "Content-Length": "30000000"}
    assert hunter._safe_stream_get(mock_s, "https://example.com/huge.js") is None

    # 4. Stream iter_content truncation at MAX_JS_SIZE (line 99)
    mock_r.headers = {"Content-Type": "application/javascript"}
    mock_r.iter_content.return_value = [b"a" * (6 * 1024 * 1024)]
    res = hunter._safe_stream_get(mock_s, "https://example.com/huge_stream.js")
    assert res is not None

    # 5. _scan_single_site when html_text is None (line 121)
    with patch.object(hunter, "_safe_stream_get", return_value=None):
        assert hunter._scan_single_site("https://example.com") == []

    # 6. Chunk expansion queue and duplicate script skip (line 174) & consecutive errors limit (179-184)
    hunter.max_chunks = 10
    with patch.object(hunter.chunk_parser, "extract_from_html", return_value={
        "scripts": [
            "https://example.com/app.js",
            "https://example.com/app.js",
            "https://example.com/err1.js",
            "https://example.com/err2.js",
            "https://example.com/err3.js",
            "https://example.com/err4.js",
            "https://example.com/err5.js",
            "https://example.com/err6.js",
        ],
        "inline_scripts": []
    }):
        with patch.object(hunter, "_safe_stream_get") as mock_get:
            mock_get.side_effect = [
                '<html></html>',
                '__webpack_require__.p = "/static/"; {1: "chunk1"}; var k = "LTAI5t7eX1234567890abcdef";',
                None, None, None, None, None, None, None, None
            ]
            recs = hunter._scan_single_site("https://example.com")
            assert len(recs) >= 1

    # 7. _scan_single_site unexpected exception handling (lines 213-214)
    with patch.object(hunter.chunk_parser, "extract_from_html", side_effect=RuntimeError("DOM crash")):
        with patch.object(hunter, "_safe_stream_get", return_value="<html></html>"):
            assert hunter._scan_single_site("https://example.com") == []


def test_rule_engine_exact_lines():
    import importlib
    import app.services.wih.rule_engine

    # 1. Test top-level ImportError fallback for yaml (lines 16-17)
    with patch.dict("sys.modules", {"yaml": None}):
        importlib.reload(app.services.wih.rule_engine)
    # Restore normal module state
    importlib.reload(app.services.wih.rule_engine)

    engine = WihRuleEngine()

    # 2. _get_default_rule_path branches (lines 26-29)
    # 2a. Config has non-existent WIH_RULE_PATH -> fallback to basedir
    with patch("app.config.Config.WIH_RULE_PATH", "/non/existent/path/wih_rules.yml"):
        p1 = _get_default_rule_path()
        assert p1.endswith("wih_rules.yml")

    # 2b. Config import raises Exception -> hits except Exception (lines 26-27)
    with patch.dict("sys.modules", {"app.config": None}):
        p2 = _get_default_rule_path()
        assert p2.endswith("wih_rules.yml")

    # 3. ExcludeRuleMatcher string source mismatch (line 109)
    ex = ExcludeRuleMatcher({"enabled": True, "source": "main.js"})
    assert ex.matches("domain", "foo.com", "https://test.com", "https://test.com/other.js") is False

    # 4. yaml is None fallback path (line 187)
    with patch("app.services.wih.rule_engine.yaml", None):
        e_fallback = WihRuleEngine()
        assert len(e_fallback.rules) >= 4

    # 5. is_excluded match returns True (line 230)
    assert engine.is_excluded("secret_key", "sec1234567890123456", "https://cc.163.com", "https://cc.163.com/app.js") is True

    # 6. Domain filters: ignored ext (line 253), short length / no dot (line 257)
    with patch("app.services.wih.rule_engine.BUILTIN_DOMAIN_PATTERN", MagicMock(findall=MagicMock(return_value=["foo.js", "localhost", "a.b", "valid-site.com"]))):
        domains_extracted = [m[1] for m in engine.extract_from_text("dummy") if m[0] == "domain"]
        assert "valid-site.com" in domains_extracted

    # 7. Custom regex with empty cleaned match (line 285)
    custom_rule = {"id": "wechat_appid", "compiled": MagicMock(findall=MagicMock(return_value=[""]))}
    engine.rules.append(custom_rule)
    engine.extract_from_text("dummy")


def test_chunk_parser_exact_lines():
    parser = WebpackChunkParser(max_chunks_per_site=50)

    # 1. Next.js __NEXT_DATA__ json loads exception (lines 138-142)
    bad_html = '<script id="__NEXT_DATA__">{"corrupted": json</script>'
    res = parser.extract_from_html(bad_html, "https://example.com")
    assert len(res["next_manifest_urls"]) == 0

    # 2. Webpack dictionary filter condition (line 217)
    res_dict = parser._extract_webpack_dict_chunks('{function() {}, window: 1}')
    assert res_dict == set()


if __name__ == "__main__":
    print("Executing WIH 100% Full Coverage Test Suite...")
    test_fnv1a_complete()
    print("✅ 1. FNV-1a Parity & Types: PASSED")
    test_verifier_jwt()
    test_verifier_cloud_aks()
    print("✅ 2. Verifiers (JWT, AliCloud, TencentCloud): PASSED")
    test_rule_engine_exclude_rules_and_matching()
    test_rule_engine_fallback_yaml_and_error_handling()
    test_rule_engine_all_rule_types()
    test_rule_engine_extra_branches()
    test_rule_engine_exact_lines()
    print("✅ 3. Rule Engine & 100% Rules/Excludes: PASSED")
    test_chunk_parser_all_scenarios()
    test_chunk_parser_extra_branches()
    test_chunk_parser_exact_lines()
    print("✅ 4. Webpack/Vite/Next.js/HTML Chunk Parser: PASSED")
    test_hunter_full_features_and_concurrency()
    test_hunter_exact_lines()
    print("✅ 5. Hunter, Streaming, OOM Cutoff & Concurrency: PASSED")
    test_services_run_wih_entrypoint()
    print("✅ 6. services.run_wih Unified Entrypoint: PASSED")
    print("\n🎉 ALL FULL COVERAGE TESTS PASSED SUCCESSFULLY!")
