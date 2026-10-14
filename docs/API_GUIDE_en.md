<div align="center">
  <p>
    <b>English</b> |
    <a href="./API_GUIDE.md"><b>简体中文</b></a>
  </p>
</div>

# ARL-Next REST API Calling Guide & Integration Conventions

> This guide outlines basic API specifications, authentication methods, legacy HTTP verb conventions, task state lifecycle rules, and data namespace architectures for automated scripts, CI/CD pipelines, and Security Orchestration, Automation, and Response (SOAR) workflows.<br>
> For full OpenAPI / Swagger schemas and interactive debugging, visit `https://<your-arl-host>:5173/api/doc` on your running deployment.

---

## 1. Core Conventions & Gateway Routing

- **Base Path**: All backend API endpoints are prefixed with `/api`.
- **Protocol & Gateway Port**: In production environments, all requests are routed through the frontend Nginx reverse proxy at `https://<your-arl-host>:5173/api/...`.
- **Payload Schema**: All endpoints return JSON objects. Top-level responses include business status code `code` and descriptive `message`:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": { ... }
  }
  ```
  > [!IMPORTANT]
  > Clients **must not rely solely on HTTP 200 status codes** to infer business success; always inspect `code === 200` (or appropriate success codes) in the response payload.

---

## 2. Authentication & Security Policy

- **Header Authentication (Recommended)**: Pass the token in the HTTP header when authentication is enabled:
  ```http
  Token: <your-token>
  ```
- **Query Parameter (Fallback)**: The backend also supports `?token=<your-token>`. However, query tokens are often recorded in Web server access logs, reverse proxies, and browser histories. **Headers are strongly recommended**.
- **Security Red Line**: Never commit real API tokens to public version control, GitHub issues, publicly shared debug logs, or terminal command histories.
- **Unauthenticated Environments**: If authentication is explicitly disabled in the system configuration for air-gapped or testing environments, token verification is bypassed. Always ensure platform authentication and gateway access controls are enforced on exposed networks.

---

## 3. Task Management & Lifecycle State Constraints

> [!WARNING]
> Due to backward compatibility, certain task endpoints retain specific HTTP method bindings and prerequisite lifecycle state checks. Strictly follow these conventions instead of guessing generic RESTful patterns.

### Core Task Operations Reference

| Operation | HTTP Method & Path | Parameters / Request Payload | Prerequisites & Constraints |
| :--- | :--- | :--- | :--- |
| **List Tasks** | `GET /api/task/` | Query params: `target`, `status`, `page`, `size`; optionally `include_statistics=1` | Returns paginated task records |
| **Scan Task Statistics** | `GET /api/task/statistics` | None | Returns aggregated count per state without loading records |
| **Enterprise Task Statistics** | `GET /api/icp/task/statistics` | None | Returns status statistics for enterprise OSINT / ICP tasks |
| **Stop Single Task** | `GET /api/task/stop/<task_id>` | URL path param: `task_id` (24-char hex) | ⚠️ **Note: Uses GET to perform state mutation** (terminates the task). Do not use `POST` or `DELETE` |
| **Batch Stop Tasks** | `POST /api/task/batch_stop/` | JSON: see OpenAPI schema | Stops multiple tasks simultaneously |
| **Delete Task** | `POST /api/task/delete/` | JSON: `{"task_id": ["<task_id>"], "del_task_data": false}` | ⚠️ **State Constraint**: Only tasks in terminal states (`done`, `stop`, `error`) can be deleted. Running tasks return error code `104` ("Task is running") |
| **Restart Task** | `POST /api/task/restart/` | JSON: `{"task_id": ["<task_id>"]}` | Only stopped/finished tasks can be restarted |

### Best Practices for Task Deletion

To delete currently running tasks programmatically, execute a two-stage sequence:
1. Call `GET /api/task/stop/<task_id>` to transition the task to `stop` state;
2. Confirm the task has reached a terminal state, then call `POST /api/task/delete/`. Deletion requests on active tasks are rejected by the server with `{"code": 104, "message": "任务运行中"}`.

### Aggregated Statistics Parameter (`include_statistics=1`)

- Supplying `include_statistics=1` to `GET /api/task/` or `GET /api/icp/task` appends an aggregated `statistics` object to the response payload:
  ```json
  {
    "total": 120,
    "running": 2,
    "waiting": 1,
    "done": 110,
    "error": 5,
    "stop": 2,
    "active": 3,
    "abnormal": 7
  }
  ```
  - `active`: Total active tasks (`running + waiting`).
  - `abnormal`: Total abnormally terminated tasks (`error + stop`).
  - `running`: Includes intermediate stages (port scan, service recognition, risk巡航, etc.).
  - **Scope**: Statistics represent the entire collection and do not change with page number or keyword filters.
- **Degradation Resilience**: If metric aggregation encounters an error, the core task list is still returned, annotated with `statistics_error: true` (and `statistics` omitted). Clients should retain previous valid statistics rather than zeroing them out.

---

## 4. Result Query Namespaces

ARL-Next separates reconnaissance outputs into **Task-Specific Outputs** and **Asset Group Archives**, using dedicated API namespaces:

| Asset Type | Single Task Query Namespace (via `task_id`) | Asset Group Query Namespace (via `scope_id`) |
| :--- | :--- | :--- |
| **Subdomain** | `/api/domain/` | `/api/asset_domain/` |
| **IP Address** | `/api/ip/` | `/api/asset_ip/` |
| **Web Site** | `/api/site/` | `/api/asset_site/` |
| **Other Dimensions** | `/api/wih/`, `/api/vuln/`, `/api/fileleak/`, etc. | `/api/asset_wih/`, `/api/asset_vuln/`, etc. |

> [!NOTE]
> - Task-level queries require a valid `task_id`;
> - Group-level queries require a valid `scope_id`;
> - These namespaces map to separate underlying MongoDB collections and indexing schemes. Consult `/api/doc` for exact query fields and filtering options.

---

## 5. Error Code Conventions & Client Branching

| Code | Meaning | Typical Scenario |
| :--- | :--- | :--- |
| `200` | Business success | All successful responses |
| `104` | Task is running | Returned when deleting/operating on a running task; stop the task first |
| `999` | Parameter validation error | Missing/invalid parameters or exceeded limits (e.g. empty asset group ID list or more than 500 in a single request, invalid asset group/group ID) |

> [!NOTE]
> - `999` is a generic parameter-validation code; read `message` and `data.error` for the specific cause.
> - Clients should always keep a `default` branch in `switch/if` handling to avoid silently ignoring unmapped codes.
> - Error codes are not yet fully unified between task and enterprise-task endpoints (for example, enterprise task deletion may return `400` when the task is active); always verify against `/api/doc` and actual responses.
