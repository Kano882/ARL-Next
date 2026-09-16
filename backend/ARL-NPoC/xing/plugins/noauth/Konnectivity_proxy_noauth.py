import re
import socket
import ssl
from xing.core.BasePlugin import BasePlugin
from xing.utils import http_req
from xing.core import PluginType, SchemeType


class Plugin(BasePlugin):
    def __init__(self):
        super(Plugin, self).__init__()
        self.plugin_type = PluginType.POC
        self.vul_name = "Kubernetes Konnectivity 代理未授权访问"
        self.app_name = 'Kubernetes-Konnectivity'
        self.scheme = [SchemeType.HTTPS, SchemeType.HTTP]
        self.default_port = [8090]
        self.severity = "Critical"
        self.description = (
            "Kubernetes apiserver-network-proxy (Konnectivity) 隧道代理未开启客户端证书认证（mTLS）或访问鉴权，"
            "攻击者可直接利用 HTTP CONNECT 方法在公网与集群内网建立任意 TCP 双向透传隧道，造成内网穿透与越界访问风险。"
        )
        self.remediation = (
            "1. 限制该端口仅集群受信任控制面节点内网互联，撤销公网监听；\n"
            "2. 强制启用客户端 mTLS 双向证书认证（对齐 konnectivity-agent 端口策略），禁止匿名透传。"
        )
        self.references = [
            "https://github.com/kubernetes-sigs/apiserver-network-proxy",
            "https://kubernetes.io/docs/tasks/extend-kubernetes/setup-konnectivity/"
        ]

    def _probe_cert_and_fingerprint(self, target):
        """
        探测目标是否具有 Konnectivity 代理特征：
        1. HTTP GET 响应 405 且包含 "this proxy only supports CONNECT passthrough"
        2. TLS 证书主体包含 konnectivity-server
        """
        is_konnectivity = False
        cert_info = ""

        # 1. HTTP 探测
        try:
            conn = http_req(target)
            if conn and conn.status_code == 405:
                if b"this proxy only supports connect passthrough" in conn.content.lower():
                    is_konnectivity = True
        except Exception:
            pass

        # 2. TLS 证书探测
        host = self.target_info["host"]
        port = self.target_info["port"]
        raw_s = None
        tls_s = None
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            raw_s = socket.create_connection((host, port), timeout=4)
            tls_s = ctx.wrap_socket(raw_s)
            cert = tls_s.getpeercert(binary_form=True)
            if cert:
                cert_text = cert.decode("latin1", errors="ignore")
                if "konnectivity" in cert_text.lower():
                    is_konnectivity = True
                    cert_info = "TLS证书匹配 konnectivity-server"
        except Exception:
            pass
        finally:
            if tls_s:
                try:
                    tls_s.close()
                except Exception:
                    pass
            elif raw_s:
                try:
                    raw_s.close()
                except Exception:
                    pass

        return is_konnectivity, cert_info

    def _test_connect_bypass(self, host, port, use_ssl):
        """
        测试未授权 CONNECT 握手放行与阴性对照：
        采用 RFC 5737 规定的测试网段 (192.0.2.1:80)，不可路由且无任何真实服务。
        严格采用 try...finally 保证高并发扫描下套接字句柄 100% 释放，彻底规避 FD 泄漏。
        """
        neg_target = "192.0.2.1:80"
        connect_req = f"CONNECT {neg_target} HTTP/1.1\r\nHost: {neg_target}\r\n\r\n".encode()

        s = None
        sock = None
        try:
            s = socket.create_connection((host, port), timeout=5)
            if use_ssl:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                sock = ctx.wrap_socket(s)
            else:
                sock = s

            # 发送 CONNECT 请求
            sock.sendall(connect_req)
            sock.settimeout(5)

            hdr = b""
            while b"\r\n\r\n" not in hdr:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                hdr += chunk

            first_line = hdr.split(b"\r\n")[0].decode("latin1", errors="ignore")
            # 严格校验：必须为 200 状态，且绝不能是 401 Unauthorized / 407 Proxy Authentication Required / 403 Forbidden
            if not ("200" in first_line and not any(code in first_line for code in ("401", "407", "403", "404", "502"))):
                return False, first_line

            # 阴性对照校验：Konnectivity 对不存在目标应异步挂起/超时，隧道内不会有真实应答
            sock.sendall(b"GET / HTTP/1.0\r\n\r\n")
            sock.settimeout(1.5)
            body = b""
            try:
                body = sock.recv(1024)
            except Exception:
                pass

            # 如果收到 HTML 数据，说明是泛域名 Web 服务的误判
            if body and b"<html" in body.lower():
                return False, "收到伪造 HTML 响应"

            return True, first_line
        except Exception as e:
            return False, str(e)
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
            elif s:
                try:
                    s.close()
                except Exception:
                    pass

    def verify(self, target):
        host = self.target_info["host"]
        port = self.target_info["port"]
        use_ssl = (self.target_info["scheme"] == "https")

        is_konnectivity, cert_info = self._probe_cert_and_fingerprint(target)

        # 若未命中特征，且端口非常见 8090/8091，则跳过以避免盲目发送 CONNECT
        if not is_konnectivity and port not in (8090, 8091):
            return False

        passed, status_line = self._test_connect_bypass(host, port, use_ssl)
        if passed:
            self.logger.success(f"发现 Kubernetes Konnectivity 代理未授权访问 {target}")
            msg = (
                f"URL: {target} | 状态行: {status_line}\n"
                f"指纹特征: {cert_info or '命中 405 CONNECT Passthrough 特征'}\n"
                f"核心风险: 隧道代理无需客户端证书或凭据即可完成 CONNECT 建连，支持公网穿透进入集群内网"
            )
            return msg

        return False
