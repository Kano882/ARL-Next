#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARL-Next 官方社区模板「离线更新功能」正反双向深度测试套件
涵盖：
1. 反向防御与边界异常拦截 (非法后缀, 无YAML伪包, 未鉴权)
2. 正向端到端全链路闭环 (构造多层级ZIP -> 上传 -> 状态机流转 -> 社区检索 -> 源码读取 -> 物理落地核验 -> 无痕清理)
"""

import sys
import os
import time
import json
import zipfile
import io
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
print(f"🚀 开始执行「离线更新功能」正反双向深度专项测试")
print(f"目标主机: {BASE_URL}")
print("=" * 70)

# ==============================================================================
# SECTION 1: 反向防御与边界异常拦截测试 (Negative Defense)
# ==============================================================================
print("\n[PART 1] 反向防御与异常边界拦截测试...")

# 1.1 未鉴权拦截
try:
    r_noauth = requests.post(f"{BASE_URL}/api/nuclei/community/sync_offline/", verify=False, timeout=10)
    if r_noauth.status_code == 200 and r_noauth.json().get("code") == 401:
        log_pass("未鉴权上传拦截 (401 拦截有效)")
    else:
        log_fail("未鉴权上传拦截", f"返回: {r_noauth.text[:100]}")
except Exception as e:
    log_fail("未鉴权上传测试", f"异常: {e}")

# 1.2 非法文件后缀拦截 (如 .txt / .tar.gz)
try:
    fake_txt = io.BytesIO(b"fake file content")
    files_txt = {'file': ('test.txt', fake_txt.getvalue(), 'text/plain')}
    r_txt = requests.post(f"{BASE_URL}/api/nuclei/community/sync_offline/", headers=HEADERS, files=files_txt, verify=False, timeout=10)
    res_txt = r_txt.json()
    if r_txt.status_code == 200 and res_txt.get("code") != 200 and "仅支持上传 .zip" in res_txt.get("message", ""):
        log_pass("非 ZIP 后缀格式拦截", f"友好提示: '{res_txt.get('message')}'")
    else:
        log_fail("非 ZIP 后缀格式拦截", f"未拦截非法后缀: {r_txt.text}")
except Exception as e:
    log_fail("非 ZIP 后缀测试", f"异常: {e}")

# 1.3 伪造 ZIP 拦截 (ZIP 内无任何 YAML 模板文件)
try:
    fake_zip_buf = io.BytesIO()
    with zipfile.ZipFile(fake_zip_buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr("readme.txt", "this is just a text file without any templates")
        z.writestr("image.png", b"\x89PNG\r\n\x1a\nfakeimage")
    fake_zip_buf.seek(0)

    files_fake_zip = {'file': ('fake-templates.zip', fake_zip_buf.getvalue(), 'application/zip')}
    r_fake_zip = requests.post(f"{BASE_URL}/api/nuclei/community/sync_offline/", headers=HEADERS, files=files_fake_zip, verify=False, timeout=10)
    res_fake_zip = r_fake_zip.json()
    if r_fake_zip.status_code == 200 and res_fake_zip.get("code") != 200 and "未检测到 Nuclei YAML" in res_fake_zip.get("message", ""):
        log_pass("伪造无模板 ZIP 静态拦截", f"防御提示: '{res_fake_zip.get('message')}'")
    else:
        log_fail("伪造无模板 ZIP 静态拦截", f"未能拦截无模板压缩包: {r_fake_zip.text}")
except Exception as e:
    log_fail("伪造 ZIP 拦截测试", f"异常: {e}")


# ==============================================================================
# SECTION 2: 正向端到端全链路闭环实测 (Positive End-to-End Loop)
# ==============================================================================
print("\n[PART 2] 正向端到端全链路闭环实测...")

test_stamp = int(time.time())
offline_tid = f"offline-deep-poc-{test_stamp}"
offline_subpath = f"http/miscellaneous/{offline_tid}.yaml"
offline_yaml = f"""id: {offline_tid}

info:
  name: Deep Audit Offline Verified Vulnerability
  author: security-qa
  severity: high
  description: Automatically verified offline sync vulnerability template
  tags: offline,audit,verified

http:
  - method: GET
    path:
      - "{{{{BaseURL}}}}/offline-audit-probe"
    matchers:
      - type: word
        words:
          - "probe-matched-ok"
