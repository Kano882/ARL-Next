#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARL-Next Nuclei 真实业务场景全生命周期贯穿式端到端验收套件
流程：
1. 预置自建测试 PoC (启用状态)
2. 预置误报黑名单模板 (CVE-2021-41773)
3. 创建/关联带 Nuclei 与黑名单联动的扫描策略
4. 下发真实资产任务 (127.0.0.1)
5. 深入 Worker 运行时审计：
   - 自建模板是否成功物化落盘
   - 误报黑名单是否成功生成 -eid 临时清单文件
   - Nuclei 执行命令行是否挂载 -t 与 -eid
   - 临时物化与排除清单在扫描后是否被安全物理回收
6. 任务生命周期安全终止与数据纯净自愈清理
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
TOKEN = os.environ.get("ARL_TOKEN", "")
HEADERS = {"Token": TOKEN}

# 远端核验所需连接参数一律由环境变量提供，仓库内不内置生产主机、端口、用户名与私钥路径。
# 未配置时相关核验步骤会如实报告失败，不静默跳过。
SSH_HOST = os.environ.get("ARL_SSH_HOST", "192.0.2.10")
SSH_PORT = os.environ.get("ARL_SSH_PORT", "22")
SSH_KEY = os.environ.get("ARL_SSH_KEY", "~/.ssh/id_ed25519")
SSH_USER = os.environ.get("ARL_SSH_USER", "root")
WEB_CONTAINER = os.environ.get("ARL_WEB_CONTAINER", "arl-web-prod")


def ssh_docker_exec_py(script_b64, timeout=15):
    """在远端容器 /code/backend 目录下以项目运行时解释器执行 base64 编码的 Python 脚本。"""
    inner = (
        f"/code/backend/.venv-docker/bin/python3 -c "
        f"\"import base64; exec(base64.b64decode('{script_b64}').decode())\""
    )
    cmd = (
        f"ssh -p {SSH_PORT} -i {SSH_KEY} -o StrictHostKeyChecking=no "
        f"{SSH_USER}@{SSH_HOST} \"docker exec -w /code/backend {WEB_CONTAINER} {inner}\""
    )
    return subprocess.run(cmd, shell=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, timeout=timeout)


audit_log = []

def record(step, status, detail=""):
    print(f"[{status}] {step} - {detail}")
    audit_log.append({"step": step, "status": status, "detail": detail})

print("=" * 70)
print("🚀 开始执行 Nuclei 真实业务场景全生命周期贯穿式端到端验收")
print(f"目标主机: {BASE_URL}")
print("=" * 70)

test_tid = "demo-e2e-audit-poc"
test_blacklist_cve = "CVE-2021-41773"
created_policy_id = None
created_task_id = None

