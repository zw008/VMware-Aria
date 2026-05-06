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