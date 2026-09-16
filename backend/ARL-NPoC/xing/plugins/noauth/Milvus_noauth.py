import json
from xing.core.BasePlugin import BasePlugin
from xing.utils import http_req
from xing.core import PluginType, SchemeType


class Plugin(BasePlugin):
    def __init__(self):
        super(Plugin, self).__init__()
        self.plugin_type = PluginType.POC
        self.vul_name = "Milvus 向量数据库未授权访问"
        self.app_name = 'Milvus'
        self.scheme = [SchemeType.HTTP, SchemeType.HTTPS]
        self.default_port = [9091, 19530]
        self.severity = "Critical"
        self.description = (
            "Milvus 向量数据库管理及 REST 接口未开启身份鉴权（默认常见于 9091 / 19530 端口），"
            "攻击者可直接通过 HTTP 接口未授权枚举数据库用户、获取集合元数据甚至操控向量知识库（如 CVE-2026-26190 类似风险面）。"
        )
        self.remediation = (
            "1. 在 milvus.yaml 中启用通用鉴权配置 (common.security.authorization: true)；\n"
            "2. 强制修改内置 root 默认口令；\n"
            "3. 限制 19530 及 9091 端口仅限受信任的业务微服务内网访问，杜绝公网直连。"
        )
        self.references = [
            "https://milvus.io/docs/authenticate.md",
            "https://github.com/milvus-io/milvus"
        ]

    def verify(self, target):
        # 1. 探针 A: /api/v1/credential/users (未授权用户枚举)
        user_endpoint = target + "/api/v1/credential/users"
        try:
            conn = http_req(user_endpoint)
        except Exception:
            conn = None

        if conn and conn.ok and b"<html" not in conn.content.lower():
            try:
                data = conn.json()
                if isinstance(data, dict) and "usernames" in data:
                    usernames = data.get("usernames", [])
                    self.logger.success(f"发现 Milvus 向量数据库未授权访问 {target}")
                    return (
                        f"URL: {user_endpoint} | 响应状态: 200 OK\n"
                        f"泄露组件: Milvus 向量数据库用户管理端点\n"
                        f"枚举用户列表: {usernames}\n"
                        f"影响评估: 未经身份验证可直接枚举数据库管理账户，暴露高危攻击面"
                    )
            except Exception:
                pass

        # 2. 探针 B: /api/v1/collections (未授权集合元数据)
        coll_endpoint = target + "/api/v1/collections"
        try:
            conn_coll = http_req(coll_endpoint)
        except Exception:
            conn_coll = None

        if conn_coll and conn_coll.ok and b"<html" not in conn_coll.content.lower():
            try:
                data = conn_coll.json()
                if isinstance(data, dict):
                    status_dict = data.get("status")
                    # 严格特征校验：必须命中 collection_names 列表，或者 status 对象中具备 Milvus 专属的 error_code/reason/extra_info 特征字段
                    has_colls = "collection_names" in data and isinstance(data["collection_names"], list)
                    has_milvus_status = (
                        isinstance(status_dict, dict)
                        and ("error_code" in status_dict or status_dict.get("error_code") == "Success")
                        and any(k in status_dict for k in ("reason", "extra_info", "error_code"))
                    )

                    if has_colls or has_milvus_status:
                        # 结合健康探针确认是否为 Milvus
                        health_conn = http_req(target + "/healthz")
                        if health_conn and b"ok" in health_conn.content.lower():
                            self.logger.success(f"发现 Milvus 向量数据库未授权访问 {target}")
                            colls = data.get("collection_names", [])
                            return (
                                f"URL: {coll_endpoint} | 响应状态: 200 OK\n"
                                f"泄露组件: Milvus 向量数据库集合端点\n"
                                f"集合列表: {colls[:10] if colls else '已获取接口权限'}\n"
                                f"影响评估: 未经身份验证可读取/枚举向量集合元数据"
                            )
            except Exception:
                pass

        return False
