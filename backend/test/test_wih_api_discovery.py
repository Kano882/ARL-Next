"""离线验证接口候选提取、WIH 扫描及导出；所有 HTTP 响应均为本地内存样例。"""

import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


BACKEND = Path(__file__).resolve().parents[1]
WIH = BACKEND / "app/services/wih"


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


api = load_file("api_extractor_under_test", WIH / "api_extractor.py")
record_module = load_file("api_record_under_test", BACKEND / "app/modules/wihRecord.py")
export = load_file("api_export_under_test", BACKEND / "app/utils/wih_export.py")


def load_hunter():
    package = types.ModuleType("isolated_api_wih")
    package.__path__ = [str(WIH)]
    app = types.ModuleType("app")
    utils = types.ModuleType("app.utils")
    modules = types.ModuleType("app.modules")
    modules.WihRecord = record_module.WihRecord
    from concurrent.futures import ThreadPoolExecutor
    utils.ContextAwareThreadPoolExecutor = ThreadPoolExecutor
    with mock.patch.dict(sys.modules, {
        "app": app, "app.utils": utils, "app.modules": modules, "isolated_api_wih": package,
    }):
        return load_file("isolated_api_wih.hunter", WIH / "hunter.py")


hunter = load_hunter()
BASE = "https://app.example.test/portal/index.html"


