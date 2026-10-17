import sys
import os
import pytest
import asyncio

from bson import ObjectId

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from osint_service.clients import job_runner


class FakeAsyncCollection:
    def __init__(self):
        self.docs = []
        self.inserted = []
        self.updated = []

    async def insert_one(self, item):
        doc = dict(item)
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        self.inserted.append(doc)
        self.docs.append(doc)
        return type("InsertResult", (), {"inserted_id": doc["_id"]})()

    async def update_one(self, query, update):
        self.updated.append((query, update))
        # 模拟 Mongo 原子更新语义：把 $set 落到 docs，否则 waiting→running
        # 认领后状态永不翻转，循环首检即判"任务被手动停止"直接返回。
        matched = 0
        for doc in self.docs:
            hit = True
            for k, v in query.items():
                if doc.get(k) != v:
                    hit = False
                    break
            if hit:
                matched += 1
                for sk, sv in (update.get("$set") or {}).items():
                    doc[sk] = sv
        return type("UpdateResult", (), {"matched_count": matched, "modified_count": matched})()

    async def find_one(self, query, projection=None):
        for doc in self.docs:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                return doc
        return None


@pytest.fixture
def mock_tyc_env(monkeypatch):
    collections = {
        "icp_task": FakeAsyncCollection(),
        "icp_asset": FakeAsyncCollection(),
        "syslog": FakeAsyncCollection(),
    }
    fake_db = collections

    monkeypatch.setattr(job_runner, "db", fake_db)

    async def fake_sleep(*args, **kwargs):
        pass

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    return collections


class _BaseMockClient:
    """测试替身上限：补齐 run_tyc_job 强依赖的接口，默认返回空。"""

    def __init__(self, *args, **kwargs):
        pass

    async def get_company_name(self, gid):
        return ""

    async def get_icp_record_list(self, gid):
        return []

    async def get_app_list(self, gid):
        return []

    async def get_wechat_list(self, gid):
        return []

    async def get_weibo_list(self, gid):
        return []

    async def get_mini_program_list(self, gid):
        return []


def test_tyc_invest_strict_mode_drops_empty_and_low_ratio(mock_tyc_env, monkeypatch):
    """测试严格模式：持股比例 < 50% 或为空/破折号时一律丢弃，仅保留 >= 50% 的子公司"""
    task_id = str(ObjectId())
    mock_tyc_env["icp_task"].docs.append({"_id": ObjectId(task_id), "status": "waiting"})

    class MockClient(_BaseMockClient):
        async def get_invest_list(self, gid):
            return [
                {"id": "c1", "name": "达标控股公司", "percent": "60.00%", "amount": "1000万人民币"},
                {"id": "c2", "name": "低比例子公司", "percent": "30%", "amount": "500万人民币"},
                {"id": "c3", "name": "无比例子公司", "percent": None, "amount": "200万人民币"},
                {"id": "c4", "name": "破折号比例子公司", "percent": "-", "amount": "100万人民币"},
            ]

    monkeypatch.setattr(job_runner, "AsyncTycClient", MockClient)

    options = {
        "task_id": task_id,
        "gid": "test_root_gid",
        "depth": 1,
        "invest_ratio": 50,
        "query_type": ["invest"],
        "tyc_id": "test_tyc_id",
        "tyc_token": "test_token"
    }

    asyncio.run(job_runner.run_tyc_job(options))

    # 验证仅达标公司入库
    inserted_assets = mock_tyc_env["icp_asset"].inserted
    assert len(inserted_assets) == 1
    assert inserted_assets[0]["name"] == "达标控股公司"
    assert inserted_assets[0]["percent_num"] == 60.0
    assert inserted_assets[0]["amount_num"] == 1000.0

    # 验证统计信息
    last_update = mock_tyc_env["icp_task"].updated[-1][1]["$set"]
    assert last_update["status"] == "done"
    assert last_update["statistic"]["invest_cnt"] == 1
    assert last_update["statistic"]["asset_cnt"] == 1

    # 验证日志中记录了严格丢弃明细
    syslog_msgs = [doc["message"] for doc in mock_tyc_env["syslog"].inserted]
    assert any("无具体投资比例数据，在最低投资比例限制下已被丢弃: 无比例子公司, 破折号比例子公司" in msg for msg in syslog_msgs)


def test_tyc_invest_unrestricted_mode_keeps_all(mock_tyc_env, monkeypatch):
    """测试无限制模式（invest_ratio=0）：无论是否有比例或比例多少，全部放行入库"""
    task_id = str(ObjectId())
    mock_tyc_env["icp_task"].docs.append({"_id": ObjectId(task_id), "status": "waiting"})

    class MockClient(_BaseMockClient):
        async def get_invest_list(self, gid):
            return [
                {"id": "c1", "name": "微小参股", "percent": "5%", "amount": "50万"},
                {"id": "c2", "name": "无比例公司", "percent": None, "amount": "100万"},
                {"id": "c3", "name": "控股公司", "percent": "90%", "amount": "1000万"},
            ]

    monkeypatch.setattr(job_runner, "AsyncTycClient", MockClient)

    options = {
        "task_id": task_id,
        "gid": "test_root_gid",
        "depth": 1,
        "invest_ratio": 0,
        "query_type": ["invest"],
        "tyc_id": "test_tyc_id",
        "tyc_token": "test_token"
    }

    asyncio.run(job_runner.run_tyc_job(options))

    # 验证全部入库
    inserted_assets = mock_tyc_env["icp_asset"].inserted
    assert len(inserted_assets) == 3
    assert {a["name"] for a in inserted_assets} == {"微小参股", "无比例公司", "控股公司"}

    last_update = mock_tyc_env["icp_task"].updated[-1][1]["$set"]
    assert last_update["statistic"]["invest_cnt"] == 3


