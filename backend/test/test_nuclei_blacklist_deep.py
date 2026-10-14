#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARL-Next Nuclei 官方误报模板标记与扫描排除全链路深度测试套件
涵盖：
1. 黑名单 API 鉴权拦截与 CRUD 闭环 (添加、查重幂等、检索、删除、批量删除)
2. 社区模板库只读列表状态联动与按状态过滤穿透 (is_blacklisted, blacklist_reason, blacklist_status)
3. 底层执行引擎 Nuclei CLI 原生 -eid 排除清单生成、命令行注入与无痕生命周期回收
4. 扫描策略 (Policy) 联动测试 (自动排除开关与策略级额外排除 ID)
"""

import sys
import os
import time
import json
import urllib3
import requests
import subprocess

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = os.environ.get("ARL_HOST", "https://192.0.2.10:5173")
TOKEN = os.environ.get("ARL_TOKEN", "<ARL_API_TOKEN>")

HEADERS = {
    "Token": TOKEN
}

results = {
    "passed": [],
    "failed": []
}

def log_pass(name, detail=""):
    print(f"  ✅ [PASS] {name} {detail}")
    results["passed"].append({"name": name, "detail": detail})

def log_fail(name, reason=""):
    print(f"  ❌ [FAIL] {name}: {reason}")
    results["failed"].append({"name": name, "reason": reason})

print("=" * 70)
print(f"🚀 开始执行 Nuclei 误报黑名单与扫描排除深度测试")
print(f"目标主机: {BASE_URL}")
print("=" * 70)

# ==============================================================================
# SECTION 1: 黑名单 CRUD 与安全边界
# ==============================================================================
print("\n[PART 1] 黑名单 API 鉴权与 CRUD 基础能力...")

# 1.1 未鉴权拦截
try:
    r_noauth = requests.get(f"{BASE_URL}/api/nuclei/blacklist/", verify=False, timeout=10)
    if r_noauth.status_code == 200 and r_noauth.json().get("code") == 401:
        log_pass("未鉴权访问黑名单拦截 (401 拦截有效)")
    else:
        log_fail("未鉴权访问黑名单拦截", f"返回: {r_noauth.text[:100]}")
except Exception as e:
    log_fail("未鉴权访问黑名单测试", f"异常: {e}")

# 1.2 添加误报模板到黑名单
test_tid = "cve-2021-41773"
test_name = "Apache HTTP Server Path Traversal"
test_reason = "内网代理网关统一返回特定错误头引发大面积误报"

try:
    r_add = requests.post(f"{BASE_URL}/api/nuclei/blacklist/", headers=HEADERS, json={
        "template_id": test_tid,
        "name": test_name,
        "severity": "critical",
        "tags": ["cve", "apache"],
        "reason": test_reason
    }, verify=False, timeout=10)
    res_add = r_add.json()
    if r_add.status_code == 200 and res_add.get("code") == 200:
        log_pass("添加模板到误报黑名单", f"响应: {res_add.get('data', {}).get('message')}")
    else:
        log_fail("添加模板到误报黑名单", f"被拒: {r_add.text}")
except Exception as e:
    log_fail("添加黑名单测试", f"异常: {e}")

# 1.3 查重与幂等更新 (同一 template_id 再次添加更新原因)
new_reason = "更新后的屏蔽原因: 确认特定环境存在误判"
try:
    r_upsert = requests.post(f"{BASE_URL}/api/nuclei/blacklist/", headers=HEADERS, json={
        "template_id": test_tid,
        "name": test_name,
        "severity": "critical",
        "reason": new_reason
    }, verify=False, timeout=10)
    res_upsert = r_upsert.json()
    if r_upsert.status_code == 200 and res_upsert.get("code") == 200:
        log_pass("黑名单查重与幂等性更新 (Upsert 生效)")
    else:
        log_fail("黑名单查重与幂等性更新", f"返回异常: {r_upsert.text}")
except Exception as e:
    log_fail("黑名单幂等性测试", f"异常: {e}")

# 1.4 黑名单分页检索与关键字过滤
try:
    r_get = requests.get(f"{BASE_URL}/api/nuclei/blacklist/?search={test_tid}", headers=HEADERS, verify=False, timeout=10)
    get_res = r_get.json()
    items = get_res.get("data", {}).get("items", [])
    if len(items) >= 1 and items[0].get("template_id") == test_tid and items[0].get("reason") == new_reason:
        log_pass("黑名单模糊查询与字段校验", f"查出屏蔽模板: {test_tid}, 原因: '{items[0].get('reason')}'")
    else:
        log_fail("黑名单模糊查询与字段校验", f"未搜出预期条目: {r_get.text}")
except Exception as e:
    log_fail("黑名单查询测试", f"异常: {e}")

# 1.5 统计概览感知自增
try:
    r_stats = requests.get(f"{BASE_URL}/api/nuclei/stats/", headers=HEADERS, verify=False, timeout=10)
    st_json = r_stats.json().get("data", {})
    bl_total = st_json.get("blacklist_total", 0)
    if bl_total >= 1:
        log_pass("全局概览统计黑名单感知", f"(已屏蔽误报数: {bl_total})")
    else:
        log_fail("全局概览统计黑名单感知", f"blacklist_total 异常: {st_json}")
except Exception as e:
    log_fail("全局统计感知测试", f"异常: {e}")


# ==============================================================================
# SECTION 2: 官方社区模板列表状态联动与状态过滤
# ==============================================================================
print("\n[PART 2] 官方社区模板列表状态联动...")

# 2.1 社区模板检索结果中注入 is_blacklisted 与 blacklist_reason
try:
    r_comm = requests.get(f"{BASE_URL}/api/nuclei/community/?search={test_tid}", headers=HEADERS, verify=False, timeout=10)
    c_items = r_comm.json().get("data", {}).get("items", [])
    matched_item = next((x for x in c_items if x.get("template_id", "").lower() == test_tid.lower()), None)
    if matched_item and matched_item.get("is_blacklisted") is True and matched_item.get("blacklist_reason") == new_reason:
        log_pass("社区列表行内黑名单状态联动", f"成功标记 is_blacklisted: True, reason: '{matched_item.get('blacklist_reason')}'")
    else:
        log_fail("社区列表行内黑名单状态联动", f"状态未正确注入: {matched_item}")
except Exception as e:
    log_fail("社区列表状态联动测试", f"异常: {e}")

# 2.2 社区模板按 blacklist_status=blacklisted 过滤
try:
    r_bl_filter = requests.get(f"{BASE_URL}/api/nuclei/community/?blacklist_status=blacklisted", headers=HEADERS, verify=False, timeout=10)
    bl_filtered = r_bl_filter.json().get("data", {}).get("items", [])
    if any(x.get("template_id", "").lower() == test_tid.lower() for x in bl_filtered):
        log_pass("社区列表按 '已屏蔽(误报)' 过滤", f"正确过滤出已屏蔽模板集合 (数量: {len(bl_filtered)})")
    else:
        log_fail("社区列表按 '已屏蔽(误报)' 过滤", f"未返回已拉黑模板: {r_bl_filter.text}")
except Exception as e:
    log_fail("社区状态过滤测试", f"异常: {e}")

# 2.3 社区模板按 blacklist_status=normal 过滤 (应排除已屏蔽模板)
try:
    r_norm_filter = requests.get(f"{BASE_URL}/api/nuclei/community/?search={test_tid}&blacklist_status=normal", headers=HEADERS, verify=False, timeout=10)
    norm_filtered = r_norm_filter.json().get("data", {}).get("items", [])
    if not any(x.get("template_id", "").lower() == test_tid.lower() for x in norm_filtered):
        log_pass("社区列表按 '正常扫描' 过滤", f"成功剔除已屏蔽模板 (正常条目数: {len(norm_filtered)})")
    else:
        log_fail("社区列表按 '正常扫描' 过滤", f"未剔除已拉黑模板: {r_norm_filter.text}")
except Exception as e:
    log_fail("正常扫描过滤测试", f"异常: {e}")


# ==============================================================================
# SECTION 3: 底层执行引擎 NucleiScan 原生 -eid 排除清单闭环测试
# ==============================================================================
print("\n[PART 3] 底层扫描执行引擎排除清单闭环验证...")

import base64

raw_py_script = """
import os
from app.services.nuclei_scan import NucleiScan