class ExtractionTests(unittest.TestCase):
    def extract(self, source, base=BASE):
        return api.extract_api_requests(source, base)

    def test_fetch_methods_and_document_relative_paths(self):
        records = self.extract('''fetch("/api/users");
window.fetch("./orders", {method: "post", body: JSON.stringify({id: 1})});
globalThis.fetch("../health?full=1#section", {"method": "HEAD"});''')
        self.assertEqual([(r["method"], r["path"], r["url"], r["line"]) for r in records], [
            ("GET", "/api/users", "https://app.example.test/api/users", 1),
            ("POST", "./orders", "https://app.example.test/portal/orders", 2),
            ("HEAD", "../health?full=1#section", "https://app.example.test/health?full=1", 3),
        ])
        self.assertTrue(all(r["verified"] is False for r in records))

    def test_axios_base_url_uses_concatenation_instead_of_urljoin(self):
        records = self.extract('''axios.get("/users", {baseURL: "https://api.example.test/v1"});
axios.post("users", {method: "DELETE"}, {baseURL: "https://api.example.test/v1/"});
axios.request({url: "/users", method: "patch", baseURL: "/v2"});
axios({url: "/users", method: "delete", baseURL: "https://api.example.test/v3"});
axios("/users", {baseURL: "https://api.example.test/v4", method: "options"});''')
        self.assertEqual([(r["method"], r["url"]) for r in records], [
            ("GET", "https://api.example.test/v1/users"),
            ("POST", "https://api.example.test/v1/users"),
            ("PATCH", "https://app.example.test/v2/users"),
            ("DELETE", "https://api.example.test/v3/users"),
            ("OPTIONS", "https://api.example.test/v4/users"),
        ])

    def test_axios_method_alias_overrides_method_in_config(self):
        record = self.extract('axios.get("/users", {method: "POST", baseURL: "/api"})')[0]
        self.assertEqual(record["method"], "GET")

    def test_uncertain_options_and_base_urls_preserve_literal_path(self):
        records = self.extract('''fetch("/fetch", runtimeOptions);
fetch("/spread", {...runtimeOptions});
axios.get("/global-defaults");
axios.get("/dynamic-base", {baseURL: runtimeBase});
axios.get("/opaque", runtimeConfig);
axios.get("https://api.example.test/absolute", {allowAbsoluteUrls: false, baseURL: "/proxy"});''')
        self.assertEqual(len(records), 6)
        self.assertEqual([r["method"] for r in records[:2]], ["UNKNOWN", "UNKNOWN"])
        self.assertTrue(all(r["url"] is None for r in records[2:]))
        self.assertEqual(records[3]["path"], "/dynamic-base")

    def test_comments_strings_regex_and_arbitrary_fetch_methods_are_not_calls(self):
        source = r'''// fetch("/comment")
/* axios.get("/comment") */
const example = 'fetch("/quoted")';
const regex = /fetch\("fake"\)/g;
if (ok) /axios.get\("fake"\)/.test(text);
object.fetch("/custom"); object.axios.get("/custom");
object.window.fetch("/custom"); object?.fetch("/custom");
"window".fetch("/custom");
fetch("/real");'''
        self.assertEqual([r["path"] for r in self.extract(source)], ["/real"])

    def test_static_templates_and_escapes_without_evaluating_dynamic_expressions(self):
        quote = chr(96)
        source = 'fetch(' + quote + '/static' + quote + ');'
        source += r'''fetch("\x2fapi\u002fusers"); fetch("https:\/\/api.example.test\/health");'''
        source += 'fetch(' + quote + '/users/' + chr(36) + '{id}' + quote + ');'
        source += 'fetch("/users/" + id); fetch(variable);'
        source += 'const x = ' + quote + 'text ' + chr(36) + '{' + quote + 'nested' + quote + '}' + quote + ';'
        source += 'fetch("/after");'
        self.assertEqual([r["path"] for r in self.extract(source)],
                         ["/static", "/api/users", "https://api.example.test/health", "/after"])

    def test_division_does_not_swallow_subsequent_request_calls(self):
        source = r'''const value = total / 2; fetch("/after-division");
const next = compute() / 2; fetch("/after-call");
if (ready) /fetch\("fake"\)/.test(text); fetch("/after-regex");
const escaped = /[a\/b]/g; fetch("/after-class");
const value2 = count++ / 2; fetch("/after-increment");
const value3 = object.if(value) / 2; fetch("/after-member");'''
        self.assertEqual([r["path"] for r in self.extract(source)],
                         ["/after-division", "/after-call", "/after-regex", "/after-class",
                          "/after-increment", "/after-member"])
        quote = chr(96)
        source = 'const example=' + quote + 'value ' + chr(36) + '{total / 2}' + quote + ';fetch("/after-template");'
        self.assertEqual([r["path"] for r in self.extract(source)], ["/after-template"])

    def test_duplicate_config_keys_spreads_and_dynamic_urls_are_not_inferred(self):
        source = '''axios({url: "/first", url: "/last"});
axios({url: "/candidate", ...runtime});
axios.request({url: prefix + "/dynamic", method: "GET"});
fetch("/literal", {method: runtimeMethod});'''
        records = self.extract(source)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["path"], "/literal")
        self.assertEqual(records[0]["method"], "UNKNOWN")

    def test_valid_absolute_and_protocol_relative_urls_preserve_ports(self):
        records = self.extract('''fetch("https://api.example.test:8443/a?q=1");
axios.head("http://[2001:db8::1]:8080/status");
fetch("//api.example.test/status");''')
        self.assertEqual([r["url"] for r in records], [
            "https://api.example.test:8443/a?q=1", "http://[2001:db8::1]:8080/status",
            "https://api.example.test/status",
        ])

    def test_missing_base_does_not_invent_an_origin(self):
        records = self.extract('fetch("/relative"); fetch("//api.example.test/relative");', base=None)
        self.assertEqual([r["url"] for r in records], [None, None])
        self.assertEqual(records[0]["path"], "/relative")

    def test_invalid_or_non_http_urls_are_skipped(self):
        source = '''fetch("javascript:alert(1)"); fetch("data:text/plain,example");
fetch("http://[invalid]/x"); fetch("https://api.example.test:99999/x");
fetch("https://user:password@example.test/x"); fetch("/bad path"); fetch("/good");'''
        self.assertEqual([r["path"] for r in self.extract(source)], ["/good"])

    def test_duplicates_keep_distinct_http_methods(self):
        source = 'fetch("/same"); fetch("/same"); fetch("/same", {method:"POST"});'
        self.assertEqual([r["method"] for r in self.extract(source)], ["GET", "POST"])

    def test_limits_do_not_execute_large_or_incomplete_calls(self):
        source = ";".join('fetch("/api/{}")'.format(i) for i in range(250))
        self.assertEqual(len(api.extract_api_requests(source, BASE)), api.MAX_API_REQUESTS)
        self.assertEqual(len(api.extract_api_requests(source, BASE, limit=3)), 3)
        self.assertEqual(api.extract_api_requests(source, BASE, limit=0), [])
        self.assertEqual(self.extract('fetch("/incomplete"'), [])
        self.assertEqual(self.extract('fetch("/large", {' + 'x:"value",' * 200 + '});'), [])

    def test_document_base_uses_first_href_and_rejects_non_http_bases(self):
        html = '<BASE href="/v1/?a=1&amp;b=2"><base href="https://wrong.example.test/">'
        self.assertEqual(api.document_base_url(html, BASE), "https://app.example.test/v1/?a=1&b=2")
        self.assertIsNone(api.document_base_url('<base href="data:text/plain,example">', BASE))
        self.assertEqual(api.document_base_url('<base target="_blank"><base href="/v2/">', BASE),
                         "https://app.example.test/v2/")

    def test_large_strings_and_malformed_regex_do_not_hide_the_next_statement(self):
        source = 'const large="' + "x" * 200000 + '";\n'
        source += "const malformed = /" + "[" * 200000 + ';\nfetch("/after");'
        self.assertEqual([r["path"] for r in self.extract(source)], ["/after"])
        quote = chr(96)
        source = quote + chr(36) + "{" + " " * 200000 + "1}" + quote + '; fetch("/after-template");'
        self.assertEqual([r["path"] for r in self.extract(source)], ["/after-template"])

    def test_token_budget_and_overlong_endpoint_literals_are_bounded(self):
        with mock.patch.object(api, "MAX_TOKENS", 20):
            self.assertEqual(self.extract('const x=1;' * 30 + 'fetch("/later");'), [])
        self.assertEqual(self.extract('fetch("/' + "x" * api.MAX_LITERAL_CHARS + '");'), [])


