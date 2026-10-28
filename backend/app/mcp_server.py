#coding: utf-8
"""
ARL-Next 原生异步 MCP SSE 服务 (Model Context Protocol 2024-11-05 规范)
- 异步高并发：基于 Python asyncio 标准库原生实现 HTTP/1.1 与 SSE 长连接，不占用 Web 线程池
- 协议完整性：支持 GET /sse 建立长连接握手与 POST /message 消息上行
- 双通道鉴权：支持 Header (Authorization: Bearer / Token) 与 URL Query (?token= / ?api_key=)
- 渐进式工具集：默认仅暴露只读资产画像与状态查询；环境变量 ARL_MCP_ENABLE_DISPATCH=true 时开启调度写入
"""

import asyncio
import hmac
import json
import logging
import os
import secrets
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Set

try:
    from app import utils
    from app.config import Config
    from app.mcp_asset import build_asset_profile, build_enterprise_profile, _clean_empty
except ImportError:
    # 允许作为单脚本在不同路径下启动加载
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from app import utils
    from app.config import Config
    from app.mcp_asset import build_asset_profile, build_enterprise_profile, _clean_empty

logger = logging.getLogger("arl_mcp")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [arl-mcp] %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "arl-next-remote"
SERVER_VERSION = "2.0.0"

# 工具定义集
TOOL_GET_ASSET_PROFILE = {
    "name": "get_asset_profile",
    "description": "获取指定目标（站点URL/IP/子域名）的综合资产画像，包括解析IP、开放端口与服务、Web指纹与标题、SSL证书、已知漏洞及敏感泄露等关联情报。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "资产标的，支持域名 (如 test.com)、IP (如 1.2.3.4) 或站点 URL (如 https://test.com:8443)"
            },
            "task_id": {
                "type": "string",
                "description": "可选。24位任务 ID。若指定则锁定该任务上下文，未指定则智能匹配最新任务或全局资产"
            }
        },
        "required": ["target"]
    }
}

TOOL_GET_ENTERPRISE_PROFILE = {
    "name": "get_enterprise_profile",
    "description": "获取指定企业标的（企业全称、简称、备案域名如 qq.com 或备案号）的全景生态资产画像与组织架构（包括工商背景、ICP备案网站、移动APP、微信小程序、公众号、企业微博、快应用及投资控股关系）。支持按资产分类下钻分页查询。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "企业标的，支持企业工商全称（如'深圳市腾讯计算机系统有限公司'）、企业商业简称（如'腾讯'）、根域名（如'qq.com'，自动反查所属企业）或 ICP 备案主体/备案号"
            },
            "category": {
                "type": "string",
                "enum": ["all", "web", "app", "mapp", "wechat", "weibo", "kapp", "invest"],
                "default": "all",
                "description": "查询维度：'all'（默认总览画像与各维度统计指标）；'web'（网站备案域名）；'app'（移动应用）；'mapp'（微信小程序）；'wechat'（微信公众号）；'weibo'（企业微博）；'kapp'（快应用）；'invest'（对外投资与控股子公司）"
            },
            "page": {
                "type": "integer",
                "default": 1,
                "description": "下钻指定 category 时的页码（从 1 开始）"
            },
            "size": {
                "type": "integer",
                "default": 20,
                "description": "下钻指定 category 时每页记录条数（默认 20，最大 100）"
            },
            "task_id": {
                "type": "string",
                "description": "可选。24位企业测绘任务 ID。若指定则直接锁定该任务历史数据"
            }
        },
        "required": ["target"]
    }
}

TOOL_SEARCH_ASSETS = {
    "name": "search_assets",
    "description": "按条件检索 ARL 资产库中的站点、IP、域名或漏洞记录。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "检索关键字（如域名关键词、服务名称、Web指纹或端口号）"
            },
            "asset_type": {
                "type": "string",
                "enum": ["site", "domain", "ip", "vuln"],
                "description": "资产类别，默认为 site（可选 site, domain, ip, vuln）"
            },
            "limit": {
                "type": "integer",
                "description": "返回条目上限（1-50，默认 10）"
            }
        },
        "required": ["query"]
    }
}

