"""从明确的 fetch / axios 调用中提取接口候选，不执行 JavaScript 或请求接口。"""

from html.parser import HTMLParser
import re
from typing import NamedTuple
from urllib.parse import urldefrag, urljoin, urlsplit


MAX_TOKENS = 100000
MAX_CALL_TOKENS = 512
MAX_LITERAL_CHARS = 8192
MAX_API_REQUESTS = 200
_TEMPLATE = chr(96)
_LEXEME = re.compile(
    r"(?P<space>\s+)|(?P<comment>//[^\r\n]*|/\*[\s\S]*?(?:\*/|$))"
    r"|(?P<name>[a-zA-Z_$][a-zA-Z0-9_$]*)|(?P<punct>\.\.\.|=>|\?\.|\+\+|--|[\s\S])"
)
_HTTP_METHODS = {"get", "head", "options", "post", "put", "patch", "delete"}
_REGEX_PREFIX_WORDS = {"return", "throw", "case", "yield", "await", "else", "do",
                       "typeof", "void", "delete", "in", "of", "instanceof"}
_CONTROL_PARENS = {"if", "while", "for", "with", "switch", "catch"}
_UNSET = object()


class _Token(NamedTuple):
    kind: str
    value: str
    line: int


def _regex_end(text, start):
    """线性跳过正则字面量，畸形字符类不会反复扫描剩余的脚本。"""
    pos, in_class = start + 1, False
    while pos < len(text):
        char = text[pos]
        if char in "\r\n":
            return pos
        if char == "\\":
            pos += 2
            continue
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif char == "/" and not in_class:
            pos += 1
            while pos < len(text) and text[pos].isalpha():
                pos += 1
            return pos
        pos += 1
    return len(text)


def _string_end(text, start, depth=0):
    if depth > 32:
        return len(text)
    quote = text[start]
    pos = start + 1
    while pos < len(text):
        char = text[pos]
        if char == "\\":
            pos += 2
        elif char == quote:
            return pos + 1
        elif quote == _TEMPLATE and text.startswith("${", pos):
            pos = _interpolation_end(text, pos + 2, depth + 1)
        else:
            pos += 1
    return len(text)


def _interpolation_end(text, pos, depth):
    braces = 1
    while pos < len(text):
        char = text[pos]
        if char in ("'", '"', _TEMPLATE):
            pos = _string_end(text, pos, depth)
            continue
        if text.startswith("//", pos) or text.startswith("/*", pos):
            pos = _LEXEME.match(text, pos).end()
            continue
        if char == "/":
            previous = pos - 1
            while previous >= 0 and text[previous].isspace():
                previous -= 1
            after_value = previous >= 0 and (text[previous].isalnum() or text[previous] in "_$)]'\"" + _TEMPLATE)
            if not after_value:
                pos = _regex_end(text, pos)
                continue
        if char == "{":
            braces += 1
        elif char == "}":
            braces -= 1
            if braces == 0:
                return pos + 1
        pos += 1
    return pos


def _literal(raw):
    """只还原静态字符串；插值、旧式八进制及不完整转义不作推断。"""
    if len(raw) < 2 or raw[-1] != raw[0]:
        return None
    if raw[0] == _TEMPLATE and "${" in raw:
        return None
    text = raw[1:-1]
    escapes = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f",
               "v": "\v", "\\": "\\", "/": "/", "'": "'", '"': '"', _TEMPLATE: _TEMPLATE}
    out = []
    pos = 0
    while pos < len(text):
        char = text[pos]
        pos += 1
        if char != "\\":
            out.append(char)
            continue
        if pos == len(text):
            return None
        char = text[pos]
        pos += 1
        if char in escapes:
            out.append(escapes[char])
        elif char in "\r\n":
            if char == "\r" and text[pos:pos + 1] == "\n":
                pos += 1
        elif char in ("u", "x"):
            size = 4 if char == "u" else 2
            encoded = text[pos:pos + size]
            if len(encoded) != size or not re.fullmatch(r"[0-9a-fA-F]+", encoded):
                return None
            value = int(encoded, 16)
            if 0xD800 <= value <= 0xDFFF:
                return None
            out.append(chr(value))
            pos += size
        else:
            return None
    return "".join(out)


