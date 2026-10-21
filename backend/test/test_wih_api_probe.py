"""隔离验证接口响应采集；真实 HTTP 测试仅访问本机临时端口。"""

import ast
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest import mock

import mongomock
import requests
from urllib3.exceptions import ReadTimeoutError

import test_wih_api_discovery as discovery
from test_http_status_filter import execute_nodes


probe_module = discovery.load_file("api_probe_under_test", discovery.WIH / "api_probe.py")
BASE = "https://app.example.test/"


def candidate(url=BASE + "api/data", method="GET"):
    return {"url": url, "method": method}


class Response:
    def __init__(self, status=200, body=b'{"ok":true}', headers=None, failure=None):
        self.status_code = status
        self.headers = requests.structures.CaseInsensitiveDict(headers or {"Content-Type": "application/json"})
        self.body, self.failure, self.closed = body, failure, False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def iter_content(self, chunk_size):
        yield self.body
        if self.failure:
            raise self.failure


class Session:
    def __init__(self, responses):
        self.responses, self.calls, self.closed = responses, [], False
        self.cookies = {"fixture": "must-clear"}

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        assert not self.cookies
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        self.cookies["fixture"] = "do-not-forward"
        return response

    def close(self):
        self.closed = True


class ProbeTests(unittest.TestCase):
    def runner(self, responses):
        session = Session(responses)
        probe = probe_module.ApiProbe(BASE, lambda: session)
        self.addCleanup(probe.close)
        return probe, session

    def test_all_http_statuses_are_observations_including_access_denied_and_missing(self):
        for code in [200, 204, 301, 401, 403, 404, 500]:
            with self.subTest(code=code):
                response = Response(code)
                probe, session = self.runner([response])
                result = probe.collect(candidate())
                self.assertEqual(result["state"], "responded")
                self.assertEqual(result["status_code"], code)
                self.assertEqual(result["body_preview"], '{"ok":true}')
                self.assertTrue(response.closed)
                options = session.calls[0][2]
                self.assertFalse(options["allow_redirects"])
                self.assertNotIn("data", options)
                self.assertNotIn("headers", options)

    def test_unresolved_unsafe_methods_and_other_origins_never_open_a_session(self):
        factory = mock.Mock(side_effect=AssertionError("不得请求"))
        probe = probe_module.ApiProbe(BASE, factory)
        for url, method, reason in [
            (None, "GET", "unresolved_url"), (BASE, "POST", "unsupported_method"),
            (BASE, "DELETE", "unsupported_method"), (BASE, "PUT", "unsupported_method"),
            (BASE, "PATCH", "unsupported_method"), (BASE, "OPTIONS", "unsupported_method"),
            (BASE, "UNKNOWN", "unsupported_method"),
            ("https://other.example.test/api", "GET", "outside_origin"),
            ("https://app.example.test:8443/api", "GET", "outside_origin"),
            ("http://app.example.test/api", "GET", "outside_origin"),
            ("https://user:pass@app.example.test/api", "GET", "unresolved_url"),
            ("https://app.example.test\\@other.example.test/api", "GET", "unresolved_url"),
            ("javascript:alert(1)", "GET", "unresolved_url"),
            ("https://app.example.test:0/api", "GET", "unresolved_url"),
        ]:
            with self.subTest(url=url, method=method):
                self.assertEqual(probe.collect(candidate(url, method)), {"state": "skipped", "reason": reason})
        factory.assert_not_called()

    def test_normalizes_the_sent_host_and_default_port_before_origin_comparison(self):
        probe, session = self.runner([Response(), Response()])
        self.assertEqual(probe.collect(candidate("https://APP.EXAMPLE.TEST:443/a"))["state"], "responded")
        self.assertEqual(probe.collect(candidate("https://%61pp.example.test/b"))["state"], "responded")
        self.assertEqual(len(session.calls), 2)
        self.assertIn("app.example.test", session.calls[1][1])

    def test_cross_origin_redirect_is_recorded_but_never_followed(self):
        for location in ["https://other.example.test/private", "//app.example.test:8443/private",
                         "http://app.example.test/private", "https://user:pass@app.example.test/private",
                         "http://[invalid"]:
            with self.subTest(location=location):
                probe, session = self.runner([Response(302, headers={"Location": location})])
                result = probe.collect(candidate())
                self.assertEqual(result["state"], "responded")
                self.assertEqual(result["status_code"], 302)
                self.assertIn(result["redirect_stop"], {"outside_origin", "invalid_redirect"})
                self.assertEqual(len(session.calls), 1)
                self.assertNotIn("location", result["headers"])

    def test_same_origin_redirects_keep_method_and_close_responses(self):
        responses = [Response(303, headers={"Location": "/api/final"}), Response()]
        probe, session = self.runner(responses.copy())
        result = probe.collect(candidate(method="HEAD"))
        self.assertEqual([call[0] for call in session.calls], ["HEAD", "HEAD"])
        self.assertEqual(result["url"], BASE + "api/final")
        self.assertEqual(result["body_skipped"], "head")
        self.assertTrue(all(response.closed for response in responses))
        self.assertEqual(result["redirects"], [{"url": BASE + "api/data", "status_code": 303}])

    def test_redirect_loop_limit_and_exclusion_stop_requests(self):
        for responses, excluded, expected, count in [
            ([Response(302, headers={"Location": "/api/data"})], lambda url: False, "redirect_loop", 1),
            ([Response(302, headers={"Location": "/one"}), Response(302, headers={"Location": "/two"})],
             lambda url: False, "redirect_limit", 2),
            ([Response(302, headers={"Location": "/excluded"})],
             lambda url: url.endswith("/excluded"), "excluded", 1),
        ]:
            with self.subTest(expected=expected), mock.patch.object(probe_module, "MAX_REDIRECTS", 1):
                probe, session = self.runner(responses)
                result = probe.collect(candidate(), excluded)
                self.assertEqual(result["redirect_stop"], expected)
                self.assertEqual(len(session.calls), count)

    def test_connection_timeout_and_body_failure_are_distinct_from_no_candidates(self):
        for error, kind in [(requests.Timeout("fixture-secret"), "timeout"),
                            (requests.ConnectionError("fixture-secret"), "connection_error")]:
            probe, session = self.runner([error])
            result = probe.collect(candidate())
            self.assertEqual(result["state"], "error")
            self.assertEqual(result["error"], kind)
            self.assertNotIn("fixture-secret", str(result))
        probe, session = self.runner([Response(failure=requests.ConnectionError("fixture-secret"))])
        result = probe.collect(candidate())
        self.assertEqual(result["state"], "responded")
        self.assertEqual(result["body_preview"], '{"ok":true}')
        self.assertEqual(result["body_error"], "connection_error")
        self.assertTrue(result["body_truncated"])

    def test_failed_redirect_retains_last_http_observation_and_failed_hop(self):
        probe, session = self.runner([Response(302, headers={"Location": "/final"}), requests.Timeout()])
        result = probe.collect(candidate())
        self.assertEqual(result["state"], "responded")
        self.assertEqual(result["status_code"], 302)
        self.assertEqual(result["url"], BASE + "api/data")
        self.assertEqual(result["last_attempt_url"], BASE + "final")
        self.assertEqual(result["error"], "timeout")

    def test_stream_timeout_wrapped_by_requests_keeps_timeout_classification(self):
        error = requests.ConnectionError(ReadTimeoutError(None, "/fixture", "fixture-secret"))
        probe, _ = self.runner([Response(failure=error)])
        result = probe.collect(candidate())
        self.assertEqual(result["state"], "responded")
        self.assertEqual(result["body_error"], "timeout")
        self.assertNotIn("fixture-secret", str(result))

    def test_text_capture_is_bounded_decoded_and_filters_sensitive_headers(self):
        response = Response(body=b"x" * (probe_module.MAX_BODY_BYTES + 5000), headers={
            "Content-Type": "text/plain; charset=invalid-fixture-charset", "Server": "fixture",
            "Set-Cookie": "fixture-secret", "Authorization": "fixture-secret", "X-Token": "fixture-secret",
        })
        probe, session = self.runner([response])
        result = probe.collect(candidate())
        self.assertEqual(result["body_bytes"], probe_module.MAX_BODY_BYTES)
        self.assertEqual(len(result["body_preview"]), probe_module.MAX_BODY_BYTES)
        self.assertTrue(result["body_truncated"])
        self.assertNotIn("fixture-secret", str(result))
        probe, _ = self.runner([Response(body="正常响应".encode("gb18030"),
                                        headers={"Content-Type": "text/plain; charset=gb18030"})])
        self.assertEqual(probe.collect(candidate())["body_preview"], "正常响应")

    def test_binary_and_head_responses_are_not_read(self):
        for method, headers, reason in [("HEAD", {"Content-Type": "text/plain"}, "head"),
                                        ("GET", {"Content-Type": "application/octet-stream"}, "non_text")]:
            response = Response(headers=headers)
            response.iter_content = mock.Mock(side_effect=AssertionError("不应读取正文"))
            probe, _ = self.runner([response])
            self.assertEqual(probe.collect(candidate(method=method))["body_skipped"], reason)
            response.iter_content.assert_not_called()

    def test_quota_cache_and_time_budget_bound_additional_requests(self):
        with mock.patch.object(probe_module, "MAX_PROBES_PER_SITE", 1):
            probe, session = self.runner([Response()])
            self.assertEqual(probe.collect(candidate()), probe.collect(candidate()))
            self.assertEqual(probe.collect(candidate(BASE + "other"))["reason"], "site_quota")
            self.assertEqual(len(session.calls), 1)
        probe, session = self.runner([])
        with mock.patch.object(probe_module.time, "monotonic", return_value=probe.started + 61):
            self.assertEqual(probe.collect(candidate())["reason"], "site_budget")
        self.assertEqual(session.calls, [])

    def test_body_time_budget_preserves_headers_and_marks_incomplete_capture(self):
        probe, _ = self.runner([Response()])
        # init 后：配额检查、开始、请求前、正文检查、结束。
        with mock.patch.object(probe_module.time, "monotonic", side_effect=[0, 0, 0, 11, 11]):
            result = probe.collect(candidate())
        self.assertEqual(result["state"], "responded")
        self.assertEqual(result["body_error"], "time_budget")
        self.assertTrue(result["body_truncated"])


class LocalHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calls, cls.trap_calls = [], []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_HEAD(self):
                self.do_GET()

            def do_GET(self):
                cls.calls.append((self.command, self.path, dict(self.headers)))
                status, content_type, body, extra = 200, "application/json", '{"message":"正常"}', {}
                if self.path == "/page":
                    content_type = "text/html"
                    body = '''<script>
fetch("/api/data"); fetch("./api/data");
fetch("/api/denied"); fetch("/api/missing");
fetch("/api/redirect"); fetch("/api/external"); fetch("/api/large");
fetch("/api/head", {method:"HEAD"}); fetch("/api/data", {method:"POST", body:"fixture"});
axios.get("/unresolved"); fetch("/unknown", runtimeOptions);
</script>'''
                elif self.path == "/api/denied":
                    status = 403
                elif self.path == "/api/missing":
                    status = 404
                elif self.path == "/api/redirect":
                    status, extra = 302, {"Location": "/api/data"}
                elif self.path == "/api/external":
                    status, extra = 302, {"Location": cls.trap_url + "/must-not-request"}
                elif self.path == "/api/large":
                    body = "x" * (probe_module.MAX_BODY_BYTES + 5000)
                raw = body.encode()
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Set-Cookie", "fixture=must-not-forward")
                for key, value in extra.items():
                    self.send_header(key, value)
                self.end_headers()
                if self.command != "HEAD":
                    try:
                        self.wfile.write(raw)
                    except (ConnectionError, OSError):
                        pass

        class Trap(Handler):
            def do_GET(self):
                cls.trap_calls.append(self.path)
                super().do_GET()

        cls.servers = [ThreadingHTTPServer(("127.0.0.1", 0), handler) for handler in (Handler, Trap)]
        cls.base, cls.trap_url = ["http://127.0.0.1:{}".format(server.server_port) for server in cls.servers]
        for server in cls.servers:
            server.daemon_threads = True
            threading.Thread(target=server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for server in cls.servers:
            server.shutdown()
            server.server_close()

    def scan(self, config):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.yml"
            path.write_text(config)
            runner = discovery.hunter.PyInfoHunter([self.base + "/page"], rule_path=str(path))
            runner.proxy = None
            return runner, runner.run()

    def test_real_local_http_pipeline_collects_responses_without_auth_or_unsafe_requests(self):
        self.calls.clear()
        self.trap_calls.clear()
        # 即便存在 netrc，独立接口会话也不能隐式携带认证。
        with tempfile.TemporaryDirectory() as directory:
            netrc = Path(directory) / "netrc"
            netrc.write_text("machine 127.0.0.1 login fixture password fixture-secret\n")
            with mock.patch.dict("os.environ", {"NETRC": str(netrc)}):
                runner, records = self.scan("rules:\n  - id: api_endpoint\n    enabled: true\n    probe: true\n")
        data = [r.api_request for r in records if r.recordType == "api_endpoint"]
        self.assertEqual(len(data), 11)
        denied = next(r for r in data if r["path"] == "/api/denied")
        self.assertTrue(denied["verified"])
        self.assertEqual(denied["probe"]["status_code"], 403)
        self.assertEqual(denied["probe"]["body_preview"], '{"message":"正常"}')
        self.assertEqual(next(r for r in data if r["path"] == "/api/missing")["probe"]["status_code"], 404)
        self.assertEqual(next(r for r in data if r["path"] == "/api/external")["probe"]["redirect_stop"], "outside_origin")
        self.assertTrue(next(r for r in data if r["path"] == "/api/large")["probe"]["body_truncated"])
        self.assertTrue(all(method in {"GET", "HEAD"} for method, _, _ in self.calls))
        self.assertTrue(all("Cookie" not in headers and "Authorization" not in headers for _, _, headers in self.calls))
        self.assertFalse(self.trap_calls)
        self.assertFalse(any(path in {"/unknown", "/unresolved"} for _, path, _ in self.calls))
        # 两种原始路径解析到同一 URL，只产生一次直接探测；重定向另有一次。
        self.assertEqual(sum(path == "/api/data" for _, path, _ in self.calls), 2)

    def test_probe_requires_explicit_true_and_enabled_builtin(self):
        for config in [
            "rules:\n  - id: api_endpoint\n    enabled: true\n",
            "rules:\n  - id: api_endpoint\n    enabled: true\n    probe: false\n",
            "rules:\n  - id: api_endpoint\n    enabled: true\n    probe: 'true'\n",
            "rules:\n  - id: api_endpoint\n    enabled: false\n    probe: true\n",
            "rules:\n  - id: api_endpoint\n    enabled: true\n    probe: true\n    pattern: '/api/data'\n",
        ]:
            with self.subTest(config=config):
                self.calls.clear()
                runner, records = self.scan(config)
                self.assertFalse(runner.api_probe_enabled)
                self.assertEqual([path for _, path, _ in self.calls], ["/page"])

    def test_yaml_fallback_retains_probe_flag_and_default_stays_off(self):
        engine_module = discovery.hunter.WihRuleEngine.load_rules.__globals__
        with mock.patch.dict(engine_module, yaml=None):
            runner, records = self.scan("rules:\n  - id: api_endpoint\n    enabled: true\n    probe: true\n")
            self.assertTrue(runner.api_probe_enabled)
            self.assertTrue(any(r.api_request.get("verified") for r in records))
            self.calls.clear()
            runner, _ = self.scan("rules:\n  - id: api_endpoint\n    enabled: true\n    probe: 'true'\n")
            self.assertFalse(runner.api_probe_enabled)
            self.assertEqual([path for _, path, _ in self.calls], ["/page"])
        runner = discovery.hunter.PyInfoHunter([], rule_path=str(discovery.BACKEND / "app/dicts/wih_rules.yml"))
        self.assertFalse(runner.api_probe_enabled)

    def test_redirects_honor_existing_content_exclusions(self):
        self.calls.clear()
        runner, records = self.scan('''rules:
  - id: api_endpoint
    enabled: true
    probe: true
exclude_rules:
  - id: api_endpoint
    content: /api/data
    source_tag: inline
    enabled: true
''')
        self.assertFalse(any(path == "/api/data" for _, path, _ in self.calls))
        redirect = next(r for r in records if r.api_request["path"] == "/api/redirect")
        self.assertEqual(redirect.api_request["probe"]["redirect_stop"], "excluded")

    def test_requests_does_not_eagerly_consume_redirect_body_before_scope_checks(self):
        session = probe_module.ApiProbeSession()
        session.trust_env = False
        self.addCleanup(session.close)
        with session.get(self.base + "/api/external", stream=True, allow_redirects=False, timeout=3) as response:
            self.assertEqual(response.status_code, 302)
            self.assertFalse(response._content_consumed)
            self.assertIsNone(response.next)


class HunterFailureTests(unittest.TestCase):
    def test_session_failure_keeps_static_candidates_and_legacy_findings(self):
        fixture = discovery.HunterTests()
        self.addCleanup(fixture.doCleanups)
        runner = fixture.runner()
        runner.api_probe_enabled = True
        with mock.patch.object(runner, "_create_api_session", side_effect=RuntimeError("fixture-secret")):
            records = fixture.scan(runner)
        endpoints = [r for r in records if r.recordType == "api_endpoint"]
        self.assertEqual(len(endpoints), 3)
        self.assertTrue(any(r.content == "retained.example.com" for r in records))
        self.assertTrue(any(r.recordType == "path" for r in records))
        self.assertTrue(all(not r.api_request["verified"] for r in endpoints))
        self.assertTrue(any(r.api_request["probe"]["state"] == "error" for r in endpoints))
        self.assertNotIn("fixture-secret", str([r.dump_json() for r in records]))

    def test_cross_origin_document_base_keeps_candidates_without_opening_probe_session(self):
        fixture = discovery.HunterTests()
        self.addCleanup(fixture.doCleanups)
        runner = fixture.runner()
        runner.api_probe_enabled = True
        with mock.patch.object(runner, "_create_api_session", side_effect=AssertionError("不得请求")) as factory:
            records = fixture.scan(runner, html=(
                '<base href="https://other.example.test/api/"><script>fetch("./data")</script>'
                '<script src="https://cdn.example.test/app.js"></script>'
            ))
        factory.assert_not_called()
        endpoints = [r for r in records if r.recordType == "api_endpoint"]
        self.assertEqual(len(endpoints), 3)
        self.assertEqual({r.api_request["probe"]["reason"] for r in endpoints},
                         {"outside_origin", "unsupported_method"})


class PersistenceTests(unittest.TestCase):
    def test_existing_api_candidate_refreshes_observation_without_duplicate_notification(self):
        database = mongomock.MongoClient().arl

        class Collection:
            def find(self, *args):
                return database.asset_wih.find(*args)

            def bulk_write(self, operations, **kwargs):
                for operation in operations:
                    database.asset_wih.update_one(operation._filter, operation._doc, upsert=operation._upsert)

        env = {"utils": types.SimpleNamespace(conn_db=lambda name: Collection(), curr_date_obj=lambda: "now")}
        execute_nodes(discovery.BACKEND / "app/services/asset_wih_monitor.py", env,
                      lambda node: isinstance(node, ast.ClassDef) and node.name == "AssetWihMonitor")
        monitor = env["AssetWihMonitor"]("scope-a")
        old = discovery.record_module.WihRecord("api_endpoint", "GET /api/data", "app.js", BASE, "api",
                                               api_request=dict(candidate(), path="/api/data", line=1, verified=False))
        database.asset_wih.insert_one(dict(old.dump_json(), scope_id="scope-a", save_date="old"))
        database.asset_wih.insert_one(dict(old.dump_json(), scope_id="scope-b", save_date="old"))
        response = copy.deepcopy(old)
        response.source = "new.js"
        response.api_request["line"] = 20
        response.api_request.update(verified=True, probe={"state": "responded", "status_code": 403})
        self.assertEqual(monitor._batch_save_wih_results([response]), [])
        current = database.asset_wih.find_one({"scope_id": "scope-a"})
        self.assertEqual(current["api_request"]["probe"]["status_code"], 403)
        self.assertEqual(current["save_date"], "old")
        self.assertEqual(current["update_date"], "now")
        self.assertEqual(current["source"], "app.js")
        self.assertEqual(current["api_request"]["line"], 1)
        self.assertFalse(database.asset_wih.find_one({"scope_id": "scope-b"})["api_request"]["verified"])
        self.assertEqual(database.asset_wih.count_documents({}), 2)
        # 后续仅静态识别不应清除上一次主动采集的观测。
        monitor._batch_save_wih_results([old])
        self.assertEqual(database.asset_wih.find_one({"scope_id": "scope-a"})["api_request"], current["api_request"])

    def test_normal_task_persists_response_metadata_under_its_own_namespace(self):
        record = discovery.record_module.WihRecord("api_endpoint", "GET /api/data", "app.js", BASE, "api",
                                                  api_request=dict(candidate(), verified=True, probe={
                                                      "state": "responded", "status_code": 200,
                                                      "body_preview": '{"fixture":true}',
                                                  }))
        database = mongomock.MongoClient().arl
        env = {
            "services": types.SimpleNamespace(run_wih=lambda sites: [record]),
            "utils": types.SimpleNamespace(safe_insert_asset_many=lambda name, keys, items:
                                           database[name].insert_many(items)),
        }
        tree = ast.parse((discovery.BACKEND / "app/services/commonTask.py").read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "WebSiteFetch")
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "run_web_info_hunter")
        exec(compile(ast.Module(body=[method], type_ignores=[]), "commonTask.py", "exec"), env)
        task = types.SimpleNamespace(sites=[BASE], task_id="task-a", wih_record_set=set(),
                                     add_wih_domain_set=mock.Mock())
        env["run_web_info_hunter"](task)
        item = database.wih.find_one({"task_id": "task-a"})
        self.assertEqual(item["api_request"], record.api_request)
        self.assertEqual(database.wih.count_documents({}), 1)
        self.assertEqual(database.asset_wih.count_documents({}), 0)


if __name__ == "__main__":
    unittest.main()
