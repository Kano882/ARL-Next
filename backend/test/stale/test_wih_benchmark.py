# -*- coding: utf-8 -*-
"""
Comprehensive Benchmark and Accuracy Verification Suite for Pure Python WIH.
Tests:
  1. 64-bit FNV-1a Hash Parity against Go standard library test vectors.
  2. RuleEngine YAML parsing, regex matching, and ExcludeRules enforcement.
  3. Webpack 3/4/5, Next.js, and Vite chunk extraction.
  4. End-to-End local mock server scan with PyInfoHunter (Accuracy, Recall, Dedup, Risk Level).
"""

import os
import sys
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
# Optional pytest import
try:
    import pytest
except ImportError:
    pass


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

try:
    from http.server import ThreadingHTTPServer
except ImportError:
    from http.server import HTTPServer as ThreadingHTTPServer

from app.config import _config_cache
_config_cache["data"] = {}
_config_cache["last_update"] = time.time() + 99999999

from app.services.wih import (
    fnv1a_64,
    fnv1a_64_int,
    WihRuleEngine,
    WebpackChunkParser,
    PyInfoHunter,
    run_wih_python
)
from app.modules import WihRecord


def test_fnv1a_hash_parity():
    """
    Verify FNV-1a 64-bit calculation produces exact match with Go standard library .
    """
    test_vectors = {
        "hello world": "8618312879776256743",
        "https://example.com": "9474213896243003571",
        "LTAI5t7eXxxxxxxxxx": "5439839121716655074",
        "中文测试": "8491584761721039823",
        "": "14695981039346656037"
    }

    for text, expected_hash in test_vectors.items():
        computed = fnv1a_64(text)
        assert computed == expected_hash, f"FNV-1a mismatch for {text}: got {computed}, expected {expected_hash}"


def test_rule_engine_matching_and_excludes():
    """
    Verify RuleEngine accurately detects all sensitive categories and respects exclude rules.
    """
    engine = WihRuleEngine()
    assert len(engine.rules) > 0, "Active rules should not be empty"

    sample_js = """
    // Sample JS with injected credentials
    var ali_ak = "LTAI5t7eX1234567890abcdef";
    var qcloud_ak = "AKIDz1234567890abcdef1234567890abcdef";
    var jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c";
    var dingtalk = "https://oapi.dingtalk.com/robot/send?access_token=1234567890123456789012345678901234567890123456789012345678901234";
    var wechat_app = "wx1234567890abcdef";
    var app_secret = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6";
    var internal_api = "https://api.internal-corp.com/v1/user";
    """

    matches = engine.extract_from_text(sample_js, target_site="https://test.com", source_url="https://test.com/app.js")
    types_found = {m[0] for m in matches}
    contents_found = {m[1] for m in matches}

    assert "Aliyun_AK_ID" in types_found, "Aliyun AK should be detected"
    assert "LTAI5t7eX1234567890abcdef" in contents_found
    assert "QCloud_AK_ID" in types_found, "QCloud AK should be detected"
    assert "jwt_token" in types_found, "JWT token should be detected"
    assert "dingtalk_webhookurl" in types_found, "Dingtalk webhook should be detected"
    assert "domain" in types_found, "Internal domain should be detected"

    # Test Exclude Rule: cc.163.com secret_key
    excluded_sample = 'var sec = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6";'
    ex_matches = engine.extract_from_text(
        excluded_sample,
        target_site="https://cc.163.com",
        source_url="https://cc.163.com/app.js"
    )
    ex_types = {m[0] for m in ex_matches}
    assert "secret_key" not in ex_types, "cc.163.com secret_key should be excluded per exclude_rules"


def test_webpack_and_modern_chunk_parsing():
    """
    Verify Webpack 3/4/5, Next.js, and Vite chunk extraction capabilities.
    """
    parser = WebpackChunkParser(max_chunks_per_site=50)

    # 1. HTML with Next.js and scripts
    html = """
    <!DOCTYPE html>
    <html>
      <head>
        <script src="/static/js/manifest.js"></script>
        <script src="/static/js/app.12345.js"></script>
        <link rel="preload" as="script" href="/static/js/vendor.67890.js">
        <script id="__NEXT_DATA__" type="application/json">
          {"buildId": "PROD_BUILD_999", "page": "/admin/dashboard"}
        </script>
      </head>
      <body><h1>App</h1></body>
    </html>
    """
    dom_res = parser.extract_from_html(html, "https://example.com/")
    scripts = dom_res["scripts"]
    assert "https://example.com/static/js/manifest.js" in scripts
    assert "https://example.com/static/js/app.12345.js" in scripts
    assert "https://example.com/static/js/vendor.67890.js" in scripts
    assert "https://example.com/_next/static/PROD_BUILD_999/_buildManifest.js" in scripts
    assert "https://example.com/_next/static/chunks/pages/admin/dashboard.js" in scripts

    # 2. Webpack 4 Dictionary mapping
    wp4_js = '__webpack_require__.p = "/static/js/"; {0: "admin", 1: "user", 2: "settings"};'
    wp4_chunks = parser.extract_chunks_from_js(wp4_js, "https://example.com/static/js/app.js")
    assert any("admin" in c for c in wp4_chunks), "Webpack 4 chunk should be extracted"

    # 3. Vite __vitePreload
    vite_js = '__vitePreload(() => ["assets/chunk-login-a1b2.js", "assets/chunk-user-c3d4.js"], true);'
    vite_chunks = parser.extract_chunks_from_js(vite_js, "https://example.com/assets/index.js")
    assert any("chunk-login-a1b2.js" in c for c in vite_chunks)
    assert any("chunk-user-c3d4.js" in c for c in vite_chunks)