def _tokens(text):
    tokens = []
    pos, line = 0, 1
    regex_allowed, parens = True, []
    while pos < len(text) and len(tokens) < MAX_TOKENS:
        start = pos
        char = text[pos]
        if char in ("'", '"', _TEMPLATE):
            pos = _string_end(text, pos)
            value = _literal(text[start:pos]) if pos - start <= MAX_LITERAL_CHARS else None
            tokens.append(_Token("string" if value is not None else "opaque", value or "", line))
        else:
            match = _LEXEME.match(text, pos)
            pos = match.end()
            if match.lastgroup in ("space", "comment"):
                line += text[start:pos].count("\n")
                continue
            if char == "/" and regex_allowed:
                pos = _regex_end(text, start)
                tokens.append(_Token("opaque", "", line))
            else:
                tokens.append(_Token(match.lastgroup, match.group(), line))
        token = tokens[-1]
        if token.kind == "punct" and token.value == "(":
            parens.append(len(tokens) > 1 and tokens[-2].kind == "name"
                          and tokens[-2].value in _CONTROL_PARENS
                          and (len(tokens) < 3 or tokens[-3].value not in (".", "?.")))
            regex_allowed = True
        elif token.kind == "punct" and token.value == ")":
            regex_allowed = parens.pop() if parens else True
        elif token.kind == "punct":
            regex_allowed = token.value not in ("]", ".", "++", "--") and not token.value.isdigit()
        else:
            regex_allowed = token.kind == "name" and token.value in _REGEX_PREFIX_WORDS
        line += text[start:pos].count("\n")
    return tokens


def _pairs(tokens):
    stack, pairs = [], {}
    closing = {")": "(", "]": "[", "}": "{"}
    for pos, token in enumerate(tokens):
        if token.kind != "punct":
            continue
        if token.value in ("(", "[", "{"):
            stack.append((token.value, pos))
        elif token.value in closing:
            if not stack or stack[-1][0] != closing[token.value]:
                stack.clear()
            else:
                _, start = stack.pop()
                pairs[start] = pos
    return pairs


def _parts(tokens, pairs, start, end):
    parts, first, pos = [], start, start
    while pos < end:
        if pos in pairs:
            pos = pairs[pos] + 1
        elif tokens[pos].value == "," and tokens[pos].kind == "punct":
            parts.append(tokens[first:pos])
            first = pos = pos + 1
        else:
            pos += 1
    if first < end:
        parts.append(tokens[first:end])
    return parts


def _value(tokens):
    return tokens[0].value if len(tokens) == 1 and tokens[0].kind == "string" else None


def _config(tokens):
    if not tokens or tokens[0].value != "{" or tokens[-1].value != "}":
        return None
    pairs = _pairs(tokens)
    if pairs.get(0) != len(tokens) - 1:
        return None
    fields = {}
    for part in _parts(tokens, pairs, 1, len(tokens) - 1):
        if len(part) < 3 or part[0].kind not in ("name", "string") or part[1].value != ":":
            return None
        key = part[0].value
        if key in fields:
            return None
        fields[key] = _value(part[2:])
    return fields


def _http_url(value):
    if not value or re.search(r"[\s\\\x00-\x1f\x7f]", value):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            return None
        _ = parsed.port
        if parsed.username is not None or parsed.password is not None:
            return None
        return urldefrag(value)[0]
    except ValueError:
        return None


