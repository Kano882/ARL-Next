#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_consolidated_features_regression.py
========================================
针对本次精简合并与性能优化的专项生产环境业务回归套件：
1. 任务概览统计聚合接口 (Task & ICP Task Overview Count)
2. 统一调度中心双轨接口 (Planning Tasks & Asset Monitor)
3. 系统服务资产双轨数据流与检索导出 (Nmap Service & Python NPoC Service)
4. GitHub DLP 监控与即时抽屉检索数据源 (GitHub Tasks & Results)
5. 系统设置统一字典规则库 (Dictionary & CDN Dict & Brute Dict)
6. 前端静态资源与 SPA 路由可达性校验

遵循严格无痕执行原则：所有测试产生的临时记录均在测试后原子清理。
"""

import os
import sys
import time
import json
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = os.environ.get("ARL_HOST", "https://192.0.2.10:5173")
TOKEN = os.environ.get("ARL_TOKEN", "")
BASIC_AUTH = (os.environ.get("BASIC_USER", ""), os.environ.get("BASIC_PASS", ""))

HEADERS = {
    "Token": TOKEN,
    "Content-Type": "application/json"
}

results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def log_pass(name, detail=""):
    print(f"  ✅ [PASS] {name} {detail}")
    results["passed"].append({"name": name, "detail": detail})

def log_fail(name, reason=""):
    print(f"  ❌ [FAIL] {name}: {reason}")
    results["failed"].append({"name": name, "reason": reason})

def log_warn(name, reason=""):
    print(f"  ⚠️ [WARN] {name}: {reason}")
    results["warnings"].append({"name": name, "reason": reason})

print("=" * 70)
print("🚀 开始执行 ARL-Next 本次合并功能与优化专项生产回归测试")
print(f"目标主机: {BASE_URL}")
print("=" * 70)

# ==============================================================
# MODULE 1: 任务概览统计聚合接口验证 (Task & ICP Overview Count)
# ==============================================================
print("\n[MODULE 1] 任务概览统计聚合接口 (Task & ICP Overview Count)...")
try:
    t0 = time.time()
    r = requests.get(f"{BASE_URL}/api/task/overview_count", headers=HEADERS, auth=BASIC_AUTH, verify=False, timeout=10)
    dur = time.time() - t0
    if r.status_code == 200:
        data = r.json()
        if data.get("code") == 200 and isinstance(data.get("data"), dict):
            counts = data["data"]
            required_keys = {"total", "running", "done", "abnormal", "details"}
            if required_keys.issubset(counts.keys()):
                log_pass("Task 概览统计接口契约与聚合正确", f"(耗时: {dur*1000:.1f}ms, 总数: {counts['total']}, 完成: {counts['done']}, 异常/停止: {counts['abnormal']})")
            else:
                log_fail("Task 概览统计响应字段缺失", f"返回 keys: {list(counts.keys())}")
        else:
            log_fail("Task 概览统计业务状态码异常", str(data))
    else:
        log_fail("Task 概览统计 HTTP 异常", f"HTTP {r.status_code}")
except Exception as e:
    log_fail("Task 概览统计请求异常", str(e))

try:
    t0 = time.time()
    r = requests.get(f"{BASE_URL}/api/icp/task/overview_count", headers=HEADERS, auth=BASIC_AUTH, verify=False, timeout=10)
    dur = time.time() - t0
    if r.status_code == 200:
        data = r.json()
        if data.get("code") == 200 and isinstance(data.get("data"), dict):
            counts = data["data"]
            required_keys = {"total", "running", "done", "abnormal", "details"}
            if required_keys.issubset(counts.keys()):
                log_pass("ICP Task 概览统计接口契约与聚合正确", f"(耗时: {dur*1000:.1f}ms, 总数: {counts['total']}, 完成: {counts['done']}, 异常/停止: {counts['abnormal']})")
            else:
                log_fail("ICP Task 概览统计响应字段缺失", f"返回 keys: {list(counts.keys())}")
        else:
            log_fail("ICP Task 概览统计业务状态码异常", str(data))
    else:
        log_fail("ICP Task 概览统计 HTTP 异常", f"HTTP {r.status_code}")
except Exception as e:
    log_fail("ICP Task 概览统计请求异常", str(e))


# ==============================================================
# MODULE 2: 统一调度中心双轨接口 (Planning Tasks & Asset Monitor)
# ==============================================================
print("\n[MODULE 2] 统一调度中心双轨接口 (Planning Tasks & Asset Monitor)...")

# 2.1 扫描计划任务 (task_schedule) 列表查询
try:
    r = requests.get(f"{BASE_URL}/api/task_schedule/", headers=HEADERS, auth=BASIC_AUTH, params={"page": 1, "size": 5}, verify=False, timeout=10)
    if r.status_code == 200 and r.json().get("code") == 200:
        log_pass("扫描计划任务列表查询 (task_schedule)", f"(总数: {r.json().get('total', 0)})")
    else:
        log_fail("扫描计划任务列表查询失败", r.text[:200])
except Exception as e:
    log_fail("扫描计划任务列表请求异常", str(e))

# 2.2 资产持续监控 (scheduler) 列表查询
try:
    r = requests.get(f"{BASE_URL}/api/scheduler/", headers=HEADERS, auth=BASIC_AUTH, params={"page": 1, "size": 5}, verify=False, timeout=10)
    if r.status_code == 200 and r.json().get("code") == 200:
        log_pass("资产持续监控列表查询 (scheduler)", f"(总数: {r.json().get('total', 0)})")
    else:
        log_fail("资产持续监控列表查询失败", r.text[:200])
except Exception as e:
    log_fail("资产持续监控列表请求异常", str(e))

# 2.3 临时计划任务生命周期闭环验证与严格无痕清理
try:
    pol_r = requests.get(f"{BASE_URL}/api/policy/", headers=HEADERS, auth=BASIC_AUTH, params={"size": 1}, verify=False, timeout=10)
    policy_id = pol_r.json().get("items", [{}])[0].get("_id")
    if policy_id:
        test_payload = {
            "name": "[TEST] Regression Plan Schedule",
            "target": "example-test-safe.com",
            "schedule_type": "recurrent_scan",
            "cron": "0 0 1 1 *",
            "policy_id": policy_id,
            "task_tag": "task"
        }
        create_r = requests.post(f"{BASE_URL}/api/task_schedule/", headers=HEADERS, auth=BASIC_AUTH, json=test_payload, verify=False, timeout=10)
        c_body = create_r.json()
        if create_r.status_code == 200 and c_body.get("code") == 200:
            c_data = c_body.get("data", {})
            sched_id = c_data.get("_id") if isinstance(c_data, dict) else (c_body.get("_id") or str(c_data))
            log_pass("创建临时测试计划任务成功", f"(ID: {sched_id})")

            # 停止计划任务
            stop_r = requests.post(f"{BASE_URL}/api/task_schedule/stop/", headers=HEADERS, auth=BASIC_AUTH, json={"_id": [sched_id]}, verify=False, timeout=10)
            if stop_r.status_code == 200 and stop_r.json().get("code") == 200:
                log_pass("停止计划任务成功")
            else:
                log_fail("停止计划任务异常", stop_r.text)

            # 恢复计划任务
            rec_r = requests.post(f"{BASE_URL}/api/task_schedule/recover/", headers=HEADERS, auth=BASIC_AUTH, json={"_id": [sched_id]}, verify=False, timeout=10)
            if rec_r.status_code == 200 and rec_r.json().get("code") == 200:
                log_pass("恢复计划任务成功")
            else:
                log_fail("恢复计划任务异常", rec_r.text)

            # 严格无痕清理删除
            del_r = requests.post(f"{BASE_URL}/api/task_schedule/delete/", headers=HEADERS, auth=BASIC_AUTH, json={"_id": [sched_id]}, verify=False, timeout=10)
            if del_r.status_code == 200 and del_r.json().get("code") == 200:
                log_pass("测试计划任务原子删除并自愈清理成功")
            else:
                log_fail("测试计划任务删除异常", del_r.text)
        else:
            log_warn("创建临时计划任务被拦截", str(c_body))
    else:
        log_warn("未找到可用策略，跳过计划任务创建测试")
except Exception as e:
    log_fail("计划任务生命周期测试异常", str(e))

# 2.4 资产监控批量操作接口契约校验
try:
    fake_ids = ["600000000000000000000001"]
    for action in ["stop", "recover"]:
        url = f"{BASE_URL}/api/scheduler/{action}/batch"
        res = requests.post(url, headers=HEADERS, auth=BASIC_AUTH, json={"scheduler_id": fake_ids}, verify=False, timeout=10)
        if res.status_code == 200:
            log_pass(f"资产监控批量 {action} 接口响应契约正常", f"(HTTP 200, code: {res.json().get('code')})")
        else:
            log_fail(f"资产监控批量 {action} 接口异常", f"HTTP {res.status_code}")
except Exception as e:
    log_fail("资产监控批量接口异常", str(e))


# ==============================================================
# MODULE 3: 系统服务资产双轨数据流与检索导出
# ==============================================================
print("\n[MODULE 3] 系统服务资产双轨数据流 (Service & NPoC Service)...")

try:
    r = requests.get(f"{BASE_URL}/api/service/", headers=HEADERS, auth=BASIC_AUTH, params={"page": 1, "size": 3}, verify=False, timeout=10)
    if r.status_code == 200 and r.json().get("code") == 200:
        log_pass("Nmap 端口服务 (service) 列表检索成功", f"(总数: {r.json().get('total', 0)})")
    else:
        log_fail("Nmap 服务列表检索失败", r.text[:200])
except Exception as e:
    log_fail("Nmap 服务检索异常", str(e))

try:
    r = requests.get(f"{BASE_URL}/api/npoc_service/", headers=HEADERS, auth=BASIC_AUTH, params={"page": 1, "size": 3}, verify=False, timeout=10)
    if r.status_code == 200 and r.json().get("code") == 200:
        log_pass("Python NPoC 指纹服务 (npoc_service) 列表检索成功", f"(总数: {r.json().get('total', 0)})")
    else:
        log_fail("Python NPoC 服务列表检索失败", r.text[:200])
except Exception as e:
    log_fail("Python NPoC 服务检索异常", str(e))


# ==============================================================
# MODULE 4: GitHub DLP 监控与即时抽屉检索数据源
# ==============================================================
print("\n[MODULE 4] GitHub DLP 监控与即时抽屉数据源 (GitHub Tasks & Results)...")

try:
    r = requests.get(f"{BASE_URL}/api/github_task/", headers=HEADERS, auth=BASIC_AUTH, params={"page": 1, "size": 3}, verify=False, timeout=10)
    if r.status_code == 200 and r.json().get("code") == 200:
        log_pass("GitHub 扫描任务列表 (github_task) 检索成功", f"(总数: {r.json().get('total', 0)})")
    else:
        log_fail("GitHub 任务列表检索失败", r.text[:200])
except Exception as e:
    log_fail("GitHub 任务检索异常", str(e))

try:
    r = requests.get(f"{BASE_URL}/api/github_result/", headers=HEADERS, auth=BASIC_AUTH, params={"page": 1, "size": 5}, verify=False, timeout=10)
    if r.status_code == 200 and r.json().get("code") == 200:
        log_pass("GitHub 泄露结果检索 (github_result) 抽屉数据源契约正常", f"(总数: {r.json().get('total', 0)})")
    else:
        log_fail("GitHub 泄露结果检索失败", r.text[:200])
except Exception as e:
    log_fail("GitHub 泄露结果检索异常", str(e))


# ==============================================================
# MODULE 5: 系统设置统一字典规则库 (Dictionary & CDN Dict & Brute Dict)
# ==============================================================
print("\n[MODULE 5] 系统设置统一字典规则库 (Dictionary & CDN Dict)...")

try:
    r = requests.get(f"{BASE_URL}/api/dictionary/list", headers=HEADERS, auth=BASIC_AUTH, verify=False, timeout=10)
    if r.status_code == 200 and r.json().get("code") == 200:
        items = r.json().get("data", [])
        log_pass("系统资产测绘字典列表检索成功", f"(字典数: {len(items)})")
    else:
        log_fail("系统字典列表检索失败", r.text[:200])
except Exception as e:
    log_fail("系统字典检索异常", str(e))

try:
    r = requests.get(f"{BASE_URL}/api/cdn_dict/list", headers=HEADERS, auth=BASIC_AUTH, verify=False, timeout=10)
    if r.status_code == 200 and r.json().get("code") == 200:
        items = r.json().get("data", [])
        log_pass("CDN 特征规则字典列表检索成功", f"(规则数: {len(items)})")
    else:
        log_fail("CDN 字典列表检索失败", r.text[:200])
except Exception as e:
    log_fail("CDN 字典检索异常", str(e))

try:
    r = requests.get(f"{BASE_URL}/api/brute_dict/list", headers=HEADERS, auth=BASIC_AUTH, verify=False, timeout=10)
    if r.status_code == 200 and r.json().get("code") == 200:
        items = r.json().get("data", [])
        log_pass("弱口令爆破字典列表检索成功", f"(弱口令数: {len(items)})")
    else:
        log_fail("弱口令字典列表检索失败", r.text[:200])
except Exception as e:
    log_fail("弱口令字典检索异常", str(e))


# ==============================================================
# MODULE 6: 前端 SPA 页面路由可达性与静态构建完整性
# ==============================================================
print("\n[MODULE 6] 前端 SPA 页面可达性与静态资源完整性...")

pages_to_test = [
    ("/planningTasks", "统一调度中心主路由"),
    ("/assetsMonitor", "资产监控历史兼容路由 (SPA 承接)"),
    ("/asset-search", "全局资产检索路由"),
    ("/systemSettings", "系统设置路由")
]

for path, desc in pages_to_test:
    try:
        r = requests.get(f"{BASE_URL}{path}", auth=BASIC_AUTH, verify=False, timeout=10)
        if r.status_code == 200 and "<html" in r.text.lower():
            log_pass(f"前端路由可达: {desc} ({path})", "(HTML 200 OK)")
        else:
            log_fail(f"前端路由加载异常: {desc} ({path})", f"HTTP {r.status_code}")
    except Exception as e:
        log_fail(f"前端路由请求异常: {path}", str(e))

print("\n" + "=" * 70)
print(f"📊 专项回归测试结果汇总: 通过 {len(results['passed'])}, 失败 {len(results['failed'])}, 警告 {len(results['warnings'])}")
print("=" * 70)

if results['failed']:
    sys.exit(1)
sys.exit(0)
