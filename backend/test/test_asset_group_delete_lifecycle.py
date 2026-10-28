import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from bson import ObjectId
import mongomock
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
XING_DIR = BACKEND_DIR / "ARL-NPoC"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if XING_DIR.exists() and str(XING_DIR) not in sys.path:
    sys.path.insert(0, str(XING_DIR))

from flask import Flask
from app.config import Config
from app import utils
from app.routes.assetGroup import DeleteARLAssetGroup, delete_asset_group_fields

flask_app = Flask(__name__)

@pytest.fixture(autouse=True)
def setup_ctx():
    with flask_app.test_request_context(), patch.object(Config, 'AUTH', False):
        yield

@pytest.fixture
def mock_db():
    client = mongomock.MongoClient()
    db = client['arl_test']

    def conn_db_mock(col_name):
        return db[col_name]

    with patch.object(utils, 'conn_db', side_effect=conn_db_mock):
        yield db


def test_delete_empty_group(mock_db):
    group_id = mock_db.asset_group.insert_one({
        "name": "空集团",
        "description": "空测试集团"
    }).inserted_id

    resource = DeleteARLAssetGroup()
    with patch.object(resource, 'parse_args', return_value={'_id': str(group_id), 'action': 'dissolve'}):
        res = resource.post()
        assert res.get('code') == 200
        assert mock_db.asset_group.find_one({'_id': group_id}) is None


def test_delete_group_with_scopes_dissolve(mock_db):
    group_id = mock_db.asset_group.insert_one({
        "name": "待解散集团",
        "description": "包含下属资产组"
    }).inserted_id

    # 关联2个资产组
    s1 = mock_db.asset_scope.insert_one({
        "name": "资产组1",
        "group_id": str(group_id),
        "group_name": "待解散集团"
    }).inserted_id

    s2 = mock_db.asset_scope.insert_one({
        "name": "资产组2",
        "group_id": str(group_id),
        "group_name": "待解散集团"
    }).inserted_id

    resource = DeleteARLAssetGroup()
    with patch.object(resource, 'parse_args', return_value={'_id': str(group_id), 'action': 'dissolve'}):
        res = resource.post()
        assert res.get('code') == 200
        assert mock_db.asset_group.find_one({'_id': group_id}) is None

        # 验证下属资产组平滑解散
        doc1 = mock_db.asset_scope.find_one({'_id': s1})
        doc2 = mock_db.asset_scope.find_one({'_id': s2})
        assert 'group_id' not in doc1 or doc1.get('group_id') is None
        assert 'group_name' not in doc1 or doc1.get('group_name') is None
        assert 'group_id' not in doc2 or doc2.get('group_id') is None
        assert 'group_name' not in doc2 or doc2.get('group_name') is None


def test_delete_group_with_scopes_transfer(mock_db):
    group_src_id = mock_db.asset_group.insert_one({
        "name": "源集团",
        "description": "待转移的集团"
    }).inserted_id

    group_dst_id = mock_db.asset_group.insert_one({
        "name": "目标集团",
        "description": "划转接收方"
    }).inserted_id

    s1 = mock_db.asset_scope.insert_one({
        "name": "迁移资产组A",
        "group_id": str(group_src_id),
        "group_name": "源集团"
    }).inserted_id

    resource = DeleteARLAssetGroup()
    with patch.object(resource, 'parse_args', return_value={
        '_id': str(group_src_id),
        'action': 'transfer',
        'target_group_id': str(group_dst_id)
    }):
        res = resource.post()
        assert res.get('code') == 200
        assert mock_db.asset_group.find_one({'_id': group_src_id}) is None
        assert mock_db.asset_group.find_one({'_id': group_dst_id}) is not None

        # 验证下属资产组划转至目标集团
        doc1 = mock_db.asset_scope.find_one({'_id': s1})
        assert doc1.get('group_id') == str(group_dst_id)
        assert doc1.get('group_name') == "目标集团"


def test_delete_group_transfer_target_equal_source(mock_db):
    group_id = mock_db.asset_group.insert_one({
        "name": "自循环集团"
    }).inserted_id

    mock_db.asset_scope.insert_one({
        "name": "资产组X",
        "group_id": str(group_id),
        "group_name": "自循环集团"
    })

    resource = DeleteARLAssetGroup()
    with patch.object(resource, 'parse_args', return_value={
        '_id': str(group_id),
        'action': 'transfer',
        'target_group_id': str(group_id)
    }):
        res = resource.post()
        assert res.get('code') != 200
        assert "目标集团不能为当前集团" in str(res)


def test_delete_group_transfer_target_not_exist(mock_db):
    group_id = mock_db.asset_group.insert_one({
        "name": "源集团"
    }).inserted_id

    mock_db.asset_scope.insert_one({
        "name": "资产组Y",
        "group_id": str(group_id),
        "group_name": "源集团"
    })

    resource = DeleteARLAssetGroup()
    with patch.object(resource, 'parse_args', return_value={
        '_id': str(group_id),
        'action': 'transfer',
        'target_group_id': str(ObjectId())
    }):
        res = resource.post()
        assert res.get('code') != 200
        assert "目标集团不存在" in str(res)


if __name__ == '__main__':
    client = mongomock.MongoClient()
    db = client['arl_test']

    def conn_db_mock(col_name):
        return db[col_name]

    with flask_app.test_request_context(), patch.object(Config, 'AUTH', False), patch.object(utils, 'conn_db', side_effect=conn_db_mock):
        print("Running test_delete_empty_group...")
        test_delete_empty_group(db)
        print("Running test_delete_group_with_scopes_dissolve...")
        test_delete_group_with_scopes_dissolve(db)
        print("Running test_delete_group_with_scopes_transfer...")
        test_delete_group_with_scopes_transfer(db)
        print("Running test_delete_group_transfer_target_equal_source...")
        test_delete_group_transfer_target_equal_source(db)
        print("Running test_delete_group_transfer_target_not_exist...")
        test_delete_group_transfer_target_not_exist(db)
        print("ALL TESTS PASSED SUCCESSFULLY!")