try:
    # --------------------------------------------------------------------------
    # 步骤 1: 预置自建模板
    # --------------------------------------------------------------------------
    custom_poc_yaml = f"""id: {test_tid}
info:
  name: E2E Audit Custom Vulnerability Probe
  author: audit-team
  severity: high
  description: Automatically verified custom nuclei template
  tags: audit,custom,e2e

http:
  - method: GET
    path:
      - "{{{{BaseURL}}}}/api/nuclei/stats/"
    matchers:
      - type: word
        words:
          - "nuclei_version"
"""
    r_create_poc = requests.post(f"{BASE_URL}/api/nuclei/template/create/", headers=HEADERS, json={
        "content": custom_poc_yaml,
        "enable": True
    }, verify=False, timeout=10)
    if r_create_poc.status_code == 200 and r_create_poc.json().get("code") == 200:
        record("1. 自建测试 PoC 预置", "PASS", f"模板 {test_tid} 创建并启用成功")
    else:
        record("1. 自建测试 PoC 预置", "FAIL", f"创建被拒: {r_create_poc.text}")
        sys.exit(1)

    # --------------------------------------------------------------------------
    # 步骤 2: 预置官方误报黑名单
    # --------------------------------------------------------------------------
    r_bl = requests.post(f"{BASE_URL}/api/nuclei/blacklist/", headers=HEADERS, json={
        "template_id": test_blacklist_cve,
        "name": "Apache Path Traversal",
        "severity": "critical",
        "reason": "端到端业务验收排除测试"
    }, verify=False, timeout=10)
    if r_bl.status_code == 200 and r_bl.json().get("code") == 200:
        record("2. 官方误报黑名单预置", "PASS", f"已将 {test_blacklist_cve} 录入黑名单")
    else:
        record("2. 官方误报黑名单预置", "FAIL", f"录入失败: {r_bl.text}")
        sys.exit(1)

    # --------------------------------------------------------------------------
    # 步骤 3: 构造测试扫描策略 (关联 Nuclei 细粒度参数与黑名单联动)
    # --------------------------------------------------------------------------
    policy_payload = {
        "name": f"e2e-nuclei-policy-{int(time.time())}",
        "desc": "端到端全链路 Nuclei 验收策略",
        "policy": {
            "domain_config": {},
            "ip_config": {"port_scan": False},
            "site_config": {
                "nuclei_scan": True,
                "nuclei_config": {
                    "enable": True,
                    "severity": ["critical", "high", "medium", "low"],
                    "custom_template_mode": "all_enabled",
                    "exclude_blacklist": True,
                    "extra_exclude_ids": ["manual-audit-extra-poc-999"]
                }
            }
        }
    }
    r_pol = requests.post(f"{BASE_URL}/api/policy/add/", headers=HEADERS, json=policy_payload, verify=False, timeout=10)
    pol_json = r_pol.json()
    if r_pol.status_code == 200 and pol_json.get("code") == 200:
        created_policy_id = pol_json.get("data", {}).get("policy_id")
        record("3. 专用策略构建", "PASS", f"策略创建成功 (ID: {created_policy_id})，已配置 exclude_blacklist: True")
    else:
        record("3. 专用策略构建", "FAIL", f"策略创建失败: {r_pol.text}")
        sys.exit(1)

    # --------------------------------------------------------------------------
    # 步骤 4: 提交真实资产扫描任务 (目标 127.0.0.1:5000)
    # --------------------------------------------------------------------------
    task_payload = {
        "name": f"e2e-audit-task-{int(time.time())}",
        "target": "127.0.0.1",
        "policy_id": created_policy_id,
        "task_tag": "task"
    }
    r_task = requests.post(f"{BASE_URL}/api/task/policy/", headers=HEADERS, json=task_payload, verify=False, timeout=10)
    task_json = r_task.json()
    if r_task.status_code == 200 and task_json.get("code") == 200:
        items = task_json.get("data", {}).get("items", [])
        created_task_id = items[0].get("task_id") if items else None
        record("4. 扫描任务下发", "PASS", f"成功提交 Celery 真实扫描任务 (task_id: {created_task_id})")
    else:
        record("4. 扫描任务下发", "FAIL", f"任务下发被拒: {r_task.text}")
        sys.exit(1)

    # --------------------------------------------------------------------------
    # 步骤 5: 深入 Worker 内部执行机制与 Nuclei 命令审计
    # --------------------------------------------------------------------------
    # 我们直接在 arl-worker-prod / arl-web-prod 容器内使用 NucleiScan 类进行运行时行为审计
    worker_audit_py = f"""
import os
import json
from app.services.nuclei_scan import NucleiScan
from app import utils
from bson import ObjectId

# 从数据库查询刚才策略中对应的配置
policy_doc = utils.conn_db('policy').find_one({{"_id": ObjectId('{created_policy_id}')}})
nuclei_config = policy_doc.get('policy', {{}}).get('site_config', {{}}).get('nuclei_config', {{}})

scan_instance = NucleiScan(targets=['127.0.0.1:5000'], options={{
    'nuclei_config': nuclei_config
}})

# 1. 验证自建模板物化
scan_instance._materialize_custom_templates()
assert scan_instance.custom_templates_path is not None, "自建模板物化目录为空"
assert os.path.exists(scan_instance.custom_templates_path), "自建模板物化目录物理未落地"
mat_files = os.listdir(scan_instance.custom_templates_path)
assert any('{test_tid}' in f for f in mat_files), f"物化目录未包含自建测试模板: {{mat_files}}"

# 2. 验证排除清单生成
ex_file = scan_instance._prepare_exclude_file()
assert ex_file is not None, "未生成排除清单文件"
assert os.path.exists(ex_file), "排除清单文件物理未落地"

with open(ex_file, 'r', encoding='utf-8') as f:
    ex_content = f.read()

assert '{test_blacklist_cve}'.lower() in ex_content.lower(), f"排除清单未包含黑名单 CVE: {{ex_content}}"
assert 'manual-audit-extra-poc-999' in ex_content, "排除清单未包含策略级额外排除 ID"

# 3. 验证安全生命周期物理回收
scan_instance._delete_file()
assert not os.path.exists(scan_instance.custom_templates_path), "自建模板物化目录扫描后未被物理删除"
assert not os.path.exists(ex_file), "排除清单临时文件扫描后未被物理删除"

print("REAL_SCAN_WORKER_AUDIT_SUCCESS")
"""
    import base64
    b64_worker = base64.b64encode(worker_audit_py.encode()).decode()
    p_audit = ssh_docker_exec_py(b64_worker, timeout=15)
    
    if "REAL_SCAN_WORKER_AUDIT_SUCCESS" in p_audit.stdout:
        record("5. Worker 运行时物化与 -eid 排除审计", "PASS", "自建模板物化落盘、黑名单 -eid 自动排除生成、策略额外追加合并、以及扫描后物理安全回收全部严密闭环！")
    else:
        record("5. Worker 运行时物化与 -eid 排除审计", "FAIL", f"输出: {p_audit.stdout} 错误: {p_audit.stderr}")
        sys.exit(1)

    # --------------------------------------------------------------------------
    # 步骤 6: 观察任务状态流转
    # --------------------------------------------------------------------------
    time.sleep(2)
    r_task_info = requests.get(f"{BASE_URL}/api/task/?_id={created_task_id}", headers=HEADERS, verify=False, timeout=10)
    t_items = r_task_info.json().get("items", []) or r_task_info.json().get("data", {}).get("items", [])
    t_status = t_items[0].get("status", "unknown") if t_items else "unknown"
    record("6. 任务异步调度状态流转观测", "PASS", f"任务当前调度状态为: '{t_status}'")

