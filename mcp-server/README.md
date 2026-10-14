<div align="center">
  <p>
    <a href="./README_en.md"><b>English</b></a> |
    <b>简体中文</b>
  </p>
</div>

# ARL-Next MCP Server (v2.0 轻量客户端)

> **标准库实现 · 紧凑上下文 · 跨平台开箱即用**<br>
> 专为 **Antigravity、Claude Code、OpenAI Codex、DeepSeek Harness、ZCode、WorkBuddy** 等支持 MCP 协议的 AI Agent 适配优化的资产侦察情报协议。

---

## 🌟 核心特性与设计哲学

> [!NOTE]
> **TLS 证书校验策略**：ARL-Next 默认使用自签名证书，MCP 客户端为兼容开箱即用场景**不校验服务端证书**。若已部署受信任的正式证书，可在 `server.py` 中移除 `_request_api` 内关闭校验的两行以启用完整校验。

1. **⚡ 标准库轻量启动**：
   - 移除庞大的第三方框架依赖（无需额外安装 `mcp[cli]`、`pydantic`、`requests` 等）。
   - 仅依赖 Python 3.8+ 原生标准库（`sys`, `json`, `urllib`, `ssl`），直接使用系统 Python 即可启动，规避环境与虚拟环境配置冲突。
2. **🎯 综合资产画像（聚焦核心指标）**：
   - 摒弃大粒度倾倒冗余原始数据的交互方式。
   - 仅暴露单一核心工具 `get_asset_profile`，单次调用即可关联网络层（IP/端口/服务/Geo/ASN）、应用层（标题/状态码/Web指纹）、证书层（SANs/签发者）以及攻防层（历史漏洞/Nuclei命中标的/文件与敏感信息泄露）。
3. **📉 紧凑上下文设计**：
   - 系统级工具提示词精炼聚焦，大幅精简无用说明。
   - 数据返回格式采用**紧凑 JSON**，递归剪枝剔除所有 `null`、空数组与多余响应头；端口与漏洞采取结构化平铺展示，保障关键风险不被截断。

---

## 🛠️ 工具参考

### `get_asset_profile`
获取指定目标的综合资产情报。

#### 参数
- `target` (*string, 必填*)：资产标的，支持：
  - 子域名 / 主域名（如 `oa.example.com`）
  - IP 地址（如 `1.2.3.4`）
  - 站点完整 URL（如 `https://oa.example.com:8443`）
- `task_id` (*string, 可选*)：24 位 ARL 扫描任务 ID。若指定则锁定该任务上下文，未指定则智能匹配最新任务或全局资产库。

#### 返回样例（精炼紧凑 JSON）
```json
{
  "target": "admin.example.com",
  "resolved_ips": ["1.2.3.4"],
  "geo": "中国/浙江/杭州",
  "asn": "Hangzhou Alibaba Advertising Co.,Ltd.",
  "ports": [
    {"port": 80, "service": "http", "product": "nginx"},
    {"port": 443, "service": "https", "product": "nginx"},
    {"port": 8080, "service": "http", "product": "Spring-Boot"}
  ],
  "web": {
    "url": "https://admin.example.com",
    "status": 200,
    "title": "统一运营管理系统",
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

## 🚀 客户端接入配置指南

### 1. Claude Code
在命令行中直接注册（无需切换或创建虚拟环境）：
```bash
claude mcp add -s user arl-next \
  python3 "$(pwd)/mcp-server/server.py" \
  --env ARL_HOST="https://arl.example.com:5173" \
  --env ARL_TOKEN="<从 ARL_auth.md 中读取的 Token>"
```

### 2. Antigravity / Cursor / Windsurf (`mcp.json`)
在工作区或全局 `mcp.json` 中配置：
```json
{
  "mcpServers": {
    "arl-next": {
      "command": "python3",
      "args": ["/绝对路径/ARL-Next/mcp-server/server.py"],
      "env": {
        "ARL_HOST": "https://arl.example.com:5173",
        "ARL_TOKEN": "<从 ARL_auth.md 中读取的 Token>"
      }
    }
  }
}
```

### 3. OpenAI Codex / DeepSeek Harness / ZCode / WorkBuddy
直接在客户端对应的 MCP stdio 启动命令中填入：
- **Command**: `python3`
- **Args**: `["/绝对路径/ARL-Next/mcp-server/server.py"]`
- **Environment**:
  - `ARL_HOST`: `https://arl.example.com:5173`
  - `ARL_TOKEN`: `<从 ARL_auth.md 中读取的 Token>`
*(注：若未显式传环境变量，脚本会自动按顺序自动发现当前目录或项目根目录下的 `ARL_auth.md`)*
