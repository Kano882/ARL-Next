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

### Associate New Scan Tasks with Asset Groups

When creating a reconnaissance task, optionally select an existing asset group. The selector supports name search and pagination. Completed tasks use the existing asset synchronization pipeline; this does not create periodic monitoring or extend the group's configured scope.

`POST /api/task/` accepts an optional JSON field `related_scope_id`, for example:

```json
{"name": "Boundary discovery", "target": "www.example.com", "related_scope_id": "<asset_scope_id>"}
```

Before creating any tasks in a batch, the backend checks group existence and verifies that all domain, IP, or CIDR targets belong to its scope. Existing target validation and blacklist checks remain active. Omitting the field preserves ordinary scan behavior. Restarting an associated task retains the group ID, revalidates the current scope, and clears the new task's previous sync outcome.

The task list distinguishes synchronization after completion, queued synchronization, active synchronization, success, and failure. Failure reasons appear in a tooltip. Scan results and synchronization status are retained independently; selecting a group does not indicate successful synchronization. The group and target scope are checked again before synchronization.

`POST /api/task/sync/` supports finished domain and IP tasks with `task_id` and `scope_id`. Full scope validation still applies. The request records a queued state before dispatch and records dispatch errors. Both automatic and manual synchronization record `synced_scope_id` / `synced_scope_name` on success or `sync_error` on failure, without automatic retries.

Task creation supports scoping by asset group; Nuclei YAML/ZIP import is provided by the PoC management page and is not duplicated here.

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

### Global Dimension Counts

`GET /api/asset_overview/count` returns the **global totals** for every asset dimension listed above in a single response. It is intended for rendering per-tab count badges without issuing one count request per dimension.

Example response:

```json
{
  "code": 200,
  "message": "success",
  "counts": {
    "site": 12800, "domain": 45600, "ip": 9800, "cert": 3200,
    "service": 15400, "fileleak": 210, "url": 76200, "vuln": 540,
    "npoc_service": 1300, "cip": 860, "stat_finger": 320,
    "nuclei_result": 97, "wih": 44
  }
}
```

> [!IMPORTANT]
> - The counts are **global aggregates** and are **not** the same scope as the `task_id` / `scope_id` filtered list endpoints. Do not use them to infer the asset volume of a single task or asset group;
> - Each dimension's counting rule matches its corresponding list endpoint — for example `cip` counts distinct C-blocks and `stat_finger` counts distinct fingerprint names, rather than raw document counts;
> - A dimension whose count fails is returned as `null`. Clients should treat it as "unknown" and avoid rendering it as `0`.

### Multiple HTTP Status Code Filtering for Asset Lists

The site, URL, and file leak lists in Global Asset Search, Task Details, and Asset Group Details support multiple status selection, taking effect immediately upon selection or clearance. Status codes within the same field are matched with OR; other filters and `task_id` / `scope_id` are combined with AND. List queries, export endpoints, and site result sets share the same filter conversion:

- **Site Endpoints** (`/api/site/`, `/api/asset_site/`): Use `status__in=200,301,403`.
- **URL & File Leak Endpoints** (`/api/url/`, `/api/asset_url/`, `/api/fileleak/`, `/api/asset_fileleak/`): Use `status_code__in=200,403`.
- **Parameter Format & Validation**: Send a single comma-separated parameter containing integer codes from 100 to 599, with at most 500 entries. Empty strings, invalid values, and repeated parameters return HTTP 400. Omit the parameter to clear the filter.
- **Backward Compatibility**: Existing scalar parameters (`status=200`, `status_code=200`) remain supported; if both scalar and multiselect parameters are provided, their intersection is applied. Task execution status filters retain their existing format.

> [!NOTE]
> - Example: `GET /api/site/?task_id=<task_id>&status__in=200,403` selects sites from that task with status 200 or 403. The same parameters apply to `/api/site/export/` and `/api/site/save_result_set/`. For asset group queries, replace the parameter with `scope_id` and query `/api/asset_site/`.
> - Current support is restricted to status code field enumeration and field-level AND combinations; arbitrary boolean expressions or cross-field OR logic are not supported.

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

### WIH API request and response details

WIH lists in task details, global asset search and asset-group details provide an API details action for `record_type=api_endpoint`. All three views share one drawer, using the `api_request` and `api_request.probe` metadata already returned by the list. Opening it does not request the endpoint, capture a screenshot or rerun a probe.

- Request details preserve the original path, resolved URL, method, site, script source, client and line within the script.
- Not collected, HTTP response received, request failed and skipped are separate states. Statuses including 401, 403, 404 and 5xx remain HTTP observations and do not establish endpoint validity, unauthenticated access or a vulnerability.
- The last HTTP response URL and last attempted URL are shown separately, alongside redirect history, stop reasons, errors, collection time and duration. A failed later hop does not verify its destination.
- Headers and body previews are displayed as plain text and can be copied without executing HTML or scripts. Incomplete reads, truncation, empty bodies, HEAD and skipped body types have separate notices. Copying a preview does not fetch the full body.
- Legacy records retain their content and source without inferring methods or reachability. Changing task, asset group or tab, or leaving the view, closes the drawer to avoid mixing record contexts. Labels follow Chinese, English or Russian preferences; raw responses and sources remain unchanged.

Existing list queries, filters, counts, exports, deletion permissions and scans are unchanged. No historical migration is required.
