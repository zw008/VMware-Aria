## v1.5.31 (2026-06-08) — API layer rewritten against the official suite-api spec

An external user ran the MCP against a real Aria Operations instance and reported
that roughly half the API calls returned 404. They were right. Every claim was
verified against the official Broadcom/VMware suite-api specification (vROps 8.6
operation index + official sample payloads + VMware's own client code); 12 of
their 14 findings were confirmed, 2 were already spec-correct, and our own audit
found 6 more invented endpoints they hadn't hit yet. Sincere thanks to the reporter.

### Fixed — confirmed user findings (one line per reported bug)
1. `get_resource_metrics`: `statKey` now sent as an array of plain strings (was `[{key: ...}]` objects).
2. `get_resource_metrics`: response parsing now traverses `values[].stat-list.stat[]` (was reading non-existent top-level fields, so results were always empty).
3. `get_resource_metrics`: request field renamed `intervalQuantity` → `intervalQuantifier` per StatQuery model.
4. `get_top_consumers`: now uses real `GET /api/resources/stats/topn` (was POSTing to invented `/resources/query/topn`); resolves resource IDs by kind first since the endpoint has no resourceKind param.
5. `list_alerts`: filtering now goes through `POST /api/alerts/query` (AlertQuery: `activeOnly`, `alertCriticality`, `resource-query`) — `status`/`criticality` were never valid GET params and were silently ignored.
6. `acknowledge_alert`: now `POST /api/alerts?action=takeownership` with `{uuids:[...]}` — the spec has no acknowledge action; takeownership (control state ASSIGNED) is the semantic equivalent and is documented as such.
7. `cancel_alert`: now `POST /api/alerts?action=cancel` with `{uuids:[...]}` (was DELETE `/alerts/{id}`, which doesn't exist).
8. `set_alert_definition_state`: now PUT `/api/alertdefinitions/{id}/enable|disable` (was POST).
10. `generate_report`: correct flat creation body `{id, resourceId, reportDefinitionId, subject:[]}` (was invented `{"reportDefinition":{"id"}}` nesting); a root `resource_id` is now required with a teaching error when missing.
11. `list_reports`: `reportDefinitionId` is not a valid GET param — definition filtering is now client-side.
13. `get_aria_health`: reads the real NodeStatus `status` field, returns ONLINE/OFFLINE + healthy bool (was reporting `clusterVipAddress` — an IP address — as the status; the `services[]` array it also "parsed" doesn't exist).
14. Token handling: `validity` in the acquire response is an epoch-ms expiry timestamp with 6-hour sliding validity — the old code treated it as a duration, scheduling refresh ~56 years out, so sessions idle past 6h died with 401. README's "30 minutes" claim fixed too.

### Not changed — user findings that were already spec-correct
9. `create_alert_definition` keeps the `base-symptom-set` wire key — the Broadcom portal's model page names the property "symptoms", but the live server JSON uses `base-symptom-set` (verified against VMware's own build-tools client and official sample payloads). The invalid `relation: "ANY"` value WAS fixed (→ `SELF`, with `aggregation`/`symptomSetOperator` expressing any-of semantics).
12. `get_report` download URLs keep the `format` param — it is documented (PDF/CSV, default PDF); literals upper-cased to match the doc.

### Fixed — additional invented endpoints found during the audit (would also 404)
- `get_resource_health` / `get_resource_riskbadge`: `/resources/{id}/badge/health|risk` don't exist — badges now read from the `badges[]` array on `GET /resources/{id}`.
- `get_capacity_overview` / `get_remaining_capacity` / `get_time_remaining`: `/resources/{id}/recommendations|remainingcapacity|timeremaining` don't exist — reimplemented on the real `OnlineCapacityAnalytics|*` metrics via `GET /resources/{id}/stats/latest`.
- `list_rightsizing_recommendations`: `/recommendations/rightsizing` doesn't exist (`/api/recommendations` is alert-recommendation text CRUD) — reimplemented on `OnlineCapacityAnalytics|{cpu,mem}|demand|recommendedSize` metrics.
- `list_anomalies`: `/anomalies` and `/resources/{id}/anomalies` don't exist (the UI's anomalous-metrics view is not in the public API) — reimplemented on the `System Attributes|anomaly` metric (per-resource anomaly counts).

### Tests
- New `tests/eval/regression/test_aria_spec_conformance.py`: AST-scans every API call in the codebase and asserts it exists in the official vROps 8.6 operation index (315 operations, stored at `tests/eval/spec/vrops86_operations.json`). Invented endpoints now fail CI instead of 404-ing in production.
- New `tests/eval/regression/test_aria_specific.py`: 13 per-bug regression tests pinning correct request/response shapes with a mocked client.

### Known limitation
- Return shapes of the reimplemented capacity/anomaly/health tools changed (they previously parsed fields that never existed). Capacity analytics metrics need the product's analytics cycle to warm up; values are None until then.

## v1.5.30 (2026-06-07) — Tool description quality (Glama TDQS)

### Improved
- Rewrote MCP tool descriptions flagged by Glama's Tool Description Quality Score review:
  per-parameter semantics (format, defaults, valid values), return-field documentation,
  sibling-tool routing guidance, and behavioral transparency (side effects, audit logging,
  async semantics). Corrected descriptions that overstated or misstated actual behavior.
- No functional changes; descriptions only.

## v1.5.29 (2026-05-29) — Family Version Alignment

No Aria-specific changes since v1.5.28. Bumped for family-wide v1.5.29 alignment.

## v1.5.28 (2026-05-20)

**Fix `subclass() arg 1 must be a class` in goose/old mcp environments** —
v1.5.25–1.5.27 replaced `X | None` with `Optional[X]` but kept
`from __future__ import annotations` at the top of `mcp_server/server.py`.
Under mcp 1.10–1.13 (which Goose and some sandboxes pin), `Tool.from_function`
calls `issubclass(param.annotation, Context)` without resolving forward refs,
so string annotations crash the entire server load. Removed
`from __future__ import annotations` from `mcp_server/server.py` so annotations
are real classes; verified all tools load under mcp 1.10 and 1.14.

Traceback location: `mcp/server/fastmcp/tools/base.py:67`. CLAUDE.md 踩坑 #33
updated. family_smoke.sh Check 4b now installs `mcp==1.10.0` to catch this
regression class.

## v1.5.27 (2026-05-20)

**Loosen Python requirement: now supports Python >= 3.10** — v1.5.25/26 fixed
the PEP 604 root cause in MCP tool signatures (Optional[X] instead of X | None),
but kept `requires-python = ">=3.11"` and a 3.11 hard guard in `mcp_cmd`. Both
relaxed to 3.10 so users on Python 3.10 (e.g. Goose default sandbox, Ubuntu
22.04 system python) can install and run directly without a Python upgrade.

- `pyproject.toml`: `requires-python = ">=3.10"` (was `>=3.11`; VMware-VKS
  was `>=3.12`, now also `>=3.10` for family alignment).
- `<pkg>/cli.py` `mcp_cmd()`: version guard now triggers on `< (3, 10)`.
- Behavior on Python 3.10 matches 3.11/3.12 — the Optional[X] fix from v1.5.25
  is what actually enables this; this release just stops blocking installs.

---

## v1.5.26

**Family-wide MCP server fix — Python 3.10 compatibility (踩坑 #33)** — `vmware-aria mcp`
crashed at decorator time on Python 3.10 with `subclass() arg 1 must be a class`.
Root cause: `mcp_server/server.py` used PEP 604 `X | None` in tool signatures
plus `from __future__ import annotations`; on Python 3.10 + older mcp/pydantic
combos, `typing.get_type_hints()` evaluates `"str | None"` to a
`types.UnionType` instance, which FastMCP/Pydantic then feeds to `issubclass()`.
Reported by a goose user (qwen3.6:27, Python 3.10).

- `mcp_server/server.py`: all `X | None` → `Optional[X]`; ops layer untouched.
- `<pkg>/cli.py` `mcp_cmd()`: hard guard — exits with installation fix command
  if Python < 3.11 (defense in depth, our actual lower bound).
- `pyproject.toml`: `mcp[cli]>=1.10,<2.0` (was `>=1.0`) so uv doesn't pick
  an ancient version that has the same issubclass bug.

**Tooling — family smoke gains MCP schema-build check** — `scripts/family_smoke.sh`
new Check 4b runs `asyncio.run(mcp.list_tools())` per skill, forcing FastMCP to
build Pydantic models for every declared tool. Supports both module-level `mcp`
and `build_server()` factory patterns.

**Docs — CLAUDE.md gains 踩坑 #33 (PEP 604 / Python 3.10) and #34 (CLI/MCP exposure parity).**

---

## v1.5.24 (2026-05-19)

**Family version alignment** — no code changes in this skill. Bumped together
with VMware-AIops and VMware-VKS, which received a pyVmomi 8.x `ManagedObject`
setattr fix (踩坑 #32). `family_smoke.sh` now enforces the no-setattr rule
across all 9 skills.

## v1.5.23 (2026-05-19)

**VCF 9.0 / 9.1 ("VCF Operations") compatibility declared.**

- **docs:** README and `references/capabilities.md` now note that in VCF 9.0+, "VMware Aria Operations" has been rebranded to **VCF Operations**. The suite-api REST endpoints (`/suite-api/api/auth/token/acquire`, `/resources`, `/alerts`, etc.) are unchanged — this skill continues to work against VCF Operations 9.x without code changes.
- **docs:** Added `Official Broadcom References` pointer to [VCF Operations API docs](https://developer.broadcom.com/xapis) and the [VCF Python SDK](https://developer.broadcom.com/sdks).
- **chore:** `.trae/` and `skills-lock.json` added to `.gitignore` (local IDE/tool artifacts).
- **align:** Family v1.5.23 — all 9 skills tracking VCF 9.0 / 9.1 compatibility declaration.

## v1.5.22 (2026-05-08)

**Family alignment** — no source changes in this skill.

- **align:** Tracks v1.5.22 family bump driven by Smithery onboarding for vmware-avi / vmware-harden / vmware-pilot.

## v1.5.21 (2026-05-08)

**Family alignment** — no source changes in this skill.

- **deps:** Bumped `python-multipart` 0.0.26 → 0.0.27 (transitive, fixes GHSA HIGH DoS via unbounded multipart headers).
- **align:** Tracks v1.5.21 family bump driven by vmware-monitor folder_path feature (community PR #11).

## v1.5.20 (2026-05-08)

**Fix:** Added `<!-- mcp-name: io.github.zw008/vmware-aria -->` marker to README.md so MCP Registry ownership validation passes. Without this marker the registry refused publish (HTTP 400, "PyPI package ownership validation failed"), leaving this skill missing from the official registry from v1.3.0 through v1.5.19.

- **registry:** First-time publish of `vmware-aria` to registry.modelcontextprotocol.io.
- **align:** Family bumped 1.5.19 → 1.5.20 in lockstep.

## v1.5.19 (2026-05-06)

**Family alignment** — no source changes in this skill.

- **build:** Bumped `requires-python` from `>=3.10` to `>=3.11` (regression eval uses `tomllib`).
- **smoke:** Family `scripts/family_smoke.sh` adds Check 3b — recursive `--help` on every subcommand to surface broken lazy imports (yjs review 2026-05-06; 踩坑 #27).
- **align:** Tracks v1.5.19 fixes in vmware-nsx (CRITICAL CLI imports), vmware-vks (ApiClient leak), vmware-harden (Twin indexes + LEFT JOIN), vmware-policy (approval gate + singleton lock).

## v1.5.18 (2026-05-02)

**Family alignment + tooling normalization** — no source changes in this skill.

- **dev:** Added `[dependency-groups] dev` block (PEP 735) so `uv sync --group dev` works. Canonical set: `pytest>=8.0,<10.0`, `pytest-cov`, `ruff`.
- **test:** New `tests/eval/regression/test_release_blockers.py` (5 evals) catches the v1.5.x release blockers — missing `mcp_server` in wheel, AST-detected unimported runtime names, Typer app load failure, module import errors. Run via `pytest tests/eval/regression/`.
- **align:** Family version bump to v1.5.18.

## v1.5.17 (2026-05-01)

**Family alignment** — no source changes in this skill.

This release tracks vmware-pilot v1.5.17 (new `investigate_alert` template + `review_workflow` MCP tool + `parallel_group` step type) and vmware-policy v1.5.17 (L5 pattern matcher integrated into `@vmware_tool`). Both work with the existing skill MCP surface unchanged.

- **align:** Family version bump to v1.5.17.

## v1.5.16 (2026-04-30)

**Enterprise Harness Engineering alignment** — adapted from the Linkloud × addxai framework articles ([part 1](https://mp.weixin.qq.com/s/hz4W7ILHJ1yz_pG0Z1xP-A), [part 2](https://mp.weixin.qq.com/s/F3qYbyB3S8oIqx-Y4BrWNQ)).

- **docs:** New `references/investigation-protocol.md` — causal-chain root cause analysis protocol with 4 completeness criteria, shared with monitor/aiops. Aria is the primary L1/L2 metrics data source.
- **docs:** Added Broadcom/VMware brand disclaimer to `references/setup-guide.md` Security Notes (clears Snyk E005 brand-misuse flag on next clawhub Rescan).
- **docs:** "Automation Level Reference" section in `references/capabilities.md` — clarifies that aria is heavily L1/L2 (21 read / 6 write).
- **docs:** Common Workflows enriched with contention-vs-consumption judgment and investigation-protocol cross-reference.
- **align:** Family version bump to v1.5.16.

## v1.5.15 (2026-04-29)

**UX improvements from real user feedback**

- **feat:** New top-level CLI subcommand `vmware-aria mcp` starts the MCP server. Single command after `uv tool install vmware-aria` — no more `uvx --from`, no PyPI re-resolve, no TLS-proxy issues.
- **feat:** Default `verify_ssl: true` on new targets (already True in code). Aria Operations with default self-signed certs requires explicit `verify_ssl: false` in `config.yaml`.
- **docs:** README, SKILL.md, setup-guide.md, and `examples/mcp-configs/*.json` switched to `command: "vmware-aria"`, `args: ["mcp"]`. uvx form moved to fallback with TLS-proxy troubleshooting note.
- **compat:** Legacy `vmware-aria-mcp` console script kept — existing user configs continue to work.

## v1.5.14 (2026-04-21)

- Align with VMware skill family v1.5.14 (code review follow-up fixes by @yjs-2026)

## v1.5.13 (2026-04-21)

- Align with VMware skill family v1.5.13 (code review bug fixes)

## v1.5.12 (2026-04-17)

- Align with VMware skill family v1.5.12 (security & bug fixes from code review by @yjs-2026)

## v1.5.11 (2026-04-17)

- Align with VMware skill family v1.5.11 (AVI 22.x fixes from @timwangbc)

## v1.5.10 (2026-04-16)

- Security: bump python-multipart 0.0.22→0.0.26 (DoS via large multipart preamble/epilogue)
- Align with VMware skill family v1.5.10

## v1.5.8 (2026-04-15)

- Fix: MCP destructive tools `acknowledge_alert` and `cancel_alert` bypassed confirmation gates in MCP mode (CLI used interactive `double_confirm` which cannot run via stdio). Added `confirmed: bool = False` parameter with preview-by-default response; callers must pass `confirmed=True` to actually execute.
- Fix: SSL warning suppression scope — replaced `warnings.filterwarnings()` with class-targeted `urllib3.disable_warnings(InsecureRequestWarning)`.
- Align with VMware skill family v1.5.8

## v1.5.7 (2026-04-15)

- Align with VMware skill family v1.5.7 (Pilot `__from_step_N__` fix + VKS SSL/timeout fix)

## v1.5.6 (2026-04-15)

- Align with VMware skill family v1.5.6 (AVI bugfixes + packaging hotfix)

## v1.5.5 (2026-04-15)

- Align with VMware skill family v1.5.5

## v1.5.4 (2026-04-14)

- Security: bump pytest 9.0.2→9.0.3 (CVE-2025-71176, insecure tmpdir handling)

## v1.5.0 (2026-04-12)

### Anthropic Best Practices Integration

- **[READ]/[WRITE] tool prefixes**: All MCP tool descriptions now start with [READ] or [WRITE] to clearly indicate operation type
- **Read/write split counts**: SKILL.md MCP Tools section header shows exact read vs write tool counts
- **Negative routing**: Description frontmatter includes "Do NOT use when..." clause to prevent misrouting
- **Broadcom author attestation**: README.md, README-CN.md, and pyproject.toml include VMware by Broadcom author identity (wei-wz.zhou@broadcom.com) to resolve Snyk E005 brand warnings

### Aria-specific

- **Documentation fix**: capabilities.md corrected — create_alert_definition is supported (was incorrectly listed as "Not supported, UI required")

## v1.4.9 (2026-04-11)

- Fix: require explicit VMware/vSphere context in skill routing triggers (prevent false triggers on generic "clone", "deploy", "alarms" etc.)
- Fix: clarify vmware-policy compatibility field (Python transitive dep, not a required standalone binary)

## v1.4.8 (2026-04-09)

- Security: bump cryptography 46.0.6→46.0.7 (CVE-2026-39892, buffer overflow)
- Security: bump urllib3 2.3.0→2.6.3 (multiple CVEs) [VMware-VKS]
- Security: bump requests 2.32.5→2.33.0 (medium CVE) [VMware-VKS]

## v1.4.7 (2026-04-08)

- Fix: align openclaw metadata with actual runtime requirements
- Fix: standardize audit log path to ~/.vmware/audit.db across all docs
- Fix: update credential env var docs to correct VMWARE_<TARGET>_PASSWORD convention
- Fix: declare .env config and vmware-policy optional dependency in metadata

# Release Notes

## v1.4.5 — 2026-04-03

- **Security**: bump pygments 2.19.2 → 2.20.0 (fix ReDoS CVE in GUID matching regex)
- **Infrastructure**: add uv.lock for reproducible builds and Dependabot security tracking


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.4.0 — 2026-03-29

### Architecture: Unified Audit & Policy

- **vmware-policy integration**: All MCP tools now wrapped with `@vmware_tool` decorator
- **Unified audit logging**: Operations logged to `~/.vmware/audit.db` (SQLite WAL), replacing per-skill JSON Lines logs
- **Policy enforcement**: `check_allowed()` with rules.yaml, maintenance windows, risk-level gating
- **Sanitize consolidation**: Replaced local `_sanitize()` with shared `vmware_policy.sanitize()`
- **Risk classification**: Each tool tagged with risk_level (low/medium/high) for confirmation gating
- **Agent detection**: Audit logs identify calling agent (Claude/Codex/local)
- **New family members**: vmware-policy (audit/policy infrastructure) + vmware-pilot (workflow orchestration)


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.3.1 (2026-03-27)

### Documentation

- Updated README.md and README-CN.md companion skills table: expanded to full 6-skill family with tool counts and install commands, added vmware-nsx-security entry


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.3.0 (2026-03-27)

Initial release of `vmware-aria` — VMware Aria Operations AI monitoring skill.

### Features

**Resource Monitoring (5 tools)**
- `list_resources` — List VMs, hosts, clusters, datastores by resource kind with health badge
- `get_resource` — Full resource details including health, risk, and efficiency badge scores
- `get_resource_metrics` — Time-series metric stats with configurable window and rollup type
- `get_resource_health` — Health badge score (0–100) with color and description
- `get_top_consumers` — Rank VMs or hosts by CPU, memory, disk, or network usage

**Alert Management (5 tools)**
- `list_alerts` — Active or all alerts with criticality and resource scope filtering
- `get_alert` — Full alert details: symptom list, recommendations, timeline
- `acknowledge_alert` — Mark alert as acknowledged (write, audit-logged)
- `cancel_alert` — Dismiss an active alert (write, audit-logged)
- `list_alert_definitions` — Browse alert definition templates

**Capacity Planning (4 tools)**
- `get_capacity_overview` — Cluster capacity recommendations
- `get_remaining_capacity` — Remaining CPU, memory, disk headroom
- `get_time_remaining` — Days until capacity dimensions are exhausted
- `list_rightsizing_recommendations` — Over/under-provisioned VM recommendations

**Anomaly Detection (2 tools)**
- `list_anomalies` — ML-detected metric anomalies, per-resource or global
- `get_resource_riskbadge` — Risk score with contributing causes

**Platform Health (2 tools)**
- `get_aria_health` — All Aria internal service states
- `list_collector_groups` — Remote collector agent status

### Authentication
- OpsToken authentication: `POST /suite-api/api/auth/token/acquire`
- Auto-refresh: token refreshed 60s before 30-minute expiry
- Supports LOCAL, LDAP, and AD authentication sources

### Security
- Passwords loaded from env vars / `.env` file only
- All API text sanitized (control chars stripped, 500-char max)
- Write operations (acknowledge/cancel) audit-logged to `~/.vmware-aria/audit.log`

### CLI
- Full CLI with 5 command groups: `resource`, `alert`, `capacity`, `anomaly`, `health`
- `vmware-aria doctor` — pre-flight diagnostics for config, network, auth, MCP import
- Rich table output for list commands, JSON output for detail commands

### Compatibility
- Python 3.10+
- Aria Operations 8.x (vRealize Operations 8.x)
- Suite API v2 (`/suite-api/api/`)