class _Response:
    status_code = 200
    headers = {"Content-Type": "text/html"}

    def __init__(self, text, url):
        self.text, self.url = text, url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, **kwargs):
        yield self.text.encode("utf-8")


class _Session:
    def __init__(self, pages):
        self.pages, self.urls, self.closed = pages, [], False

    def get(self, url, **kwargs):
        self.urls.append(url)
        if url not in self.pages:
            raise AssertionError("候选接口不应被请求: " + url)
        return self.pages[url]

    def close(self):
        self.closed = True


class HunterTests(unittest.TestCase):
    def runner(self, enabled=True, extra=""):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "rules.yml"
        path.write_text('''rules:
  - id: domain
    enabled: true
  - id: path
    enabled: true
  - id: api_endpoint
    enabled: ''' + str(enabled).lower() + "\n" + extra)
        return hunter.PyInfoHunter([BASE], rule_path=str(path))

    def scan(self, runner, html=None, code=None):
        html = html or '<script>fetch("/inline")</script><script src="https://cdn.example.test/app.js"></script>'
        code = code or 'fetch("./users"); axios.post("/users"); const domain="retained.example.com";'
        session = _Session({
            BASE: _Response(html, "https://app.example.test/redirected/index.html"),
            "https://cdn.example.test/app.js": _Response(code, "https://cdn.example.test/app.js"),
        })
        with mock.patch.object(runner, "_create_session", return_value=session):
            records = runner.run()
        self.assertEqual(session.urls, [BASE, "https://cdn.example.test/app.js"])
        self.assertTrue(session.closed)
        return records

    def test_fetches_only_existing_html_js_and_uses_redirected_document_not_cdn(self):
        records = self.scan(self.runner())
        endpoints = [r.dump_json() for r in records if r.recordType == "api_endpoint"]
        self.assertEqual(len(endpoints), 3)
        fetch = next(r for r in endpoints if r["api_request"]["path"] == "./users")
        self.assertEqual(fetch["api_request"]["url"], "https://app.example.test/redirected/users")
        self.assertEqual(fetch["source"], "https://cdn.example.test/app.js [script:line 1]")
        self.assertEqual(fetch["risk_level"], "LOW")
        self.assertFalse(fetch["api_request"]["verified"])
        self.assertIn("GET https://app.example.test/redirected/users [path: ./users]", fetch["content"])
        self.assertTrue(any(r.recordType == "domain" and r.content == "retained.example.com" for r in records))
        self.assertTrue(any(r.recordType == "path" and r.content == "./users" for r in records))

    def test_html_base_href_applies_to_inline_and_external_scripts(self):
        records = self.scan(self.runner(), html=(
            '<base href="https://backend.example.test/v1/"><script>fetch("./inline")</script>'
            '<script src="https://cdn.example.test/app.js"></script>'
        ))
        urls = {r.api_request["url"] for r in records if r.recordType == "api_endpoint"}
        self.assertIn("https://backend.example.test/v1/inline", urls)
        self.assertIn("https://backend.example.test/v1/users", urls)

    def test_disabled_feature_preserves_old_record_set(self):
        records = self.scan(self.runner(enabled=False))
        self.assertFalse(any(r.recordType == "api_endpoint" for r in records))
        self.assertTrue(any(r.recordType == "path" for r in records))
        self.assertTrue(all("api_request" not in r.dump_json() for r in records))
        default = hunter.WihRuleEngine(str(BACKEND / "app/dicts/wih_rules.yml"))
        self.assertNotIn("api_endpoint", {r["id"] for r in default.rules})

    def test_same_path_with_different_methods_survives_existing_hash_deduplication(self):
        records = self.scan(self.runner(), code='fetch("/same"); fetch("/same", {method:"POST"});')
        endpoints = [r for r in records if r.recordType == "api_endpoint" and r.api_request["path"] == "/same"]
        self.assertEqual({r.api_request["method"] for r in endpoints}, {"GET", "POST"})
        self.assertEqual(len({r.fnv_hash for r in endpoints}), 2)
        self.assertTrue(any(r.recordType == "path" and r.content == "/same" for r in records))

    def test_unresolved_paths_on_different_sites_keep_distinct_persistence_hashes(self):
        runner = self.runner()
        other = "https://other.example.test/"
        runner.sites = [BASE, other]
        html = '<script>axios.get("/same-unresolved-path");</script>'
        pages = {url: _Response(html, url) for url in runner.sites}
        with mock.patch.object(runner, "_create_session", side_effect=lambda: _Session(pages)):
            records = [r for r in runner.run() if r.recordType == "api_endpoint"]
        self.assertEqual({r.site for r in records}, {BASE, other})
        # 普通任务还会按 fnv_hash 汇总，接口候选的哈希必须保留站点归属。
        self.assertEqual(len({r.fnv_hash for r in records}), 2)
        self.assertTrue(all(r.api_request["url"] is None for r in records))

    def test_exclusion_rules_apply_to_api_requests_with_original_source_tags(self):
        runner = self.runner(extra='''exclude_rules:
  - id: api_endpoint
    content: /inline
    source_tag: inline
    enabled: true
''')
        records = self.scan(runner)
        self.assertFalse(any(r.recordType == "api_endpoint" and r.api_request["path"] == "/inline" for r in records))
        self.assertTrue(any(r.recordType == "path" and r.content == "/inline" for r in records))

    def test_quota_and_extractor_failure_do_not_stop_legacy_rules_or_js_fetches(self):
        code = ";".join('fetch("/api/{}")'.format(i) for i in range(10))
        code += '; const domain="retained.example.com";'
        with mock.patch.object(hunter, "MAX_API_REQUESTS", 3):
            records = self.scan(self.runner(), code=code)
        self.assertEqual(sum(r.recordType == "api_endpoint" for r in records), 3)
        self.assertTrue(any(r.content == "retained.example.com" for r in records))
        with mock.patch.object(hunter, "extract_api_requests", side_effect=ValueError("fixture parser failure")):
            records = self.scan(self.runner(), code=code)
        self.assertTrue(any(r.content == "retained.example.com" for r in records))
        self.assertTrue(any(r.recordType == "path" and r.content == "/api/9" for r in records))

    def test_document_base_failure_keeps_existing_scan_and_unresolved_candidates(self):
        with mock.patch.object(hunter, "document_base_url", side_effect=ValueError("fixture base failure")):
            records = self.scan(self.runner())
        self.assertTrue(any(r.content == "retained.example.com" for r in records))
        endpoints = [r for r in records if r.recordType == "api_endpoint"]
        self.assertEqual(len(endpoints), 3)
        self.assertTrue(all(r.api_request["url"] is None for r in endpoints))

    def test_legacy_serialization_and_export_are_unchanged(self):
        record = record_module.WihRecord("domain", "api.example.test", "app.js", BASE, "123")
        self.assertEqual(record.dump_json(), {
            "record_type": "domain", "content": "api.example.test", "source": "app.js",
            "site": BASE, "fnv_hash": "123", "risk_level": "LOW",
        })
        self.assertEqual(export.format_wih_export(record.dump_json()),
                         BASE + " [domain] api.example.test")
        self.assertEqual(export.format_wih_export({"recordType": "legacy", "content": "value"}),
                         "unknown_site [legacy] value")
        legacy = record_module.WihRecord("api_endpoint", "/legacy", "old.js", BASE, "legacy")
        self.assertEqual(legacy.risk_level, "MEDIUM")
        self.assertEqual(export.format_wih_export(legacy.dump_json()), BASE + " [api_endpoint] /legacy")

    def test_api_export_contains_method_raw_path_resolved_url_and_source(self):
        records = self.scan(self.runner())
        record = next(r for r in records if r.recordType == "api_endpoint" and r.api_request["path"] == "./users")
        text = export.format_wih_export(record.dump_json())
        for value in ["api_endpoint", "GET", "./users", "https://app.example.test/redirected/users",
                      "https://cdn.example.test/app.js", "script:line 1"]:
            self.assertIn(value, text)


if __name__ == "__main__":
    unittest.main()
