# Changelog (English)

This document records all major version evolution, new features, performance optimizations, and bug fixes of the ARL-Next project.

> 中文版：[CHANGELOG.md](./CHANGELOG.md)

---

## [v1.4.2] - 2026-10-19

### 🚀 New Features
- **Enterprise panorama recon with backend-driven auto-grouping**: Tianyancha and MIIT ICP lookups merged into enterprise panorama recon (panorama dual-track / official filing). Registered company names auto-match Tianyancha GIDs and upgrade to dual-track pivoting; auto-grouping intents (`auto_group`, `auto_group_scan`, scan policy and interval) are consumed by the backend scheduler instead of browser polling, with in-flight tasks backfilled by incremental migration; stale `updating_icp_task_id` markers are promoted or cleaned up according to task terminal states.
- **Asset-group association for ordinary scan tasks**: the new recon task form offers an optional related asset group, with results synced to it on completion; fan-out is previewed honestly (one task per domain, merged task for IP/CIDR); the task list shows the linked group and sync state, with sync dispatched through a unified group selector.
- **Multi-select HTTP status filtering**: site assets support combined multi-status filtering (`status__in` / `status_code__in`); invalid input fails fast to narrow query scope; coexisting legacy single-value conditions intersect, independent of parameter order.
- **Searchable system settings with credential overview**: keyword search jumps to target tabs with highlighting; cross-tab credential states collapse into one summary line (folded by default); unsaved changes stay visible with jump links; the update page adds open-source repo and release links.
- **Aggregate status filters aligned with statistics**: task-list metric cards and filters share backend semantics (`active` = non-terminal, `abnormal` = `error + stop`), keeping card counts equal to filtered results; phase states render uniformly as "进行中 · \<phase\>".

### 🛠️ Performance & Refactoring
- **Settings IA regroup with concurrency governance**: settings converge into recon intel, dictionaries, scan & concurrency, notifications, and version & update; the GitHub monitor queue joins concurrency governance with peak-model recommendations; the three queue values are defined as Worker process counts, distinct from per-task blasting concurrency; omitted fields keep stored values on save to avoid silent overwrites; pool scaling retries against runtime process counts and reports observed convergence.
- **On-demand GeoIP with image decoupling**: `ip2region` / `GeoLite2` databases no longer ship in images; `tools/fetch_geoip.py` fetches and verifies them into the `arl_geoip` named volume at deploy time (GeoLite2 skipped with degraded service without `MAXMIND_LICENSE_KEY`); memory-swap observation tooling and per-queue OOM priorities added.
- **Config template / runtime config split**: effective runtime config separated from committed templates; environment markers and credentials in test scripts injected via environment variables; microservice sources and committed build artifacts excluded from build context; runtime screenshot dir untracked.
- **Nuclei engine capability caching**: redundant startup probes merged with cached engine capabilities, reducing repeated probe overhead.

### 🐛 Fixes & Hardening
- **Nuclei result attribution and failure visibility**: results keep target ports so findings from different services are not merged; scan process failures are reported with temp files cleaned up; recon abnormal paths converge on terminal-state and log observability.
- **Task sync chain hardening**: sync uses unified scope validation for domain and IP tasks, atomic claim before dispatch to avoid duplicate delivery, error state with cause preserved on dispatch failure; task-detail data namespaces corrected with global source fallback; malformed task IDs return not-found instead of degrading to system errors.
- **WIH builtin rules take effect**: missing builtin extraction rules backfilled so enabling them works; external asset text written as literal XLSX cells to block formula injection.
- **OSINT dispatch/cancel semantics**: dispatch params validated per task type with Tianyancha target field backfilled; cancellation no longer misreported as crashes; dispatch confirmation and cancellation semantics added before task deletion.
- **MCP self-signed deployment availability**: default certificate verification breaking clients on self-signed deployments mitigated — local certificates auto-trusted on loopback only with chain verification kept, remote deployments via `ARL_CA_BUNDLE`; both client copies kept in sync.
- **Frontend interaction convergence**: panorama recon advanced params always visible; dangerous-operation defaults, statistics semantics, and status terms unified; asset deletion target namespaces corrected.

### 🛡️ Security & Configuration
- **TLS verification for push channels**: Telegram, DingTalk, Feishu, and WeCom push enable TLS certificate verification, narrowing MITM exposure.
- **MongoDB fd limit raised**: `docker-compose.prod.yml` sets `nofile` to 65535 to avoid official warnings under concurrent queries over many collections; new `arl_geoip` named volume; existing persistent volume names unchanged.
- **Smooth DB evolution**: incremental migrations backfill missing concurrency fields (fill-missing-only), in-flight recon auto-group intents, and stale grouping-state healing; scope index gains `updating_icp_task_id`; every step isolated by single-step fault tolerance so one failure never blocks startup.
- **Doc wording convergence**: API conventions moved to `docs/API_GUIDE.md` (bilingual), README keeps global capabilities and quick entries; capability claims not matching implementation removed; asset-group terminology unified with community templates added; cert/credential ignore rules completed and verified.

---

> Earlier versions: see [CHANGELOG.md](./CHANGELOG.md) (Chinese).
