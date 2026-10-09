<div align="center">
  <p>
    <b>English</b> |
    <a href="./README.md"><b>简体中文</b></a>
  </p>
</div>

# ARL-Next MCP Server (v2.0 Lightweight Edition)

> **Low Token Footprint · Standard Library Implementation · Broad Client Compatibility**<br>
> An asset reconnaissance intelligence protocol tailored for AI agents including **Antigravity, Claude Code, OpenAI Codex, DeepSeek Harness, ZCode, WorkBuddy**, and others.

---

## 🌟 Core Features & Design Principles

1. **⚡ Zero External Dependencies (< 20ms startup)**:
   - Eliminates third-party package dependencies (no `mcp[cli]`, no `pydantic`, no `requests`).
   - Built exclusively on Python 3.8+ standard libraries (`sys`, `json`, `urllib`, `ssl`), allowing instant execution with system Python without virtual environment setup issues.
2. **🎯 Unified Asset Profiling**:
   - Replaces unstructured, bulky CSV outputs with structured contextual telemetry.
   - Exposes a unified core tool `get_asset_profile`, consolidating network layer details (IPs, ports, services, GeoIP, ASN), application layer data (page title, status codes, Web fingerprints), TLS certificates (SANs, issuers), and exposure intelligence (historical vulnerabilities, Nuclei findings, credential/file leaks) in a single request.
3. **📉 Token Footprint Reduction (-85%+ Tokens)**:
   - Reduces system tool prompt definitions from ~2,500 tokens down to **~120 tokens**.
   - Trims payload overhead with a compact JSON schema: strips `null` fields and empty arrays, and flattens ports and vulnerabilities into a compact representation for cost efficiency.

---

## 🛠️ Tool Reference

### `get_asset_profile`
Retrieves comprehensive asset intelligence for a specified target.

#### Parameters
- `target` (*string, required*): Target identifier, supporting:
  - Subdomain / Root domain (e.g., `oa.example.com`)
  - IP address (e.g., `1.2.3.4`)
  - Full URL (e.g., `https://oa.example.com:8443`)
- `task_id` (*string, optional*): 24-character ARL task ID. When specified, scopes the lookup to this task context; otherwise, resolves against the latest task or global asset repository.

#### Sample Response (Compact JSON)
```json
{
  "target": "admin.example.com",
  "resolved_ips": ["1.2.3.4"],
  "geo": "China/Zhejiang/Hangzhou",
  "asn": "Hangzhou Alibaba Advertising Co.,Ltd.",
  "ports": [
    {"port": 80, "service": "http", "product": "nginx"},
    {"port": 443, "service": "https", "product": "nginx"},
    {"port": 8080, "service": "http", "product": "Spring-Boot"}
  ],
  "web": {
    "url": "https://admin.example.com",
    "status": 200,
    "title": "Unified Operations Platform",
    "fingerprints": ["Vue.js", "Spring-Boot", "Nginx", "Shiro"]
  },
  "cert": {
    "issuer": "Let's Encrypt Authority X3",
    "sans": "*.example.com, example.com"
  },
  "vulns": [
    {"name": "Spring4Shell RCE", "severity": "high", "plugin": "CVE-2022-22965"}
  ],
  "leaks": [
    {"url": "https://admin.example.com/.git/config", "status": 200}
  ]
}
```

---

## 🚀 Client Configuration Guide

### 1. Claude Code
Register via CLI command (no dedicated virtual environment required):
```bash
claude mcp add -s user arl-next \
  python3 "$(pwd)/mcp-server/server.py" \
  --env ARL_HOST="https://arl.example.com:5173" \
  --env ARL_TOKEN="<Token retrieved from ARL_auth.md>"
```

### 2. Antigravity / Cursor / Windsurf (`mcp.json`)
Add to workspace or global `mcp.json`:
```json
{
  "mcpServers": {
    "arl-next": {
      "command": "python3",
      "args": ["/absolute/path/to/ARL-Next/mcp-server/server.py"],
      "env": {
        "ARL_HOST": "https://arl.example.com:5173",
        "ARL_TOKEN": "<Token retrieved from ARL_auth.md>"
      }
    }
  }
}
```

### 3. OpenAI Codex / DeepSeek Harness / ZCode / WorkBuddy
Configure standard I/O (stdio) MCP execution:
- **Command**: `python3`
- **Args**: `["/absolute/path/to/ARL-Next/mcp-server/server.py"]`
- **Environment**:
  - `ARL_HOST`: `https://arl.example.com:5173`
  - `ARL_TOKEN`: `<Token retrieved from ARL_auth.md>`
*(Note: If environment variables are omitted, the script automatically attempts discovery from `ARL_auth.md` in the current or repository root directory.)*
