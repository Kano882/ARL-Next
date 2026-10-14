<div align="center">
  <p>
    <b>English</b> |
    <a href="./README.md"><b>简体中文</b></a>
  </p>
</div>

# ARL-Next MCP Server (v2.0 Lightweight Edition)

HTTPS validates the certificate chain by default. The certificate auto-issued on first startup is `CN=localhost` with no SAN extension, which cannot cover a LAN IP, so behavior depends on the deployment shape:

| Deployment | `ARL_HOST` | Configuration |
| :--- | :--- | :--- |
| Client on the same host as the server | `https://127.0.0.1:5173` | **None.** `certs/arl.crt` (or `ARL_LOCAL_CERT` in `ARL_auth.md`) is trusted automatically |
| Trusted domain certificate deployed | `https://arl.example.com` | **None.** Chain and hostname are fully verified |
| Remote self-signed deployment (accessed by IP) | `https://<server-ip>:5173` | Copy the server certificate to the client and set `ARL_CA_BUNDLE=/abs/path/arl.crt` |

In the remote self-signed case the certificate carries no SAN for that IP, so hostname matching has no solution. The chain is still verified (any certificate outside `ARL_CA_BUNDLE` is rejected, so the connection cannot be substituted); only hostname matching is skipped, with a notice on stderr. Set `ARL_STRICT_HOSTNAME=true` to require a hostname match, or issue a server certificate carrying an IP/domain SAN for full verification.

`ARL_TLS_VERIFY=false` explicitly disables all verification for temporary testing. It cannot authenticate the server and the connection may be intercepted by a man-in-the-middle (the client prints a one-time warning on stderr); use it only for temporary tests. When unset, chain verification is always enabled.

Legacy REST fallback reports authentication and query failures as tool errors. `not_found` is returned only after successful queries with no matching asset.

> **Low Token Footprint · Standard Library Implementation · Broad Client Compatibility**<br>
> An asset reconnaissance intelligence protocol tailored for AI agents including **Antigravity, Claude Code, OpenAI Codex, DeepSeek Harness, ZCode, WorkBuddy**, and others.

---

## 🌟 Core Features & Design Principles

> [!NOTE]
> **TLS Certificate Verification**: The MCP client verifies the certificate chain and hostname by default. For a loopback deployment (`ARL_HOST` pointing at `127.0.0.1`/`localhost`), an existing `certs/arl.crt` or an `ARL_LOCAL_CERT` path registered in `ARL_auth.md` is trusted automatically with no extra configuration. Remote deployments should set `ARL_CA_BUNDLE` to the trusted PEM. `ARL_STRICT_HOSTNAME=true` forces hostname matching, and `ARL_TLS_VERIFY=false` disables verification entirely (temporary testing only).

1. **⚡ Standard Library Implementation**:
   - Eliminates third-party package dependencies (no `mcp[cli]`, no `pydantic`, no `requests`).
   - Built exclusively on Python 3.8+ standard libraries (`sys`, `json`, `urllib`, `ssl`), enabling instant execution with system Python and avoiding virtual environment conflicts.
2. **🎯 Unified Asset Profiling**:
   - Replaces unstructured, bulky outputs with structured contextual telemetry.
   - Exposes a unified core tool `get_asset_profile`, consolidating network layer details (IPs, ports, services, GeoIP, ASN), application layer data (page title, status codes, Web fingerprints), TLS certificates (SANs, issuers), and exposure intelligence (historical vulnerabilities, Nuclei findings, credential/file leaks) in a single request.
3. **📉 Context-Efficient Design**:
   - Streamlines system tool prompt definitions to minimize context footprint.
   - Returns compact JSON payloads: strips `null` fields, empty arrays, and redundant headers to maintain essential risk indicators without truncation.

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