# 1. 默认策略：自动排除全局黑名单
scan_default = NucleiScan(targets=['127.0.0.1'], options={
    'nuclei_config': {'exclude_blacklist': True}
})
ex_file = scan_default._prepare_exclude_file()
assert ex_file is not None, "未生成排除文件"
assert os.path.exists(ex_file), "排除文件物理不存在"

with open(ex_file, 'r', encoding='utf-8') as f:
    content = f.read()
assert 'cve-2021-41773' in content.lower(), "排除文件未包含目标 CVE"

# 2. 检查安全无痕清理
scan_default._delete_file()
assert not os.path.exists(ex_file), "扫描后排除文件未被安全清理"

# 3. 策略级额外排除 ID 联动
scan_extra = NucleiScan(targets=['127.0.0.1'], options={
    'nuclei_config': {
        'exclude_blacklist': True,
        'extra_exclude_ids': ['custom-policy-exclude-poc-1', 'custom-policy-exclude-poc-2']
    }
})
ex_file_extra = scan_extra._prepare_exclude_file()
with open(ex_file_extra, 'r', encoding='utf-8') as f:
    extra_content = f.read()

assert 'cve-2021-41773' in extra_content.lower(), "未包含全局黑名单"
assert 'custom-policy-exclude-poc-1' in extra_content, "未包含策略额外排除 1"
assert 'custom-policy-exclude-poc-2' in extra_content, "未包含策略额外排除 2"
scan_extra._delete_file()
assert not os.path.exists(ex_file_extra), "额外排除文件未被安全清理"

