"""
test_api_group_ops_db.py
========================
测试资产组“操作”列的 4 个后端添加功能，并直连 MongoDB 验证持久化层数据一致性。
"""
import pytest
import os
import sys
from bson import ObjectId

# 将 backend 路径加入 sys.path 以便导入后端配置和数据库连接
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.utils.conn import conn_db


@pytest.fixture(scope="module")
def setup_test_data(api_client, test_scope, test_policy):
    """
    数据预置：确保有一个 test_scope (资产范围) 和 test_policy (策略)。
    """
    return {
        "scope_id": test_scope,
        "policy_id": test_policy
    }


def test_add_asset_scope(api_client, setup_test_data):
    """测试：添加资产分组范围"""
    scope_id = setup_test_data["scope_id"]
    new_scope = "db-test-domain.com"
    
    payload = {
        "scope_id": scope_id,
        "scope": new_scope
    }
    
    # API 断言
    res = api_client.post(f"{api_client.base_url}/asset_scope/add/", json=payload)
    assert res.status_code == 200
    assert res.json().get("code") == 200
    
    # 数据库断言
    db_scope = conn_db("asset_scope")
    record = db_scope.find_one({"_id": ObjectId(scope_id)})
    assert record is not None
    assert new_scope in record.get("scope_array", [])


def test_add_asset_scope_invalid_id(api_client):
    """测试：添加资产分组范围 (非法 ID)"""
    payload = {
        "scope_id": str(ObjectId()),  # 伪造的不存在 ID
        "scope": "invalid-id.com"
    }
    res = api_client.post(f"{api_client.base_url}/asset_scope/add/", json=payload)
    assert res.status_code == 200
    assert res.json().get("code") != 200  # 应该拦截


def test_add_monitor_task(api_client, setup_test_data):
    """测试：添加常规监控任务"""
    scope_id = setup_test_data["scope_id"]
    policy_id = setup_test_data["policy_id"]
    
    payload = {
        "scope_id": scope_id,
        "domain": "db-test-domain.com",
        "interval": 86400,
        "policy_id": policy_id,
        "name": ""
    }
    
    res = api_client.post(f"{api_client.base_url}/scheduler/add/", json=payload)
    assert res.status_code == 200
    assert res.json().get("code") == 200
    
    # 数据库断言
    db_scheduler = conn_db("scheduler")
    # 按照 scope_id + 目标查找对应的监控记录
    record = db_scheduler.find_one({"scope_id": scope_id, "target": "db-test-domain.com"})
    assert record is not None
    assert record.get("interval") == 86400
    assert record.get("policy_id") == policy_id
    

def test_add_monitor_task_duplicate(api_client, setup_test_data):
    """测试：重复添加监控任务 (返回 699 并阻止生成冗余记录)"""
    scope_id = setup_test_data["scope_id"]
    policy_id = setup_test_data["policy_id"]
    
    payload = {
        "scope_id": scope_id,
        "domain": "db-test-domain.com", # 和上一步一样的域
        "interval": 86400,
        "policy_id": policy_id,
        "name": ""
    }
    
    res = api_client.post(f"{api_client.base_url}/scheduler/add/", json=payload)
    assert res.status_code == 200
    assert res.json().get("code") == 699
    
    # 验证 DB 确实只有一条记录
    db_scheduler = conn_db("scheduler")
    count = db_scheduler.count_documents({"scope_id": scope_id, "target": "db-test-domain.com"})
    assert count == 1


def test_add_site_monitor(api_client, setup_test_data):
    """测试：添加站点监控任务"""
    scope_id = setup_test_data["scope_id"]
    
    payload = {
        "scope_id": scope_id,
        "interval": 3600
    }
    
    res = api_client.post(f"{api_client.base_url}/scheduler/add/site_monitor/", json=payload)
    assert res.status_code == 200
    assert res.json().get("code") == 200
    
    # DB 验证
    db_scheduler = conn_db("scheduler")
    record = db_scheduler.find_one({"scope_id": scope_id, "task_type": "site_monitor"})
    assert record is not None
    assert record.get("interval") == 3600
    

def test_add_site_monitor_duplicate(api_client, setup_test_data):
    """测试：重复添加站点监控任务 (返回 1607)"""
    scope_id = setup_test_data["scope_id"]
    
    payload = {
        "scope_id": scope_id,
        "interval": 3600
    }
    
    res = api_client.post(f"{api_client.base_url}/scheduler/add/site_monitor/", json=payload)
    assert res.status_code == 200
    assert res.json().get("code") == 1607


def test_add_wih_monitor(api_client, setup_test_data):
    """测试：添加WIH监控任务"""
    scope_id = setup_test_data["scope_id"]
    
    payload = {
        "scope_id": scope_id,
        "interval": 7200
    }
    
    res = api_client.post(f"{api_client.base_url}/scheduler/add/wih_monitor/", json=payload)
    assert res.status_code == 200
    assert res.json().get("code") == 200
    
    # DB 验证
    db_scheduler = conn_db("scheduler")
    record = db_scheduler.find_one({"scope_id": scope_id, "task_type": "wih_monitor"})
    assert record is not None
    assert record.get("interval") == 7200


def test_add_wih_monitor_duplicate(api_client, setup_test_data):
    """测试：重复添加WIH监控任务 (返回 1607)"""
    scope_id = setup_test_data["scope_id"]
    
    payload = {
        "scope_id": scope_id,
        "interval": 7200
    }
    
    res = api_client.post(f"{api_client.base_url}/scheduler/add/wih_monitor/", json=payload)
    assert res.status_code == 200
    assert res.json().get("code") == 1607


@pytest.fixture(scope="module", autouse=True)
def teardown_test_data(setup_test_data):
    """模块级别清理，自动删除创建的特定任务"""
    yield
    scope_id = setup_test_data["scope_id"]
    # 强制清理 MongoDB 记录确保无痕
    db_scheduler = conn_db("scheduler")
    db_scheduler.delete_many({"scope_id": scope_id})