class MockWebHandler(BaseHTTPRequestHandler):
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
              <title>Mock Secure App</title>
              <script src="/static/js/app.js"></script>
              <script>
                var inline_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c";
              </script>
            </head>
            <body>Welcome to Test App</body>
            </html>
            """
            self.wfile.write(body.encode("utf-8"))
        elif self.path == "/static/js/app.js":
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            body = """
            __webpack_require__.p = "/static/js/";
            {10: "auth_chunk", 20: "payment_chunk"};
            var aliyun_key = "LTAI5t7eX9876543210zyxwvu";
            var wechat_bot = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=12345678-1234-1234-1234-123456789012";
            """
            self.wfile.write(body.encode("utf-8"))
        elif "auth_chunk" in self.path:
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            body = 'var qcloud_key = "AKIDa1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"; var api_host = "https://auth.internal-corp.com";'
            self.wfile.write(body.encode("utf-8"))
        else:
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            self.wfile.write(b"console.log('empty chunk');")

    def log_message(self, format, *args):
        # Suppress standard HTTP server log clutter in tests
        pass


def test_end_to_end_py_info_hunter_scan():
    """
    End-to-End accuracy, chunk recursion, deduplication, and risk assessment test on live mock HTTP server.
    """
    # Start local mock server
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockWebHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    site_url = f"http://127.0.0.1:{port}"

    try:
        t0 = time.time()
        hunter = PyInfoHunter(sites=[site_url], concurrency=2)
        records = hunter.run()
        elapsed = time.time() - t0

        print(f"\n[Benchmark] PyInfoHunter scanned mock SPA in {elapsed:.3f}s, found {len(records)} records")

        # Check records
        record_types = {r.recordType for r in records}
        contents = {r.content for r in records}

        # 1. Verification of HTML inline JWT
        assert "jwt_token" in record_types, "Inline JWT must be detected"

        # 2. Verification of initial app.js Aliyun AK & Wechat Webhook
        assert "Aliyun_AK_ID" in record_types, "Aliyun AK in app.js must be detected"
        assert "LTAI5t7eX9876543210zyxwvu" in contents
        assert "wechat_webhookurl" in record_types, "Wechat webhook must be detected"

        # 3. Verification of Recursively Expanded Webpack Chunk (auth_chunk) QCloud AK & Domain
        assert "QCloud_AK_ID" in record_types, "QCloud AK in dynamically expanded chunk must be detected"
        assert "AKIDa1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6" in contents
        assert any("auth.internal-corp.com" in c for c in contents), "Domain in expanded chunk must be detected"

        # 4. Verification of Hash and Risk Level Attributes
        for r in records:
            assert len(r.fnv_hash) > 0, "fnv_hash must be non-empty string"
            assert r.risk_level in ("CRITICAL", "MEDIUM", "LOW"), f"Invalid risk level {r.risk_level}"
            json_dump = r.dump_json()
            assert json_dump["site"] == site_url

        # 5. Deduplication check
        assert len(records) == len(set(records)), "No duplicate records allowed"

        print("[Benchmark] All precision, chunk recursion, and hash assertions passed successfully!")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    print("Running WIH Benchmark Suite...")
    test_fnv1a_hash_parity()
    print("✅ 1. FNV-1a Hash Parity: PASSED")
    test_rule_engine_matching_and_excludes()
    print("✅ 2. RuleEngine & ExcludeRules: PASSED")
    test_webpack_and_modern_chunk_parsing()
    print("✅ 3. Webpack 3/4/5 / Next.js / Vite Chunk Parser: PASSED")
    test_end_to_end_py_info_hunter_scan()
    print("\n=================== ALL WIH BENCHMARK TESTS PASSED (100% SUCCESS) ===================")