TOOL_GET_TASK_STATUS = {
    "name": "get_task_status",
    "description": "查询指定 24 位任务 ID 的扫描进度、运行状态与资产统计摘要。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "24 位 ARL 扫描任务 ID"
            }
        },
        "required": ["task_id"]
    }
}

TOOL_CREATE_SCAN_TASK = {
    "name": "create_scan_task",
    "description": "【受控调度】向 ARL 调度队列提交新的资产扫描任务（需在服务端启用 ARL_MCP_ENABLE_DISPATCH）。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "扫描任务名称"
            },
            "target": {
                "type": "string",
                "description": "扫描目标（多个目标以换行或逗号分隔）"
            },
            "policy_id": {
                "type": "string",
                "description": "可选。24位扫描策略模板 ID；未传则使用系统默认策略"
            }
        },
        "required": ["name", "target"]
    }
}

TOOL_STOP_SCAN_TASK = {
    "name": "stop_scan_task",
    "description": "【受控调度】紧急终止正在排队或进行中的 ARL 扫描任务。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "24 位 ARL 扫描任务 ID"
            }
        },
        "required": ["task_id"]
    }
}


class MCPSession:
    """管理单客户端 SSE 长连接会话与消息下行队列"""
    def __init__(self, session_id: str, auth_user: dict):
        self.session_id = session_id
        self.auth_user = auth_user
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.created_at = time.time()
        self.last_active = time.time()
        self.is_closed = False

    def touch(self):
        self.last_active = time.time()

    def close(self):
        self.is_closed = True