def _resolve(path, document_base, client, base=_UNSET):
    if _http_url(path):
        return _http_url(path)
    if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", path):
        return None
    if client == "fetch" or path.startswith("//"):
        return _http_url(urljoin(document_base, path)) if document_base else None
    # axios 的 baseURL 使用拼接语义，不能用 urljoin 丢弃 /v1 等路径前缀。
    if base is _UNSET or base is None:
        return None
    combined = re.sub(r"/?/$", "", base) + "/" + path.lstrip("/") if base else path
    return _http_url(combined) or (_http_url(urljoin(document_base, combined)) if document_base else None)


class _BaseParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.href = _UNSET

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "base" and self.href is _UNSET:
            for key, value in attrs:
                if key == "href":
                    self.href = value or ""
                    break


def document_base_url(html, response_url):
    """使用实际页面响应地址及首个 base href，绝不使用 CDN 脚本目录补全接口。"""
    parser = _BaseParser()
    try:
        parser.feed(html)
        value = response_url if parser.href is _UNSET else urljoin(response_url, parser.href)
        return _http_url(value)
    except (ValueError, AssertionError, TypeError):
        return None


def extract_api_requests(source, document_base=None, limit=MAX_API_REQUESTS):
    """支持直接 fetch、window.fetch、axios(config)、axios.request 和 axios.HTTP方法。"""
    if limit <= 0 or ("fetch" not in source and "axios" not in source):
        return []
    tokens = _tokens(source)
    pairs = _pairs(tokens)
    results, seen = [], set()
    for pos, token in enumerate(tokens):
        if token.kind != "name":
            continue
        client, verb, opening = None, None, pos + 1
        if token.value == "fetch":
            if pos and tokens[pos - 1].value in (".", "?."):
                if (tokens[pos - 1].value != "." or pos < 2
                        or tokens[pos - 2].value not in ("window", "globalThis")
                        or tokens[pos - 2].kind != "name"
                        or (pos >= 3 and tokens[pos - 3].value in (".", "?."))):
                    continue
            client = "fetch"
        elif token.value == "axios" and (not pos or tokens[pos - 1].value not in (".", "?.")):
            client = "axios"
            if pos + 3 < len(tokens) and tokens[pos + 1].value == ".":
                verb = tokens[pos + 2].value
                if verb not in _HTTP_METHODS | {"request"}:
                    continue
                opening = pos + 3
        else:
            continue
        if opening not in pairs or tokens[opening].value != "(":
            continue
        end = pairs[opening]
        if end - opening > MAX_CALL_TOKENS:
            continue
        args = _parts(tokens, pairs, opening + 1, end)
        if not args:
            continue
        base = _UNSET
        if client == "axios" and verb in (None, "request"):
            if _value(args[0]) is not None:
                path = _value(args[0])
                config = _config(args[1]) if len(args) > 1 else {}
            else:
                config = _config(args[0])
                path = config.get("url") if config is not None else None
            method = config.get("method", "GET") if config is not None else None
        else:
            path = _value(args[0])
            config_index = 2 if verb in {"post", "put", "patch"} else 1
            config = _config(args[config_index]) if len(args) > config_index else {}
            method = "GET" if client == "fetch" else verb
            if client == "fetch":
                method = config.get("method", "GET") if config is not None else None
        if not path or re.search(r"[\s\\\x00-\x1f\x7f]", path):
            continue
        if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", path) and not _http_url(path):
            continue
        if config is not None and "baseURL" in config:
            base = config["baseURL"]
        method = method.upper() if method and re.fullmatch(r"[a-zA-Z]+", method) else "UNKNOWN"
        # 此选项会改变绝对 URL 的组合方式，本阶段不推断。
        uncertain_axios = client == "axios" and (config is None or "allowAbsoluteUrls" in config)
        resolved = None if uncertain_axios else _resolve(path, document_base, client, base)
        identity = (method, path, resolved)
        if identity in seen:
            continue
        seen.add(identity)
        results.append({"method": method, "path": path, "url": resolved, "client": client,
                        "line": token.line, "verified": False})
        if len(results) >= min(limit, MAX_API_REQUESTS):
            break
    return results
