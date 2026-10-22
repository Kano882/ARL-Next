"""用真实路由、解析器和内存数据库验证接口候选的筛选及单项、批量导出。"""

import ast
import functools
from pathlib import Path
import types
import unittest

from flask import Flask, request
from flask_restx import Api, Namespace
import mongomock

from test_http_status_filter import assigned, execute_nodes, load_base
import test_wih_api_discovery as discovery


BACKEND = Path(__file__).resolve().parents[1]
BASE = discovery.BASE


class ApiRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().arl
        self.app = Flask(__name__)
        rest = Api(self.app, prefix="/api")
        self.env = load_base(self.db.__getitem__)
        auth_env = {
            "functools": functools, "Config": types.SimpleNamespace(AUTH=True),
            "user_login_header": lambda: request.headers.get("Token") == "fixture-token",
        }
        execute_nodes(BACKEND / "app/utils/user.py", auth_env,
                      lambda node: isinstance(node, ast.FunctionDef) and node.name == "auth")
        self.env.update(auth=auth_env["auth"], utils=types.SimpleNamespace(
            conn_db=self.db.__getitem__,
            build_ret=lambda error, data: dict(error, data=data),
        ), ErrorMsg=types.SimpleNamespace(Success={"code": 200}), request=request)
        for filename, namespace in [
            ("wih.py", "wih"), ("assetWih.py", "asset_wih"), ("batchExport.py", "batch_export"),
        ]:
            self.env["ns"] = Namespace(namespace)
            execute_nodes(BACKEND / "app/routes" / filename, self.env, lambda node:
                          isinstance(node, (ast.FunctionDef, ast.ClassDef))
                          or assigned(node, ("base_search_fields", "delete_wih_fields", "delete_asset_wih_fields",
                                            "batch_export_fields", "scope_batch_export_fields"))
                          or isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                          and isinstance(node.value.func, ast.Attribute)
                          and isinstance(node.value.func.value, ast.Name)
                          and node.value.func.value.id == "base_search_fields")
            rest.add_namespace(self.env["ns"])
        self.client = self.app.test_client()
        self.headers = {"Token": "fixture-token"}
        # 执行实际提取和序列化，再将结果放入隔离的内存数据库。
        fixture = discovery.HunterTests()
        self.addCleanup(fixture.doCleanups)
        records = fixture.scan(fixture.runner(), code=(
            'fetch("/users"); fetch("/users", {method:"POST"}); const retained="retained.example.com";'
        ))
        self.original = [record.dump_json() for record in records]
        for item in self.original:
            self.db.wih.insert_one(dict(item, task_id="task-a"))
            self.db.asset_wih.insert_one(dict(item, scope_id="scope-a"))
        other = dict(next(item for item in self.original if item["record_type"] == "api_endpoint"),
                     content="GET https://other.example.test/private")
        self.db.wih.insert_one(dict(other, task_id="task-b"))
        self.db.asset_wih.insert_one(dict(other, scope_id="scope-b"))

    def get(self, path, **query):
        return self.client.get("/api/" + path, query_string=query, headers=self.headers)

    def test_list_and_export_share_type_method_and_task_or_scope_filters(self):
        for namespace, key, scope in [("wih", "task_id", "task-a"), ("asset_wih", "scope_id", "scope-a")]:
            with self.subTest(namespace=namespace):
                query = {key: scope, "record_type__eq": "api_endpoint", "content": "POST"}
                response = self.get(namespace + "/", **query)
                self.assertEqual(response.status_code, 200)
                body = response.get_json()
                self.assertEqual(body["total"], 1)
                record = body["items"][0]
                self.assertEqual(record["api_request"]["method"], "POST")
                self.assertEqual(record["api_request"]["path"], "/users")
                self.assertEqual(record["api_request"]["url"], "https://app.example.test/users")
                self.assertFalse(record["api_request"]["verified"])
                output = self.get(namespace + "/export/", **query)
                self.assertEqual(output.status_code, 200)
                self.assertEqual(output.get_data(as_text=True).splitlines(), [discovery.export.format_wih_export(record)])

    def test_source_and_unresolved_paths_are_queryable_without_inventing_urls(self):
        # 模拟新旧记录混合的已有集合，缺少 api_request 的历史记录仍可查询。
        self.db.wih.insert_one({
            "task_id": "task-a", "record_type": "api_endpoint", "content": "GET /unknown",
            "source": "https://cdn.example.test/old.js", "site": BASE,
        })
        query = {"task_id": "task-a", "record_type": "api_endpoint", "content": "/unknown"}
        body = self.get("wih/", **query).get_json()
        self.assertEqual(body["total"], 1)
        self.assertNotIn("api_request", body["items"][0])
        self.assertEqual(self.get("wih/", task_id="task-a", source="https://cdn.example.test/old.js").get_json()["total"], 1)
        output = self.get("wih/export/", **query).get_data(as_text=True)
        self.assertIn("GET /unknown", output)
        self.assertEqual(output.splitlines(), [BASE + " [api_endpoint] GET /unknown"])

    def test_batch_task_and_scope_exports_preserve_api_source_and_legacy_format(self):
        for namespace, payload in [
            ("wih", {"task_id": ["task-a"]}),
            ("asset_wih", {"scope_id": ["scope-a"]}),
        ]:
            with self.subTest(namespace=namespace):
                response = self.client.post("/api/batch_export/" + namespace + "/",
                                            json=payload, headers=self.headers)
                self.assertEqual(response.status_code, 200)
                rows = set(response.get_data(as_text=True).splitlines())
                self.assertEqual(rows, {discovery.export.format_wih_export(item) for item in self.original})
                self.assertTrue(any("[source:" in row for row in rows))
                self.assertFalse(any("other.example.test" in row for row in rows))

    def test_new_records_remain_behind_existing_authentication(self):
        for path in ["wih/", "asset_wih/", "wih/export/", "asset_wih/export/"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get("/api/" + path).get_json()["code"], 401)
        for path, payload in [("wih", {"task_id": ["task-a"]}), ("asset_wih", {"scope_id": ["scope-a"]})]:
            response = self.client.post("/api/batch_export/" + path + "/", json=payload)
            self.assertEqual(response.get_json()["code"], 401)

    def test_captured_response_is_available_as_json_without_executing_or_exporting_body(self):
        observation = {
            "state": "responded", "status_code": 403, "headers": {"content-type": "text/html"},
            "body_preview": "<script>fixture()</script>", "body_bytes": 26, "body_truncated": False,
        }
        for name, key, value in [("wih", "task_id", "task-a"), ("asset_wih", "scope_id", "scope-a")]:
            collection = self.db[name]
            item = collection.find_one({key: value, "record_type": "api_endpoint"})
            item["api_request"].update(verified=True, probe=observation)
            collection.replace_one({"_id": item["_id"]}, item)
            query = {key: value, "record_type__eq": "api_endpoint", "content": item["content"]}
            response = self.get(name + "/", **query)
            self.assertTrue(response.content_type.startswith("application/json"))
            captured = next(record for record in response.get_json()["items"] if "probe" in record["api_request"])
            self.assertEqual(captured["api_request"]["probe"], observation)
            self.assertTrue(captured["api_request"]["verified"])
            self.assertNotIn("<script>", self.get(name + "/export/", **query).get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