def test_tyc_invest_multi_depth_strict_recursion(mock_tyc_env, monkeypatch):
    """测试多层递归与严格过滤阻断：未达标或无比例的子公司不会进入第 2 层查询"""
    task_id = str(ObjectId())
    mock_tyc_env["icp_task"].docs.append({"_id": ObjectId(task_id), "status": "waiting"})

    queried_gids = []

    class MockClient(_BaseMockClient):
        async def get_invest_list(self, gid):
            queried_gids.append(gid)
            if gid == "root_100":
                return [
                    {"id": "sub_201", "name": "第一层达标公司", "percent": "70%"},
                    {"id": "sub_202", "name": "第一层未达标公司", "percent": "20%"},
                    {"id": "sub_203", "name": "第一层无比例公司", "percent": None},
                ]
            elif gid == "sub_201":
                return [
                    {"id": "sub_301", "name": "第二层孙公司达标", "percent": "80%"},
                    {"id": "sub_302", "name": "第二层孙公司无比例", "percent": None},
                ]
            return []

    monkeypatch.setattr(job_runner, "AsyncTycClient", MockClient)

    options = {
        "task_id": task_id,
        "gid": "root_100",
        "depth": 2,
        "invest_ratio": 50,
        "query_type": ["invest"],
        "tyc_id": "test_tyc_id",
        "tyc_token": "test_token"
    }

    asyncio.run(job_runner.run_tyc_job(options))

    # 验证递归路径：只查询了 root_100 和 sub_201，sub_202 与 sub_203 被丢弃未递归
    assert queried_gids == ["root_100", "sub_201"]

    inserted_names = [a["name"] for a in mock_tyc_env["icp_asset"].inserted]
    assert inserted_names == ["第一层达标公司", "第二层孙公司达标"]


def test_tyc_job_depth_zero_fallback_to_one(mock_tyc_env, monkeypatch):
    """测试 depth=0 兜底防护：自动修正为 1，确保至少查询目标公司自身资产"""
    task_id = str(ObjectId())
    mock_tyc_env["icp_task"].docs.append({"_id": ObjectId(task_id), "status": "waiting"})

    queried_gids = []

    class MockClient(_BaseMockClient):
        async def get_invest_list(self, gid):
            queried_gids.append(gid)
            return [{"id": "sub_1", "name": "子公司1", "percent": "100%"}]

    monkeypatch.setattr(job_runner, "AsyncTycClient", MockClient)

    options = {
        "task_id": task_id,
        "gid": "target_company_gid",
        "depth": 0,  # 传入 0
        "invest_ratio": 50,
        "query_type": ["invest"],
        "tyc_id": "test_tyc_id",
        "tyc_token": "test_token"
    }

    asyncio.run(job_runner.run_tyc_job(options))

    # 验证即使传入 depth=0，也兜底执行了第 1 层查询
    assert queried_gids == ["target_company_gid"]
    assert len(mock_tyc_env["icp_asset"].inserted) == 1


def test_tyc_invest_numeric_and_formatted_amounts(mock_tyc_env, monkeypatch):
    """测试金额逗号格式解析及数字型 percent 兼容性"""
    task_id = str(ObjectId())
    mock_tyc_env["icp_task"].docs.append({"_id": ObjectId(task_id), "status": "waiting"})

    class MockClient(_BaseMockClient):
        async def get_invest_list(self, gid):
            return [
                {"id": "c1", "name": "逗号金额企业", "percent": 75.5, "amount": "1,234.56 万元人民币"},
            ]

    monkeypatch.setattr(job_runner, "AsyncTycClient", MockClient)

    options = {
        "task_id": task_id,
        "gid": "root_gid",
        "depth": 1,
        "invest_ratio": 50,
        "query_type": ["invest"],
        "tyc_id": "test_tyc_id",
        "tyc_token": "test_token"
    }

    asyncio.run(job_runner.run_tyc_job(options))

    inserted_assets = mock_tyc_env["icp_asset"].inserted
    assert len(inserted_assets) == 1
    assert inserted_assets[0]["percent_num"] == 75.5
    assert inserted_assets[0]["amount_num"] == 1234.56


def test_tyc_job_circular_reference_prevention(mock_tyc_env, monkeypatch):
    """测试循环持股防环机制：A投资B，B又投资A，必须防止死循环与重复抓取"""
    task_id = str(ObjectId())
    mock_tyc_env["icp_task"].docs.append({"_id": ObjectId(task_id), "status": "waiting"})

    queried_gids = []

    class MockClient(_BaseMockClient):
        async def get_invest_list(self, gid):
            queried_gids.append(gid)
            if gid == "comp_A":
                # A 投资 B
                return [{"id": "comp_B", "name": "子公司B", "percent": 100}]
            elif gid == "comp_B":
                # B 投资 A (循环持股) 及 C
                return [
                    {"id": "comp_A", "name": "母公司A", "percent": 100},
                    {"id": "comp_C", "name": "孙公司C", "percent": 100}
                ]
            return []

    monkeypatch.setattr(job_runner, "AsyncTycClient", MockClient)

    options = {
        "task_id": task_id,
        "gid": "comp_A",
        "depth": 25,  # 允许最多穿透到 25 层
        "invest_ratio": 50,
        "query_type": ["invest"],
        "tyc_id": "test_tyc_id",
        "tyc_token": "test_token"
    }

    asyncio.run(job_runner.run_tyc_job(options))

    # 验证 comp_A 仅在第 1 层查询一次，第 2 层查询 comp_B，第 3 层查询 comp_C，comp_A 不会重复被查询
    assert queried_gids == ["comp_A", "comp_B", "comp_C"]