# 4. 显式禁用全局黑名单排除
scan_disabled = NucleiScan(targets=['127.0.0.1'], options={
    'nuclei_config': {'exclude_blacklist': False, 'extra_exclude_ids': []}
})
ex_file_dis = scan_disabled._prepare_exclude_file()
assert ex_file_dis is None, "禁用黑名单时不应生成排除清单"

print("NUCLEI_ENGINE_VERIFIED_OK")
"""

b64_script = base64.b64encode(raw_py_script.encode()).decode()

try:
    remote_cmd = f"ssh -p 2222 -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@192.0.2.10 \"docker exec -w /code/backend arl-web-prod /code/backend/.venv-docker/bin/python3 -c \\\"import base64; exec(base64.b64decode('{b64_script}').decode())\\\"\""
    p = subprocess.run(remote_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
    if "NUCLEI_ENGINE_VERIFIED_OK" in p.stdout:
        log_pass("NucleiScan 底层 -eid 排除清单生成与回收闭环", "(默认全局排除、策略额外追加、开关禁用及无痕清理全部通过)")
    else:
        log_fail("NucleiScan 底层排除验证", f"输出: {p.stdout} 错误: {p.stderr}")
except Exception as e:
    log_fail("底层引擎排除测试", f"异常: {e}")


# ==============================================================================
# SECTION 4: 批量解除与环境自愈清理
# ==============================================================================
print("\n[PART 4] 黑名单解除与环境自愈清理...")

# 4.1 单个解除屏蔽
try:
    r_del = requests.delete(f"{BASE_URL}/api/nuclei/blacklist/{test_tid}/", headers=HEADERS, verify=False, timeout=10)
    del_res = r_del.json()
    if r_del.status_code == 200 and del_res.get("code") == 200:
        log_pass("单个解除误报黑名单", f"响应: {del_res.get('data', {}).get('message')}")
    else:
        log_fail("单个解除误报黑名单", f"解除失败: {r_del.text}")
except Exception as e:
    log_fail("单个解除黑名单测试", f"异常: {e}")

# 4.2 验证解除后社区状态恢复
try:
    r_comm_restore = requests.get(f"{BASE_URL}/api/nuclei/community/?search={test_tid}", headers=HEADERS, verify=False, timeout=10)
    restored_items = r_comm_restore.json().get("data", {}).get("items", [])
    m_item = next((x for x in restored_items if x.get("template_id", "").lower() == test_tid.lower()), None)
    if m_item and m_item.get("is_blacklisted") is False:
        log_pass("解除后社区列表状态自动恢复", "(is_blacklisted 已恢复为 False)")
    else:
        log_fail("解除后社区列表状态恢复", f"状态未恢复: {m_item}")
except Exception as e:
    log_fail("解除状态恢复测试", f"异常: {e}")

# 4.3 批量添加测试条目并批量解除
try:
    # 批量添加两个条目
    requests.post(f"{BASE_URL}/api/nuclei/blacklist/", headers=HEADERS, json={"template_id": "batch-fp-1", "reason": "测试"}, verify=False, timeout=10)
    requests.post(f"{BASE_URL}/api/nuclei/blacklist/", headers=HEADERS, json={"template_id": "batch-fp-2", "reason": "测试"}, verify=False, timeout=10)
    
    # 批量移除
    r_batch_del = requests.post(f"{BASE_URL}/api/nuclei/blacklist/delete/", headers=HEADERS, json={"template_ids": ["batch-fp-1", "batch-fp-2"]}, verify=False, timeout=10)
    batch_del_res = r_batch_del.json()
    if r_batch_del.status_code == 200 and batch_del_res.get("data", {}).get("deleted_count") == 2:
        log_pass("批量解除误报黑名单", f"成功批量解除 2 条模板")
    else:
        log_fail("批量解除误报黑名单", f"批量删除响应异常: {r_batch_del.text}")
except Exception as e:
    log_fail("批量解除黑名单测试", f"异常: {e}")

# 4.4 最终全局统计核验与无痕收尾
try:
    r_final_stats = requests.get(f"{BASE_URL}/api/nuclei/stats/", headers=HEADERS, verify=False, timeout=10)
    final_bl = r_final_stats.json().get("data", {}).get("blacklist_total", 0)
    if final_bl == 0:
        log_pass("测试数据安全清理与全局统计恢复 (blacklist_total: 0)")
    else:
        log_fail("最终统计恢复核验", f"blacklist_total 未归零: {final_bl}")
except Exception as e:
    log_fail("最终统计测试", f"异常: {e}")

print("\n" + "=" * 70)
print(f"📊 误报黑名单深度测试结果: 通过 {len(results['passed'])}, 失败 {len(results['failed'])}")
print("=" * 70)

if results["failed"]:
    sys.exit(1)
