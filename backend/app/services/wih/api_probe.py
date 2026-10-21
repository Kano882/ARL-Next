"""对显式启用的同源 GET/HEAD 候选采集有限响应，不执行 JavaScript。"""

import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from urllib3.exceptions import TimeoutError as StreamTimeoutError


MAX_PROBES_PER_SITE = 20
MAX_REDIRECTS = 3
MAX_BODY_BYTES = 16 * 1024
SITE_BUDGET_SECONDS = 60
REQUEST_BUDGET_SECONDS = 10
REQUEST_TIMEOUT = (3, 3)
RESPONSE_HEADERS = ("Content-Type", "Content-Length", "Server", "Allow")
REDIRECT_CODES = {301, 302, 303, 307, 308}


class ApiProbeSession(requests.Session):
    def resolve_redirects(self, *args, **kwargs):
        # requests 即使 allow_redirects=False，也会为 Response.next 读取重定向正文。
        # 所有跳转由 ApiProbe 校验和处理，避免隐式读取绕过长度、时间及范围限制。
        return iter(())


def _url(value):
    if (not isinstance(value, str) or not value or len(value) > 8192
            or any(char.isspace() or ord(char) < 32 or char == "\\" for char in value)):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.port == 0):
            return None
        # 按 requests 实际发送的形式校验主机，防止编码后的 authority 改变同源判断。
        prepared = requests.Request("GET", urlunsplit(parsed._replace(fragment=""))).prepare().url
        checked = urlsplit(prepared)
        if checked.username is not None or checked.password is not None:
            return None
        return prepared
    except (ValueError, UnicodeError, requests.RequestException):
        return None


def _origin(url):
    parsed = urlsplit(url)
    return (parsed.scheme.lower(), parsed.hostname.lower(),
            parsed.port or (443 if parsed.scheme.lower() == "https" else 80))


def _error_kind(error):
    # 不保存异常原文，避免代理地址或认证信息进入结果及日志。
    # requests 将流式读取超时包装为 ConnectionError，保留其真实分类。
    wrapped = error.args[0] if error.args else None
    if isinstance(error, requests.Timeout) or isinstance(wrapped, StreamTimeoutError):
        return "timeout"
    if isinstance(error, requests.exceptions.SSLError):
        return "tls_error"
    if isinstance(error, requests.ConnectionError):
        return "connection_error"
    return "request_error"


def _text_content(content_type):
    media = content_type.split(";", 1)[0].strip().lower()
    return (media.startswith("text/") or media in {
        "application/json", "application/xml", "application/javascript",
        "application/x-javascript", "application/x-www-form-urlencoded",
    } or media.endswith(("+json", "+xml")))


class ApiProbe:
    """每站点一个独立会话；数量、时间及重定向配额不影响静态结果。"""

    def __init__(self, site, session_factory):
        self.site = _url(site)
        self.session_factory = session_factory
        self.session = None
        self.started = time.monotonic()
        self.count = 0
        self.cache = {}

    def close(self):
        if self.session is not None:
            self.session.close()

    def collect(self, candidate, is_excluded=lambda url: False):
        method = candidate.get("method")
        url = _url(candidate.get("url"))
        reason = None
        if method not in {"GET", "HEAD"}:
            reason = "unsupported_method"
        elif not url:
            reason = "unresolved_url"
        elif not self.site or _origin(url) != _origin(self.site):
            reason = "outside_origin"
        elif is_excluded(url):
            reason = "excluded"
        if reason:
            return {"state": "skipped", "reason": reason}

        key = (method, url)
        if key in self.cache:
            return self.cache[key]
        if self.count >= MAX_PROBES_PER_SITE:
            return {"state": "skipped", "reason": "site_quota"}
        if time.monotonic() - self.started >= SITE_BUDGET_SECONDS:
            return {"state": "skipped", "reason": "site_budget"}
        self.count += 1
        started = time.monotonic()
        deadline = min(self.started + SITE_BUDGET_SECONDS, started + REQUEST_BUDGET_SECONDS)
        result = {
            "state": "error", "method": method, "url": url, "redirects": [],
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        try:
            if self.session is None:
                self.session = self.session_factory()
            self._request(method, url, result, deadline, is_excluded)
        except Exception as error:
            result["error"] = _error_kind(error)
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        self.cache[key] = result
        return result

    def _request(self, method, url, result, deadline, is_excluded):
        visited = set()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                result["error"] = "time_budget"
                return
            visited.add(url)
            result["last_attempt_url"] = url
            # 不复用页面抓取的 Cookie，也不在接口之间传递 Set-Cookie。
            self.session.cookies.clear()
            with self.session.request(
                method, url, stream=True, allow_redirects=False,
                timeout=tuple(min(value, remaining) for value in REQUEST_TIMEOUT),
            ) as response:
                result.update({
                    "state": "responded", "url": url, "status_code": response.status_code,
                    "headers": {key.lower(): response.headers[key][:1024]
                                for key in RESPONSE_HEADERS if key in response.headers},
                })
                location = response.headers.get("Location")
                if response.status_code in REDIRECT_CODES and location:
                    try:
                        next_url = _url(urljoin(url, location))
                    except ValueError:
                        next_url = None
                    stop = None
                    if not next_url:
                        stop = "invalid_redirect"
                    elif _origin(next_url) != _origin(self.site):
                        stop = "outside_origin"
                    elif is_excluded(next_url):
                        stop = "excluded"
                    elif next_url in visited:
                        stop = "redirect_loop"
                    elif len(result["redirects"]) >= MAX_REDIRECTS:
                        stop = "redirect_limit"
                    if stop:
                        result["redirect_stop"] = stop
                    else:
                        result["redirects"].append({"url": url, "status_code": response.status_code})
                        url = next_url
                        continue
                self._body(response, method, result, deadline)
                return

    @staticmethod
    def _body(response, method, result, deadline):
        result.update({"body_preview": "", "body_bytes": 0, "body_truncated": False})
        content_type = response.headers.get("Content-Type", "")
        if method == "HEAD":
            result["body_skipped"] = "head"
            return
        if not _text_content(content_type):
            result["body_skipped"] = "non_text"
            return
        data = bytearray()
        try:
            # 小块读取使持续少量发送的响应也能频繁检查时间预算。
            for chunk in response.iter_content(chunk_size=1):
                if time.monotonic() >= deadline:
                    result.update({"body_truncated": True, "body_error": "time_budget"})
                    break
                if not chunk:
                    continue
                room = MAX_BODY_BYTES - len(data)
                data.extend(chunk[:room])
                if len(chunk) > room:
                    result["body_truncated"] = True
                    break
        except Exception as error:
            result.update({"body_truncated": True, "body_error": _error_kind(error)})
        charset = re.search(r'''charset\s*=\s*["']?([^;\s"']+)''', content_type, re.I)
        encoding = charset.group(1) if charset else "utf-8"
        try:
            preview = data.decode(encoding, errors="replace")
        except (LookupError, UnicodeError):
            preview = data.decode("utf-8", errors="replace")
        result.update({"body_preview": preview, "body_bytes": len(data)})