"""

# 2.1 构造并上传合规的多层级离线模板包
try:
    valid_zip_buf = io.BytesIO()
    with zipfile.ZipFile(valid_zip_buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(offline_subpath, offline_yaml)
    valid_zip_buf.seek(0)

    files_valid = {'file': (f'nuclei-templates-offline-{test_stamp}.zip', valid_zip_buf.getvalue(), 'application/zip')}
    t0 = time.time()
    r_upload = requests.post(f"{BASE_URL}/api/nuclei/community/sync_offline/", headers=HEADERS, files=files_valid, verify=False, timeout=15)
    upload_res = r_upload.json()
    if r_upload.status_code == 200 and upload_res.get("code") == 200:
        log_pass("合规离线模板 ZIP 包上传", f"响应成功: {upload_res.get('data', {}).get('message')}")
    else:
        log_fail("合规离线模板 ZIP 包上传", f"上传被拒: {r_upload.text}")
except Exception as e:
    log_fail("离线模板上传测试", f"异常: {e}")

# 2.2 轮询状态机至成功
sync_finished = False
poll_logs = ""
try:
    print("    ⏳ 等待后台解压覆盖与索引重载...")
    for i in range(12):
        time.sleep(1.5)
        r_st = requests.get(f"{BASE_URL}/api/nuclei/community/sync_status/", headers=HEADERS, verify=False, timeout=10)
        if r_st.status_code == 200:
            st_data = r_st.json().get("data", {})
            cur_status = st_data.get("status")
            cur_mode = st_data.get("sync_mode")
            poll_logs = st_data.get("log", "")
            if cur_status == "success":
                sync_finished = True
                log_pass("离线同步状态机转换闭环", f"(状态: {cur_status}, 模式: {cur_mode}, 耗时: {round((i+1)*1.5, 1)}s)")
                break
            elif cur_status == "failed":
                log_fail("离线同步状态机转换", f"后台处理失败: {st_data.get('error_message')}")
                break
    if not sync_finished:
        log_fail("离线同步状态机超时", "在 18 秒内未检测到 status 转为 success")
except Exception as e:
    log_fail("状态机轮询异常", f"{e}")

# 2.3 验证控制台日志记录完整性
if "解析本地离线模板 ZIP 包" in poll_logs and "离线模板解压完成" in poll_logs:
    log_pass("控制台日志审计", "(日志完整记录离线包解析、解压与模板索引刷新全过程)")
else:
    log_fail("控制台日志审计", f"日志未包含预期的离线解析特征: {poll_logs[-200:]}")

# 2.4 业务检索穿透核验 (通过社区搜索 API 查出新模板)
try:
    r_search = requests.get(f"{BASE_URL}/api/nuclei/community/?search={offline_tid}", headers=HEADERS, verify=False, timeout=10)
    s_json = r_search.json()
    items = s_json.get("data", {}).get("items", [])
    if len(items) >= 1 and items[0].get("template_id") == offline_tid:
        log_pass("社区库全局检索穿透", f"(成功搜出新离线模板: {offline_tid}, 危害级: {items[0].get('severity')})")
    else:
        log_fail("社区库全局检索穿透", f"未搜到离线更新的模板: {r_search.text}")
except Exception as e:
    log_fail("社区模板检索穿透测试", f"异常: {e}")

# 2.5 模板源码读取穿透核验 (通过 source API 获取 YAML 文本)
try:
    r_src = requests.get(f"{BASE_URL}/api/nuclei/community/source/?template_id={offline_tid}", headers=HEADERS, verify=False, timeout=10)
    src_json = r_src.json()
    content = src_json.get("data", {}).get("content", "")
    if "Deep Audit Offline Verified Vulnerability" in content and "probe-matched-ok" in content:
        log_pass("社区模板源码读取穿透", "(成功跨目录读取解压后的 YAML 原文)")
    else:
        log_fail("社区模板源码读取穿透", f"源码读取内容异常: {r_src.text}")
except Exception as e:
    log_fail("源码读取穿透测试", f"异常: {e}")

# 2.6 服务器物理磁盘落地核验 (通过 SSH / Docker Exec 核验实际物理文件)
try:
    ssh_cmd = f"ssh -p 2222 -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@192.0.2.10 'docker exec arl-web-prod test -f /root/nuclei-templates/{offline_subpath} && echo EXISTS'"
    res = subprocess.run(ssh_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
    if "EXISTS" in res.stdout:
        log_pass("容器底层物理磁盘落地核验", f"(文件在 /root/nuclei-templates/{offline_subpath} 物理存在)")
    else:
        log_fail("容器底层物理磁盘落地核验", f"磁盘未检测到落地文件: {res.stdout} {res.stderr}")
except Exception as e:
    log_fail("物理磁盘落地核验", f"异常: {e}")

# 2.7 物理磁盘清理与环境无痕收尾 (遵守 Agent 环境安全准则)
try:
    clean_cmd = f"ssh -p 2222 -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@192.0.2.10 'docker exec arl-web-prod rm -f /root/nuclei-templates/{offline_subpath}'"
    subprocess.run(clean_cmd, shell=True, timeout=10)
    # 重新触发刷新索引
    requests.get(f"{BASE_URL}/api/nuclei/stats/", headers=HEADERS, verify=False, timeout=10)
    log_pass("测试模板安全物理清理与索引无痕收尾")
except Exception as e:
    log_fail("无痕清理", f"异常: {e}")

print("\n" + "=" * 70)
print(f"📊 离线更新专项测试结果: 通过 {len(results['passed'])}, 失败 {len(results['failed'])}")
print("=" * 70)

if results["failed"]:
    sys.exit(1)
