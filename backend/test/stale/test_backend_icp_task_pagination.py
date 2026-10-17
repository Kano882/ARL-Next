from bson import ObjectId

from backend.app.tasks import icp as icp_task_module


class FakeCollection:
    def __init__(self):
        self.inserted = []
        self.updated = []

    def insert_one(self, item):
        self.inserted.append(dict(item))

    def update_one(self, query, update):
        self.updated.append((query, update))


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_run_icp_task_fetches_all_pages(monkeypatch):
    task_id = "687000000000000000000001"
    page_payloads = {
        1: {
            "code": 200,
            "params": {
                "pageNum": 1,
                "pages": 3,
                "list": [{"domain": "a.example"}, {"domain": "b.example"}],
            },
        },
        2: {
            "code": 200,
            "params": {
                "pageNum": 2,
                "pages": 3,
                "list": [{"domain": "c.example"}],
            },
        },
        3: {
            "code": 200,
            "params": {
                "pageNum": 3,
                "pages": 3,
                "list": [{"domain": "d.example"}],
            },
        },
    }
    request_urls = []
    collections = {
        "icp_task": FakeCollection(),
        "icp_asset": FakeCollection(),
    }

    def fake_get(url, timeout=30):
        request_urls.append(url)
        page_num = 1
        if "pageNum=" in url:
            page_num = int(url.split("pageNum=")[1].split("&")[0])
        return FakeResponse(page_payloads[page_num])

    def fake_conn_db(name):
        return collections[name]

    monkeypatch.setattr(icp_task_module.requests, "get", fake_get)
    monkeypatch.setattr(icp_task_module.utils, "conn_db", fake_conn_db)
    monkeypatch.setattr(icp_task_module.utils, "curr_date", lambda: "2026-07-03 00:00:00")

    icp_task_module.run_icp_task(
        {
            "task_id": task_id,
            "target": "北京抖音信息服务有限公司",
            "query_type": ["web"],
        }
    )

    assert request_urls == [
        "http://icp_query:16181/query/web?search=北京抖音信息服务有限公司",
        "http://icp_query:16181/query/web?search=北京抖音信息服务有限公司&pageNum=2",
        "http://icp_query:16181/query/web?search=北京抖音信息服务有限公司&pageNum=3",
    ]
    assert len(collections["icp_asset"].inserted) == 4
    assert all(item["task_id"] == task_id for item in collections["icp_asset"].inserted)
    assert all(item["query_type"] == "web" for item in collections["icp_asset"].inserted)

    assert collections["icp_task"].updated[0] == (
        {"_id": ObjectId(task_id)},
        {"$set": {"status": "running"}},
    )
    assert collections["icp_task"].updated[-1] == (
        {"_id": ObjectId(task_id)},
        {
            "$set": {
                "status": "done",
                "end_time": "2026-07-03 00:00:00",
                "statistic": {
                    "asset_cnt": 4,
                    "web_cnt": 4,
                    "app_cnt": 0,
                    "mapp_cnt": 0,
                    "kapp_cnt": 0,
                },
            }
        },
    )