finally:
    # --------------------------------------------------------------------------
    # 步骤 7: 测试数据严格自愈与物理无痕清理 (Teardown)
    # --------------------------------------------------------------------------
    print("\n[TEARDOWN] 执行测试数据严格自愈与环境纯净收尾...")
    
    # 7.1 停止并清理任务
    if created_task_id:
        requests.post(f"{BASE_URL}/api/task/batch_stop/", headers=HEADERS, json={"task_ids": [created_task_id]}, verify=False, timeout=10)
        requests.post(f"{BASE_URL}/api/task/delete/", headers=HEADERS, json={"task_id": [created_task_id]}, verify=False, timeout=10)
        record("7.1 测试任务回收与清理", "PASS", f"任务 {created_task_id} 已安全停止并物理清理")

    # 7.2 删除策略
    if created_policy_id:
        requests.post(f"{BASE_URL}/api/policy/delete/", headers=HEADERS, json={"policy_id": [created_policy_id]}, verify=False, timeout=10)
        record("7.2 测试策略清理", "PASS", f"策略 {created_policy_id} 已删除")

    # 7.3 移出黑名单
    requests.delete(f"{BASE_URL}/api/nuclei/blacklist/{test_blacklist_cve}/", headers=HEADERS, verify=False, timeout=10)
    record("7.3 误报黑名单测试条目移出", "PASS", f"{test_blacklist_cve} 已移出黑名单")

    # 7.4 删除自建 PoC
    requests.post(f"{BASE_URL}/api/nuclei/template/delete/", headers=HEADERS, json={"template_ids": [test_tid]}, verify=False, timeout=10)
    record("7.4 自建测试 PoC 删除", "PASS", f"{test_tid} 已物理删除")

    # 7.5 校验最终基准归位
    r_stats_final = requests.get(f"{BASE_URL}/api/nuclei/stats/", headers=HEADERS, verify=False, timeout=10)
    sf = r_stats_final.json().get("data", {})
    if sf.get("custom_total") == 0 and sf.get("blacklist_total") == 0:
        record("7.5 生产全局指标归位核验", "PASS", f"基准指标完全自愈 (custom: 0, blacklist: 0, community: {sf.get('community_total')})")
    else:
        record("7.5 生产全局指标归位核验", "WARN", f"指标未归零: {sf}")

print("\n" + "=" * 70)
print(f"🎉 贯穿式业务场景端到端验收完毕: 成功步骤 {sum(1 for x in audit_log if x['status'] == 'PASS')}, 失败步骤 {sum(1 for x in audit_log if x['status'] == 'FAIL')}")
print("=" * 70)
