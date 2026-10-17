import asyncio
import os
import sys
from pathlib import Path


SERVICE_DIR = Path(__file__).parent.parent / "backend" / "icp_query"
sys.path.insert(0, str(SERVICE_DIR))

_cwd = os.getcwd()
os.chdir(SERVICE_DIR)
try:
    from routes.query_routes import _normalize_pagination
    from ymicp import beian
finally:
    os.chdir(_cwd)


def teardown_module():
    try:
        (SERVICE_DIR / "logs").rmdir()
    except OSError:
        pass


def _page_result(page_num, pages, items):
    return {
        "code": 200,
        "success": True,
        "params": {
            "pageNum": page_num,
            "pageSize": 26,
            "pages": pages,
            "total": sum(len(page_items) for page_items in items.values()),
            "list": items[page_num],
        },
    }


def test_default_query_fetches_all_pages():
    service = beian()
    calls = []
    page_items = {
        1: [{"id": "p1-a"}, {"id": "p1-b"}],
        2: [{"id": "p2-a"}],
        3: [{"id": "p3-a"}],
    }

    async def fake_query_page(name, sp, pageNum, pageSize, proxy=""):
        calls.append((pageNum, pageSize))
        return True, _page_result(pageNum, 3, page_items), {
            "p_uuid": "",
            "token": "token",
            "sign": "sign",
            "base_header": {},
        }

    service._query_beian_page = fake_query_page

    success, result = asyncio.run(service.getbeian("example", 0, None, None))

    assert success is True
    assert calls == [(1, 26), (2, 26), (3, 26)]
    assert [item["id"] for item in result["params"]["list"]] == [
        "p1-a",
        "p1-b",
        "p2-a",
        "p3-a",
    ]
    assert result["params"]["pageNum"] == 1
    assert result["params"]["pageSize"] == 4


def test_explicit_pagination_keeps_single_page_behavior():
    service = beian()
    calls = []
    page_items = {3: [{"id": "p3-a"}]}

    async def fake_query_page(name, sp, pageNum, pageSize, proxy=""):
        calls.append((pageNum, pageSize))
        return True, _page_result(pageNum, 5, page_items), {
            "p_uuid": "",
            "token": "token",
            "sign": "sign",
            "base_header": {},
        }

    service._query_beian_page = fake_query_page

    success, result = asyncio.run(service.getbeian("example", 0, "3", "20"))

    assert success is True
    assert calls == [(3, 20)]
    assert result["params"]["list"] == [{"id": "p3-a"}]


def test_pagination_normalization_rejects_invalid_values():
    assert _normalize_pagination(None, None) == (None, None, None)
    assert _normalize_pagination("2", None) == ("2", "26", None)
    assert _normalize_pagination(None, "20") == ("1", "20", None)

    _, _, error = _normalize_pagination("0", "20")
    assert error == "pageNum必须大于等于1"

    _, _, error = _normalize_pagination("1", "27")
    assert error == "pageSize必须在1到26之间"

    _, _, error = _normalize_pagination("abc", "20")
    assert error == "pageNum/pageSize必须为正整数"
