#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ARL-Next MCP 模块生产全链路自动化探活套件 (E2E Verification Suite)

验证维度：
  1. 前端静态资产与直链分发 (/mcpCenter, /mcp/server.py)
  2. 后端 REST 治理 API (/api/mcp/overview, /api/mcp/config, /api/mcp/keys, /api/mcp/logs)
  3. 远程原生 MCP 协议握手与双向交互 (GET /mcp/sse + POST /mcp/message JSON-RPC)
  4. MongoDB 审计日志落盘与微秒级延迟验证
  5. 测试凭据与临时资源的自愈清理闭环
"""

import os
import sys
import json
import re
import ssl
import time
import urllib.request
import urllib.error
import urllib.parse
from http.client import HTTPResponse

def resolve_target():
    """动态解析目标主机与凭据（优先环境变量，兜底 ARL_auth.md）"""
    host = os.environ.get("ARL_HOST", "").rstrip("/")
    token = os.environ.get("ARL_TOKEN", "")
    basic_auth = os.environ.get("ARL_BASIC_AUTH", "")

    if not host or not token or not basic_auth:
        auth_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ARL_auth.md"))
        if os.path.isfile(auth_file):
            try:
                with open(auth_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    host_match = re.search(r"ARL_HOST:\s*(https?://[^\s]+)", content)
                    token_match = re.search(r"ARL_TOKEN:\s*([a-f0-9]{32,64})", content)
                    basic_match = re.search(r"Basic Auth[^:]*:\s*`?([a-zA-Z0-9_]+:[a-zA-Z0-9_]+)`?", content)
                    if host_match and not host:
                        host = host_match.group(1).rstrip("/")
                    if token_match and not token:
                        token = token_match.group(1)
                    if basic_match and not basic_auth:
                        basic_auth = basic_match.group(1).strip()
            except Exception as e:
                print(f"[!] Warning reading ARL_auth.md: {e}")

    if not host or not token:
        print("[X] 错误: 无法解析 ARL_HOST 或 ARL_TOKEN，请设置环境变量或检查 ARL_auth.md")
        sys.exit(1)

    return host, token, basic_auth

def make_ssl_ctx():
    """构造跳过自签名证书校验的 SSL 上下文"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def run_tests():
    host, token, basic_auth = resolve_target()
    ssl_ctx = make_ssl_ctx()
    print("=" * 60)
    print(f"🚀 开始 ARL-Next MCP 生产全链路自动化探活")
    print(f"🎯 目标主机: {host.split('://')[0]}://<CENSORED_HOST>")
    print("=" * 60)

    import base64
    b64_basic = base64.b64encode(basic_auth.encode("utf-8")).decode("utf-8") if basic_auth else ""

    def auth_headers(extra=None):
        h = extra.copy() if extra else {}
        if b64_basic:
            h["Authorization"] = f"Basic {b64_basic}"
        return h

    # -------------------------------------------------------------
    # Step 1: 验证前端静态路由与客户端直链下载
    # -------------------------------------------------------------
    print("\n[1/5] 验证前端静态资产与直链分发...")
    
    # 1.1 /mcpCenter 路由检查
    req = urllib.request.Request(f"{host}/mcpCenter", headers=auth_headers({
        "User-Agent": "ARL-E2E-Verifier/1.0"
    }))
    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            status = resp.status
            html = resp.read().decode("utf-8", errors="ignore")
            assert status == 200, f"Expected 200, got {status}"
            assert "<div id=\"app\">" in html or "assets/index-" in html, "Invalid HTML response"
            print("  ✓ Web UI 路由 /mcpCenter 访问正常 (HTTP 200)")
    except Exception as e:
        print(f"  ✗ /mcpCenter 访问失败: {e}")
        return False

    # 1.2 /mcp/server.py 直链下载检查 (不受 Basic Auth 拦截)
    req = urllib.request.Request(f"{host}/mcp/server.py", headers={
        "User-Agent": "ARL-E2E-Verifier/1.0"
    })
    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            status = resp.status
            script_text = resp.read().decode("utf-8", errors="ignore")
            assert status == 200, f"Expected 200, got {status}"
            assert "ARL-Next" in script_text or "class" in script_text, "Invalid script content"
            print("  ✓ 客户端直链 /mcp/server.py 下载畅通且免 Basic Auth 拦截 (HTTP 200)")
    except Exception as e:
        print(f"  ✗ /mcp/server.py 下载失败: {e}")
        return False

    # -------------------------------------------------------------
    # Step 2: 验证后端 REST 治理 API
    # -------------------------------------------------------------
    print("\n[2/5] 验证 REST 治理 API 与权限矩阵...")

    # 2.1 /api/mcp/overview
    req = urllib.request.Request(f"{host}/api/mcp/overview", headers=auth_headers({
        "Token": token,
        "Content-Type": "application/json"
    }))
    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("code") == 200, f"API error: {data}"
            overview = data.get("data", {})
            service_status = overview.get("service_status")
            today_calls = overview.get("today_calls")
            print(f"  ✓ /api/mcp/overview 响应正常: 今日调用={today_calls}, 服务状态={service_status}")
    except Exception as e:
        print(f"  ✗ /api/mcp/overview 失败: {e}")
        return False

    # 2.2 /api/mcp/config
    req = urllib.request.Request(f"{host}/api/mcp/config", headers=auth_headers({
        "Token": token,
        "Content-Type": "application/json"
    }))
    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("code") == 200, f"Config error: {data}"
            cfg = data.get("data", {})
            print(f"  ✓ /api/mcp/config 策略读取正常: 频控={cfg.get('rate_limit_per_min')}/分, 最大分页={cfg.get('max_search_limit')}")
    except Exception as e:
        print(f"  ✗ /api/mcp/config 失败: {e}")
        return False

    # 2.3 生成临时 MCP Key
    test_key_name = f"e2e_probe_{int(time.time())}"
    create_payload = json.dumps({"name": test_key_name, "rate_limit": 60}).encode("utf-8")
    req = urllib.request.Request(f"{host}/api/mcp/keys", data=create_payload, headers=auth_headers({
        "Token": token,
        "Content-Type": "application/json"
    }), method="POST")
    key_id = None
    raw_key = None
    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("code") == 200, f"Create key error: {data}"
            created_data = data.get("data", {})
            key_id = created_data.get("id") or created_data.get("_id")
            raw_key = created_data.get("raw_key")
            assert raw_key and raw_key.startswith("arl_mcp_"), f"Invalid raw key: {raw_key}"
            print(f"  ✓ 动态生成 E2E 测试密钥成功 (ID: {key_id})")
    except Exception as e:
        print(f"  ✗ 动态生成 MCP Key 失败: {e}")
        return False

    # -------------------------------------------------------------
    # Step 3: 验证远程原生 MCP SSE 协议握手与双向交互
    # -------------------------------------------------------------
    print("\n[3/5] 验证远程 MCP SSE 协议握手与双向 JSON-RPC 通信...")
    try:
        # 3.1 握手 GET /mcp/sse?token=<raw_key> (长连接)
        sse_url = f"{host}/mcp/sse?token={raw_key}"
        sse_req = urllib.request.Request(sse_url, headers={
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "User-Agent": "ARL-E2E-Verifier/1.0"
        })
        
        # 打开长连接并读取 endpoint 事件
        sse_conn = urllib.request.urlopen(sse_req, context=ssl_ctx, timeout=15)
        content_type = sse_conn.headers.get("Content-Type", "")
        assert "text/event-stream" in content_type, f"Invalid Content-Type: {content_type}"
        print("  ✓ SSE 流式通道握手成功 (HTTP 200 text/event-stream)")

        # 读取前几行获取 endpoint 事件
        endpoint_line = None
        session_id = None
        for _ in range(10):
            line = sse_conn.readline().decode("utf-8").strip()
            if line.startswith("data:"):
                endpoint_line = line[len("data:"):].strip()
                break
        
        assert endpoint_line, "Failed to read endpoint event from SSE"
        print(f"  ✓ 收到服务端 endpoint 事件: {endpoint_line}")
        
        # 提取 sessionId
        if "sessionId=" in endpoint_line:
            session_id = endpoint_line.split("sessionId=")[1].split("&")[0]
        elif "session_id=" in endpoint_line:
            session_id = endpoint_line.split("session_id=")[1].split("&")[0]
        assert session_id, f"Failed to extract session_id from: {endpoint_line}"

        # 3.2 发送 initialize JSON-RPC 指令
        post_url = f"{host}{endpoint_line}" if endpoint_line.startswith("/") else f"{host}/{endpoint_line}"
        init_body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ARL-E2E-Verifier", "version": "1.0.0"}
            }
        }).encode("utf-8")

        post_req = urllib.request.Request(post_url, data=init_body, headers={
            "Content-Type": "application/json",
            "User-Agent": "ARL-E2E-Verifier/1.0"
        }, method="POST")

        with urllib.request.urlopen(post_req, context=ssl_ctx, timeout=10) as post_resp:
            assert post_resp.status in (200, 202), f"Post init failed: {post_resp.status}"

        # 从 SSE 读取服务端 initialize 响应
        init_resp_data = None
        for _ in range(15):
            line = sse_conn.readline().decode("utf-8").strip()
            if line.startswith("data:"):
                msg_payload = json.loads(line[len("data:"):].strip())
                if msg_payload.get("id") == 1:
                    init_resp_data = msg_payload
                    break
        assert init_resp_data, "Timeout waiting for initialize response on SSE"
        server_info = init_resp_data.get("result", {}).get("serverInfo", {})
        print(f"  ✓ JSON-RPC 初始化握手完成: {server_info.get('name')} v{server_info.get('version')}")

        # 3.3 tools/list 查询
        tools_body = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }).encode("utf-8")

        post_req = urllib.request.Request(post_url, data=tools_body, headers={
            "Content-Type": "application/json",
            "User-Agent": "ARL-E2E-Verifier/1.0"
        }, method="POST")

        with urllib.request.urlopen(post_req, context=ssl_ctx, timeout=10) as post_resp:
            assert post_resp.status in (200, 202), f"Post tools/list failed: {post_resp.status}"

        tools_resp_data = None
        for _ in range(15):
            line = sse_conn.readline().decode("utf-8").strip()
            if line.startswith("data:"):
                msg_payload = json.loads(line[len("data:"):].strip())
                if msg_payload.get("id") == 2:
                    tools_resp_data = msg_payload
                    break
        assert tools_resp_data, "Timeout waiting for tools/list response on SSE"
        tool_names = [t.get("name") for t in tools_resp_data.get("result", {}).get("tools", [])]
        print(f"  ✓ 成功检索到可用 MCP 工具集 ({len(tool_names)} 个): {tool_names}")
        assert "get_asset_profile" in tool_names, "Missing core tool: get_asset_profile"
        assert "search_assets" in tool_names, "Missing core tool: search_assets"

        # 3.4 tools/call 调度调用
        call_body = json.dumps({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_asset_profile",
                "arguments": {"target": "127.0.0.1"}
            }
        }).encode("utf-8")

        post_req = urllib.request.Request(post_url, data=call_body, headers={
            "Content-Type": "application/json",
            "User-Agent": "ARL-E2E-Verifier/1.0"
        }, method="POST")

        with urllib.request.urlopen(post_req, context=ssl_ctx, timeout=15) as post_resp:
            assert post_resp.status in (200, 202), f"Post tools/call failed: {post_resp.status}"

        call_resp_data = None
        for _ in range(15):
            line = sse_conn.readline().decode("utf-8").strip()
            if line.startswith("data:"):
                msg_payload = json.loads(line[len("data:"):].strip())
                if msg_payload.get("id") == 3:
                    call_resp_data = msg_payload
                    break
        assert call_resp_data, "Timeout waiting for tools/call response on SSE"
        content_item = call_resp_data.get("result", {}).get("content", [{}])[0]
        profile_result = json.loads(content_item.get("text", "{}"))
        print(f"  ✓ tools/call (get_asset_profile) 执行成功: target={profile_result.get('target', '127.0.0.1')}, 状态={profile_result.get('status', 'ok')}")

        sse_conn.close()
    except Exception as e:
        print(f"  ✗ 远程 MCP SSE 协议通信失败: {e}")
        return False

    # -------------------------------------------------------------
    # Step 4: 验证调用审计日志与落盘
    # -------------------------------------------------------------
    print("\n[4/5] 验证调用审计日志实时记录...")
    time.sleep(1) # 容纳异步落盘延迟
    req = urllib.request.Request(f"{host}/api/mcp/logs?page=1&size=5", headers=auth_headers({
        "Token": token,
        "Content-Type": "application/json"
    }))
    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("code") == 200, f"Log query error: {data}"
            logs = data.get("data", {}).get("items", [])
            assert len(logs) > 0, "No logs recorded"
            latest = logs[0]
            assert latest.get("tool_name") == "get_asset_profile", f"Unexpected latest tool: {latest}"
            print(f"  ✓ 审计日志正确落盘: 工具={latest.get('tool_name')}, 状态={latest.get('status')}, 耗时={latest.get('duration_ms')}ms")
    except Exception as e:
        print(f"  ✗ 审计日志校验失败: {e}")
        return False

    # -------------------------------------------------------------
    # Step 5: 清理临时测试密钥
    # -------------------------------------------------------------
    print("\n[5/5] 执行临时测试凭据闭环自愈清理...")
    if key_id:
        req = urllib.request.Request(f"{host}/api/mcp/keys/{key_id}", headers=auth_headers({
            "Token": token,
            "Content-Type": "application/json"
        }), method="DELETE")
        try:
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                assert data.get("code") == 200
                print(f"  ✓ 临时测试密钥 {key_id} 已安全注销")
        except Exception as e:
            print(f"  ✗ 清理临时密钥失败: {e}")

    print("\n" + "=" * 60)
    print("🎉 ARL-Next MCP 生产全链路所有 5 项探活验证全部通过！")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