class MCPServer:
    """标准库原生异步 MCP SSE 服务器"""
    def __init__(self, host: str = "0.0.0.0", port: int = 5005):
        self.host = host
        self.port = port
        self.sessions: Dict[str, MCPSession] = {}
        self.server: Optional[asyncio.AbstractServer] = None
        self._dispatch_enabled = os.environ.get("ARL_MCP_ENABLE_DISPATCH", "").strip().lower() in ("true", "1", "yes")

    def get_supported_tools(self) -> list:
        tools = [TOOL_GET_ASSET_PROFILE, TOOL_GET_ENTERPRISE_PROFILE, TOOL_SEARCH_ASSETS, TOOL_GET_TASK_STATUS]
        if self._dispatch_enabled:
            tools.extend([TOOL_CREATE_SCAN_TASK, TOOL_STOP_SCAN_TASK])
        return tools

    def authenticate_token(self, token: str) -> Optional[dict]:
        """双通道凭据校验：比对系统 API_KEY、独立 MCP API Key 或 MongoDB user 会话"""
        if not getattr(Config, "AUTH", True):
            return {"username": "anonymous", "type": "no_auth", "scopes": ["asset:read", "task:dispatch"], "key_id": "none", "key_name": "anonymous"}

        if not token or not isinstance(token, str):
            return None

        clean_token = token.strip()
        if clean_token.startswith("Bearer "):
            clean_token = clean_token[7:].strip()

        # 1. 优先校验系统全局 API_KEY (内部运维调用，无需查库)
        api_key = getattr(Config, "API_KEY", "")
        if isinstance(api_key, str) and api_key and hmac.compare_digest(clean_token.encode(), api_key.encode()):
            return {
                "username": "ARL-API",
                "key_id": "legacy",
                "key_name": "[System API Key]",
                "scopes": ["asset:read", "task:dispatch"],
                "token": clean_token,
                "type": "api"
            }

        # 2. 校验专用 MCP API Key (以 arl_mcp_ 前缀标识)
        if clean_token.startswith("arl_mcp_"):
            try:
                import hashlib
                key_hash = hashlib.sha256(clean_token.encode('utf-8')).hexdigest()
                mcp_key = utils.conn_db('mcp_key').find_one({'key_hash': key_hash})
                if mcp_key:
                    if mcp_key.get('status') != 'active':
                        return None
                    expire_at = mcp_key.get('expire_at')
                    if expire_at and isinstance(expire_at, datetime):
                        now_dt = datetime.now() if expire_at.tzinfo is None else datetime.now(timezone.utc)
                        if expire_at < now_dt:
                            return None
                    return {
                        "username": mcp_key.get("created_by", "admin"),
                        "key_id": str(mcp_key["_id"]),
                        "key_name": mcp_key.get("name", "MCP-Key"),
                        "scopes": mcp_key.get("scopes", ["asset:read"]),
                        "token": clean_token,
                        "type": "mcp_key"
                    }
            except Exception as e:
                logger.warning(f"MCP Key auth lookup failed: {e}")
            return None

        # 3. 降级兼容存量 User 登录 Token
        try:
            now = datetime.now(timezone.utc)
            user = utils.conn_db('user').find_one({
                'token': clean_token,
                'token_expire_at': {'$gt': now}
            })
            if user:
                return {
                    "username": user.get("username", "admin"),
                    "key_id": "legacy",
                    "key_name": "[Legacy Token]",
                    "scopes": ["asset:read", "task:dispatch"],
                    "token": clean_token,
                    "type": "user"
                }
        except Exception as e:
            logger.warning(f"Database auth lookup failed: {e}")

        return None

    def _extract_token_from_request(self, headers: dict, query_params: dict) -> str:
        """优先提取 Header，兜底提取 Query 参数"""
        # 1. 优先从 Header 提取
        auth_header = headers.get("authorization", "") or headers.get("token", "")
        if auth_header:
            if auth_header.lower().startswith("bearer "):
                return auth_header[7:].strip()
            return auth_header.strip()

        # 2. 兜底从 URL Query 提取 (供 EventSource 或浏览器 Agent 使用)
        q_token = query_params.get("token", "") or query_params.get("api_key", "")
        if isinstance(q_token, list) and q_token:
            return q_token[0].strip()
        elif isinstance(q_token, str):
            return q_token.strip()

        return ""

    async def _record_audit_log(self, user_info: dict, tool_name: str, target: str, args: dict, result: dict, is_err: bool, duration_ms: int):
        """异步在 MongoDB 中留存 MCP 审计日志，并更新 Key 活跃信息"""
        def _sync_insert():
            try:
                status = "error" if is_err else "success"
                err_msg = ""
                summary = ""
                if is_err and isinstance(result, dict):
                    err_msg = str(result.get("message", ""))
                    if result.get("status") == "denied":
                        status = "denied"
                elif not is_err and isinstance(result, dict):
                    if tool_name == "get_asset_profile":
                        summary = f"状态: {result.get('status', 'ok')}"
                    elif tool_name == "get_enterprise_profile":
                        summary = f"企业: {result.get('enterprise_name') or target} (状态: {result.get('status', 'ok')})"
                    elif tool_name == "search_assets":
                        summary = f"命中 {result.get('total', 0)} 条记录"
                    elif tool_name == "get_task_status":
                        summary = f"任务状态: {result.get('status', 'unknown')}"
                    elif tool_name == "create_scan_task":
                        summary = f"新任务 ID: {result.get('task_id', '')}"
                    elif tool_name == "stop_scan_task":
                        summary = f"已停止任务: {result.get('task_id', '')}"

                p_str = json.dumps(args, ensure_ascii=False)
                if len(p_str) > 200:
                    p_str = p_str[:200] + "..."

                doc = {
                    "key_id": user_info.get("key_id", "legacy"),
                    "key_name": user_info.get("key_name", "[Legacy Token]"),
                    "client_ip": user_info.get("client_ip", ""),
                    "tool_name": tool_name,
                    "target": target,
                    "params_summary": p_str,
                    "status": status,
                    "duration_ms": duration_ms,
                    "summary": summary,
                    "error_message": err_msg,
                    "created_at": datetime.now(timezone.utc)
                }
                utils.conn_db('mcp_log').insert_one(doc)

                if user_info.get("type") == "mcp_key" and user_info.get("key_id") and user_info.get("key_id") != "legacy":
                    from bson import ObjectId
                    utils.conn_db('mcp_key').update_one(
                        {"_id": ObjectId(user_info["key_id"])},
                        {"$set": {
                            "last_used_at": datetime.now(timezone.utc),
                            "last_ip": user_info.get("client_ip", "")
                        }}
                    )
            except Exception as e:
                logger.warning(f"Failed to record audit log: {e}")

        await asyncio.to_thread(_sync_insert)

    async def handle_tool_call(self, name: str, args: dict, user_info: dict) -> Tuple[dict, bool]:
        """异步执行指定 Tool 并返回 (结果对象, is_error)，并记录审计日志"""
        start_time = time.time()
        target = str(args.get("target", "") or args.get("query", "") or args.get("task_id", "") or args.get("name", "")).strip()
        result, is_err = {}, False

        try:
            # 1. 检查全局配置与工具开关
            try:
                cfg = utils.conn_db('mcp_config').find_one({"_id": "global"}) or {}
                switches = cfg.get("tool_switches", {})
                max_search_limit = int(cfg.get("max_search_limit", 50))
            except Exception:
                switches = {}
                max_search_limit = 50

            if switches.get(name) is False:
                result, is_err = {"status": "denied", "message": f"Tool '{name}' is currently disabled in system settings"}, True
                return result, is_err

            # 2. 检查权限 Scope
            user_scopes = user_info.get("scopes", ["asset:read"])
            if name in ("create_scan_task", "stop_scan_task") and "task:dispatch" not in user_scopes:
                result, is_err = {"status": "denied", "message": "Permission denied: key lacks 'task:dispatch' scope"}, True
                return result, is_err

            # 3. 具体工具分流执行
            if name == "get_asset_profile":
                target_param = str(args.get("target", "")).strip()
                task_id = str(args.get("task_id", "")).strip()
                if not target_param:
                    result, is_err = {"status": "error", "message": "Missing required parameter: target"}, True
                    return result, is_err
                # 在线程池中执行同步的 MongoDB 聚合查询，不阻塞主事件循环
                profile = await asyncio.to_thread(build_asset_profile, target_param, task_id)
                is_err = isinstance(profile, dict) and profile.get("status") in ("auth_error", "error")
                result = profile
                return result, is_err

            elif name == "get_enterprise_profile":
                target_param = str(args.get("target", "")).strip()
                category = str(args.get("category", "all")).strip()
                task_id = str(args.get("task_id", "")).strip()
                page = args.get("page", 1)
                size = args.get("size", 20)
                if not target_param and not task_id:
                    result, is_err = {"status": "error", "message": "Missing required parameter: target"}, True
                    return result, is_err
                profile = await asyncio.to_thread(build_enterprise_profile, target_param, category, page, size, task_id)
                is_err = isinstance(profile, dict) and profile.get("status") in ("auth_error", "error")
                result = profile
                return result, is_err

            elif name == "search_assets":
                query = str(args.get("query", "")).strip()
                asset_type = str(args.get("asset_type", "site")).strip().lower()
                requested_limit = int(args.get("limit", 10))
                limit = min(max(requested_limit, 1), max_search_limit)
                if not query:
                    result, is_err = {"status": "error", "message": "Missing required parameter: query"}, True
                    return result, is_err

                def _query_db():
                    coll_name = asset_type if asset_type in ("site", "domain", "ip", "vuln") else "site"
                    filter_cond = {}
                    if coll_name == "site":
                        filter_cond = {"$or": [{"site": {"$regex": query, "$options": "i"}}, {"title": {"$regex": query, "$options": "i"}}]}
                        proj = {"favicon.data": 0, "body": 0, "header": 0}
                    elif coll_name == "domain":
                        filter_cond = {"domain": {"$regex": query, "$options": "i"}}
                        proj = None
                    elif coll_name == "ip":
                        filter_cond = {"ip": {"$regex": query, "$options": "i"}}
                        proj = None
                    else: # vuln
                        filter_cond = {"$or": [{"target": {"$regex": query, "$options": "i"}}, {"vul_name": {"$regex": query, "$options": "i"}}]}
                        proj = None
                    cursor = utils.conn_db(coll_name).find(filter_cond, proj).sort("_id", -1).limit(limit)
                    items = list(cursor)
                    # 转换 ObjectId 并精简空字段
                    for it in items:
                        if "_id" in it:
                            it["_id"] = str(it["_id"])
                    return _clean_empty({"items": items, "total": len(items), "type": coll_name})

                res = await asyncio.to_thread(_query_db)
                result, is_err = res, False
                return result, is_err

            elif name == "get_task_status":
                task_id = str(args.get("task_id", "")).strip()
                if not task_id or len(task_id) != 24:
                    result, is_err = {"status": "error", "message": "Invalid 24-character task_id"}, True
                    return result, is_err

                def _get_status():
                    from bson import ObjectId
                    t_doc = utils.conn_db('task').find_one({"_id": ObjectId(task_id)})
                    if not t_doc:
                        return {"status": "not_found", "message": f"Task {task_id} not found"}
                    return _clean_empty({
                        "task_id": str(t_doc.get("_id")),
                        "name": t_doc.get("name"),
                        "status": t_doc.get("status"),
                        "target": t_doc.get("target"),
                        "start_time": str(t_doc.get("start_time", "")),
                        "end_time": str(t_doc.get("end_time", "")),
                        "progress": t_doc.get("statistic", {})
                    })

                res = await asyncio.to_thread(_get_status)
                result, is_err = res, False
                return result, is_err

            elif name == "create_scan_task":
                dispatch_allowed = self._dispatch_enabled or switches.get("create_scan_task", False)
                if not dispatch_allowed:
                    result, is_err = {"status": "error", "message": "Task dispatching is disabled on this server"}, True
                    return result, is_err
                task_name = str(args.get("name", "")).strip()
                target_str = str(args.get("target", "")).strip()
                policy_id = str(args.get("policy_id", "")).strip()
                if not task_name or not target_str:
                    result, is_err = {"status": "error", "message": "Both name and target are required"}, True
                    return result, is_err

                def _dispatch_task():
                    from app.routes.task import TaskByPolicy
                    from app.utils.user import get_options_by_policy_id
                    # 查找默认策略
                    pol_id = policy_id
                    if not pol_id:
                        p_doc = utils.conn_db('policy').find_one({"is_default": True}) or utils.conn_db('policy').find_one({})
                        if p_doc:
                            pol_id = str(p_doc["_id"])
                    if not pol_id:
                        return {"status": "error", "message": "No scan policy available to submit task"}

                    options = get_options_by_policy_id(pol_id, "task")
                    from app.celerytask import celery
                    from bson import ObjectId
                    new_task_id = str(ObjectId())
                    task_doc = {
                        "_id": ObjectId(new_task_id),
                        "name": task_name,
                        "target": target_str,
                        "status": "waiting",
                        "policy_id": pol_id,
                        "options": options,
                        "start_time": datetime.now(timezone.utc)
                    }
                    utils.conn_db('task').insert_one(task_doc)
                    celery.send_task("task.arl_task", args=[new_task_id])
                    return {"status": "success", "task_id": new_task_id, "message": "Task submitted to queue"}

                res = await asyncio.to_thread(_dispatch_task)
                result, is_err = res, False
                return result, is_err

            elif name == "stop_scan_task":
                dispatch_allowed = self._dispatch_enabled or switches.get("stop_scan_task", False)
                if not dispatch_allowed:
                    result, is_err = {"status": "error", "message": "Task control is disabled on this server"}, True
                    return result, is_err
                task_id = str(args.get("task_id", "")).strip()
                if not task_id or len(task_id) != 24:
                    result, is_err = {"status": "error", "message": "Invalid 24-character task_id"}, True
                    return result, is_err

                def _stop_task():
                    from bson import ObjectId
                    utils.conn_db('task').update_one({"_id": ObjectId(task_id)}, {"$set": {"status": "stop"}})
                    return {"status": "success", "task_id": task_id, "message": "Task stopped"}

                res = await asyncio.to_thread(_stop_task)
                result, is_err = res, False
                return result, is_err

            result, is_err = {"status": "error", "message": f"Tool '{name}' not found"}, True
            return result, is_err
        except Exception as e:
            logger.error(f"Error handling tool call {name}: {e}", exc_info=True)
            result, is_err = {"status": "error", "message": str(e)}, True
            return result, is_err
        finally:
            duration_ms = int((time.time() - start_time) * 1000)
            asyncio.create_task(self._record_audit_log(user_info, name, target, args, result, is_err, duration_ms))

    async def handle_jsonrpc(self, req: dict, session: MCPSession) -> Optional[dict]:
        """处理遵循 JSON-RPC 2.0 规范的 MCP 核心协议报文"""
        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        # 1. 协议初始化握手
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {
                            "listChanged": False
                        }
                    },
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION
                    }
                }
            }

        # 2. 客户端通知 (无返回值)
        if method in ("notifications/initialized", "initialized"):
            return None

        # 3. 探活心跳
        if method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {}
            }

        # 4. 列出可用工具集
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.get_supported_tools()
                }
            }

        # 5. 调用工具
        if method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            profile_data, is_err = await self.handle_tool_call(tool_name, tool_args, session.auth_user)
            compact_json_str = json.dumps(profile_data, ensure_ascii=False, separators=(",", ":"))
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": compact_json_str
                        }
                    ],
                    "isError": is_err
                }
            }

        # 未知方法
        if req_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not recognized"
                }
            }
        return None

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理 HTTP/1.1 原生长连接与请求路由"""
        peer_name = writer.get_extra_info("peername")
        try:
            raw_line = await reader.readline()
            if not raw_line:
                writer.close()
                await writer.wait_closed()
                return

            line = raw_line.decode("utf-8", errors="replace").strip()
            parts = line.split(" ")
            if len(parts) < 3:
                writer.write(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n")
                await writer.drain()
                writer.close()
                return

            method, path_raw, _ = parts[0], parts[1], parts[2]

            # 解析 Headers
            headers = {}
            while True:
                h_line = await reader.readline()
                if not h_line or h_line == b"\r\n" or h_line == b"\n":
                    break
                h_str = h_line.decode("utf-8", errors="replace").strip()
                if ":" in h_str:
                    k, v = h_str.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            parsed_url = urllib.parse.urlparse(path_raw)
            path = parsed_url.path
            query_params = urllib.parse.parse_qs(parsed_url.query)

            # 鉴权检查:
            # 1. 尝试从 Header 或 Query 提取 token 并验证
            token = self._extract_token_from_request(headers, query_params)
            auth_user = self.authenticate_token(token) if token else None

            # 2. 若未携带显式 Token 且为 POST /message，支持基于激活状态的 Session ID 继承握手鉴权上下文
            if not auth_user and method == "POST" and path in ("/message", "/mcp/message"):
                sid = ""
                if "sessionid" in query_params:
                    sid = query_params["sessionid"][0]
                elif "sessionId" in query_params:
                    sid = query_params["sessionId"][0]
                elif "x-session-id" in headers:
                    sid = headers["x-session-id"]

                if sid and sid in self.sessions:
                    existing_session = self.sessions[sid]
                    if not existing_session.is_closed and existing_session.auth_user:
                        auth_user = existing_session.auth_user

            if not auth_user:
                err_resp = json.dumps({"error": "Unauthorized", "message": "Invalid or missing token / session"}, ensure_ascii=False)
                writer.write(
                    f"HTTP/1.1 401 Unauthorized\r\n"
                    f"Content-Type: application/json; charset=utf-8\r\n"
                    f"Content-Length: {len(err_resp.encode('utf-8'))}\r\n"
                    f"Connection: close\r\n\r\n{err_resp}".encode("utf-8")
                )
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

            client_ip = headers.get("x-forwarded-for", "").split(",")[0].strip() or headers.get("x-real-ip", "").strip()
            if not client_ip:
                client_ip = peer_name[0] if peer_name and isinstance(peer_name, tuple) else ""
            auth_user["client_ip"] = client_ip

            # ==================== 路由 1: GET /sse 或 /mcp/sse (建立 SSE 长连接) ====================
            if method == "GET" and path in ("/sse", "/mcp/sse"):
                session_id = secrets.token_urlsafe(24)
                session = MCPSession(session_id, auth_user)
                self.sessions[session_id] = session
                logger.info(f"SSE Client connected: session={session_id}, user={auth_user.get('username')}, peer={peer_name}")

                # 构造响应头 (严格按照 SSE 规范要求设置长连接与防缓冲)
                header_resp = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: text/event-stream; charset=utf-8\r\n"
                    "Cache-Control: no-cache, no-transform\r\n"
                    "Connection: keep-alive\r\n"
                    "X-Accel-Buffering: no\r\n"
                    "\r\n"
                )
                writer.write(header_resp.encode("utf-8"))
                await writer.drain()

                # 推送初始化 endpoint 事件（告知 Agent 后续上行消息的 URL）
                # 兼容反代路径与直连路径
                endpoint_url = f"/mcp/message?sessionId={session_id}"
                endpoint_event = f"event: endpoint\r\ndata: {endpoint_url}\r\n\r\n"
                writer.write(endpoint_event.encode("utf-8"))
                await writer.drain()

                # 事件循环：并发分发队列事件与即时断开探测
                async def _send_events():
                    while not session.is_closed:
                        try:
                            event_data = await asyncio.wait_for(session.queue.get(), timeout=15.0)
                            msg_str = json.dumps(event_data, ensure_ascii=False)
                            sse_block = f"event: message\r\ndata: {msg_str}\r\n\r\n"
                            writer.write(sse_block.encode("utf-8"))
                            await writer.drain()
                        except asyncio.TimeoutError:
                            writer.write(b": keepalive\r\n\r\n")
                            await writer.drain()

                async def _watch_disconnect():
                    try:
                        while not session.is_closed:
                            data = await reader.read(1024)
                            if not data:
                                break
                    except Exception:
                        pass
                    finally:
                        session.close()

                send_task = asyncio.create_task(_send_events())
                watch_task = asyncio.create_task(_watch_disconnect())
                try:
                    await asyncio.wait(
                        [send_task, watch_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                except Exception:
                    pass
                finally:
                    session.close()
                    send_task.cancel()
                    watch_task.cancel()
                    self.sessions.pop(session_id, None)
                    logger.info(f"SSE Client disconnected: session={session_id}")
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass
                return

            # ==================== 路由 2: POST /message 或 /mcp/message (上行消息处理) ====================
            elif method == "POST" and path in ("/message", "/mcp/message"):
                sid = ""
                if "sessionid" in query_params:
                    sid = query_params["sessionid"][0]
                elif "sessionId" in query_params:
                    sid = query_params["sessionId"][0]
                elif "x-session-id" in headers:
                    sid = headers["x-session-id"]

                session = self.sessions.get(sid)
                if not session or session.is_closed:
                    err_resp = json.dumps({"error": "SessionNotFound", "message": f"Session '{sid}' expired or not found"}, ensure_ascii=False)
                    writer.write(
                        f"HTTP/1.1 404 Not Found\r\n"
                        f"Content-Type: application/json; charset=utf-8\r\n"
                        f"Content-Length: {len(err_resp.encode('utf-8'))}\r\n"
                        f"Connection: close\r\n\r\n{err_resp}".encode("utf-8")
                    )
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    return

                # 读取 Body
                content_len = int(headers.get("content-length", 0))
                body_bytes = await reader.readexactly(content_len) if content_len > 0 else b""
                try:
                    req_json = json.loads(body_bytes.decode("utf-8"))
                except Exception as e:
                    err_resp = json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}})
                    writer.write(f"HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\nContent-Length: {len(err_resp)}\r\n\r\n{err_resp}".encode("utf-8"))
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    return

                session.touch()
                # 立即向客户端返回 202 Accepted 确认投递
                resp_ack = b"HTTP/1.1 202 Accepted\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: 8\r\n\r\nAccepted"
                writer.write(resp_ack)
                await writer.drain()
                writer.close()
                await writer.wait_closed()

                # 异步处理 JSON-RPC 逻辑并将结果推入该 session 的下行队列
                async def _dispatch_rpc():
                    res = await self.handle_jsonrpc(req_json, session)
                    if res is not None:
                        await session.queue.put(res)

                asyncio.create_task(_dispatch_rpc())
                return

            # 未识别路由
            writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        except Exception as ex:
            logger.error(f"Error handling request from {peer_name}: {ex}", exc_info=True)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def start(self):
        """启动异步监听"""
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        addr = self.server.sockets[0].getsockname()
        logger.info(f"ARL-Next Native MCP SSE Server started on {addr[0]}:{addr[1]}")
        logger.info(f"Supported tools: {[t['name'] for t in self.get_supported_tools()]}")
        async with self.server:
            await self.server.serve_forever()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ARL-Next Native Asynchronous MCP SSE Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5005, help="Port to bind (default: 5005)")
    args = parser.parse_args()

    server = MCPServer(host=args.host, port=args.port)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server terminated by user.")


if __name__ == "__main__":
    main()
