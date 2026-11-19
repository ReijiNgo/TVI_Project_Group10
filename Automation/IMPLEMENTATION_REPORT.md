# Member 3 implementation report - Step 7 and Step 9

## Step 9 automatic rollback update — 2026-11-19

This section supersedes the older Step 9 failure-handling record below. Step 7
and protected Step 1–8 sources remain unchanged. The pre-implementation
[workspace audit](ROLLBACK_AUDIT.md) records the actual starting code, ownership
and 112 passing tests. Existing user edits to `.gitignore` and root `README.md`
were retained without modification by this task. No live SSH operation was run.

Automatic scoped compensation is now part of the real apply transaction,
including CLI errors, partial writes, post-check/evidence failures and first
Ctrl-C after mutation. Complete pre JSON and readable CFG are atomically saved
and read back before writes. Recovery collects actual current state, reverses
only submitted owned objects and verifies full/owned/protected/interface/VLAN
state against the pre-snapshot. Restored snapshot and a sanitized report are
saved. A verified rollback remains a failed apply; the batch stops.

Changed/created files for this update:

| File | Purpose |
|---|---|
| automation_core.py | Transaction recovery, strict reconnect, backup readback, Result statuses, snapshots/reports |
| rollback.py | Conservative canonical comparisons, safe original-state inverse generation, content-free diff |
| auto_provision.py | Single-enabled-device double-confirmed live demo and progress |
| tests/helpers.py | Stateful fake inverse commands, per-command fault injection, membership/default-name state |
| tests/test_rollback.py | Additional state-based recovery, safety, evidence and CLI tests |
| verify_local.py | Recovery API/import/CLI checks and tracked CFG guard |
| ROLLBACK_AUDIT.md | Required audit before coding |
| DEMO_ROLLBACK_EVE.md | Exact PowerShell/console demo, proof inspection and manual recovery |
| README_STEP9.md | Current transaction, status and compatibility contracts |
| IMPLEMENTATION_REPORT.md | This update and validation record |

Recovered originals include nonstandard VLAN names, implicit default VLAN names
(`no name`), absent VLANs, absent approved NTP and original single-line MOTD.
Unrelated NTP/options, banner when disabled, VLANs and every protected config
command remain outside the inverse grammar. New VLAN deletion requires no ports,
no extra attributes and unchanged interfaces. VLAN writes require explicit local
VTP mode (transparent/off); the script never changes VTP. Foreign object edits
become conflicts. Transport recovery reconnects with the existing strict host
keys and identity checks, then recomputes remaining inverses from actual state.
CLI rejection is never blindly retried. No device-wide restore is implemented.

The demo applies one approved object, verifies its real readback, saves a
demo_changed snapshot and injects an application exception. It requires a fresh
audit review, one explicit mandatory device, normal confirmation and separate
demo confirmation. No-op/echo-only state cannot fabricate the demonstration.

Verification normalizes known IOS show metadata/separators/CRLF/trailing spaces
outside banners and banner serialization. It preserves order, command context,
banner text and every other command. VLAN memberships and all interface brief
fields are compared. Unknown output is unverified; mismatches/conflicts or missing
durable recovery evidence cannot produce a verified result. Raw checksum equality
is not used as recovery proof. Reports include command submissions with banner
text redacted, not sensitive inverse commands or config diffs.

Validation uses Python 3.14.4, Netmiko 4.8.0, PyYAML 6.0.3 in project `.venv`.
The exact requested `python -B ...` commands were invoked after activating that
environment; no global package installation or policy changes were needed.
Final rollback validation record (2026-11-19):

| Check | Actual outcome |
|---|---|
| unittest discovery / final offline runner | 160 passed, 0 failures/errors, 0 skipped |
| Existing regression tests | All original 112 pass; no existing test assertions changed |
| New rollback/comparison tests | 48 pass, with actual fake-device state comparisons |
| security_validation.py | STATIC PASS, 9 base + 21 conditional fragments |
| verify_local.py | 13/13 PASS; network_connections = 0 |
| auto_provision.py --mode plan | PASS, deterministic offline plan for 3 enabled switches |
| Member2 tests/static_audit.py | STATIC PASS |
| Protected-source manifest | All 65 files retain their SHA256 values |
| Demo runbook PowerShell blocks | All 6 parse with the actual PowerShell parser; none executed live |
| git diff --check | PASS |
| Live IOS parser / EVE-NG SSH, apply and rollback | NOT RUN |

Ignored local QA evidence was regenerated at
`Automation/reports/offline-test-results.json` and `offline-tests.txt`.
The runner reports `runtime: NOT RUN; all SSH sessions in tests are fake`.
The final suite includes banner-embedded fake-command recognition, VTP drift,
broken progress output, evidence write failures and original implicit VLAN names.
One documentation test initially mistook PowerShell `[bool](...)` for Markdown;
the runbook now uses a direct boolean expression. A new VTP test initially also
triggered an independent safe NTP inverse; its fixture now isolates VLAN writes.
Neither issue required weakening any existing assertions or changing Git metadata,
line endings, dependency versions or protected sources.

Limits: no exact IOS image/replace support is evidenced by the workspace. Actual
IOS parser support requires live preflight. Multiline/control/ambiguous original
MOTD changes reject before mutation. Unsupported table/config formats, lost
management reachability, concurrent changes, repeated interruption, process kill
and controller power loss may leave recovery unverified. Administrative exclusion
of concurrent writers and console fallback are required. Config comparisons do
not certify dataplane traffic, NTP sync, VTP revision or startup persistence.
Runtime artifacts remain ignored, private, unencrypted and never overwritten.

**Verdict: implemented and offline-tested; prepared for EVE-NG live verification,
subject to image/parser and lab prerequisites. Live recovery NOT VERIFIED.**

The following sections retain the original 2026-11-18 implementation history;
their Step 9 test counts/failure handling are superseded by this update.

Publication was additionally checked against GitHub main `0d003e3` in an isolated
temporary checkout. Its integrated configurations and updated protected manifest
were retained. Windows autocrlf initially changed the bytes of 11 protected files;
their committed Git blob bytes matched the manifest, so those exact bytes were
restored only in the temporary checkout. No assertions or expected hashes were
weakened. All 160 tests then passed, along with security/local/plan/Member2 checks.
`Automation/.gitignore` now independently excludes private runtime directories
when publishing only this folder. No runtime artifacts are part of the upload.

## Scope and observed status

Implementation branch: feature/security-automation. Starting HEAD: d5590a7.
The previous audit was rechecked before writing source: Automation and final startup
slots were still empty. Only M3-owned source, root README pointers and additive
ignore rules changed. No checkout/reset/clean/merge/commit/push or live router action
was performed. All Configurations/ placeholders, M1/M2, Specs/topology and Report
remain byte-identical across 65 protected files (SHA256 regression manifest).

No function is classified IMPLEMENTED + RUNTIME VERIFIED. No live SSH/audit/apply,
RSA generation, credential change or IPsec key modification was performed. Mocked
CLI audit/apply tests are not EVE-NG operation. All 12 manual runtime cases are NOT RUN.

## Features and status

| Feature | Status | Evidence/limit |
|---|---|---|
| Contract-derived inventory, strict YAML, defaults/optional selection, site VLAN rendering | IMPLEMENTED + OFFLINE TESTED | Inventory/rendering tests; no unrelated VLAN/port changes |
| Offline default plan and deterministic JSON | IMPLEMENTED + OFFLINE TESTED | Zero-connection fake guard, CLI/CWD smoke |
| Netmiko SSH, strict known_hosts, environment/getpass, enable, transient retry, finally disconnect | IMPLEMENTED + OFFLINE TESTED | Fake failure/success workflows; installed Netmiko API signature/import checks; real SSH unverified |
| Read-only audit and state-bound reviewed apply | IMPLEMENTED + OFFLINE TESTED | Fake CLI roundtrip, hostname/management guards, stale/tampered review denial |
| Complete atomic pre/post snapshots, no overwrite/traversal, structured logs | IMPLEMENTED + OFFLINE TESTED | Disk/empty/truncated/collision tests; raw configs never logged or tracked |
| Idempotency and protected state verification | IMPLEMENTED + OFFLINE TESTED | No-op rerun, IOS banner serialization, unrelated VLAN/route guard |
| Partial-failure handling | IMPLEMENTED + OFFLINE TESTED | Unknown applied count, best-effort forensic capture with explicit secondary failure, fail-fast apply batch |
| MOTD support | IMPLEMENTED + OFFLINE TESTED | Explicit approval flag/text required, disabled by default |
| Optional AAA/Syslog deployment | BLOCKED BY EXTERNAL DEPENDENCY | Missing approved method list/endpoint/transport; enabling is rejected rather than inventing settings |
| NAT/PAT three routers | IMPLEMENTED + OFFLINE TESTED | Local source matching, ordered no-NAT destinations, roles checked; real NAT/GRE/IPsec order not proven |
| Guest IPv4/IPv6 ingress ACL | IMPLEMENTED + OFFLINE TESTED | DHCP bootstrap/renew, bounded IPv6 ND/DAD/RS and negative isolation packet-model tests |
| Corporate Finance/Engineering/IoT/network Management ACL | BLOCKED BY EXTERNAL DEPENDENCY | Policy matrix and non-executable proposals only; no invented blanket deny attached |
| DHCP Snooping and wired Port Security | IMPLEMENTED + OFFLINE TESTED | Source-derived trust/port checks; Option82 insertion off; AP/server/controller protected from restrictive PortSec |
| DAI VLAN20 activation candidates | IMPLEMENTED BUT UNVERIFIED | Conditional files only; require actual binding/static-host and reboot recovery proof |
| DAI VLAN10/50/30/99 activation | BLOCKED BY EXTERNAL DEPENDENCY | Missing static endpoint data/approval; no fake MAC or premature inspection |
| Nine enterprise safe hardening fragments | IMPLEMENTED + OFFLINE TESTED | No account/key/AAA/VTY mutation in base fragments; real IOS parser unverified |
| VTY restrictions and RSA/bootstrap/recovery | IMPLEMENTED BUT UNVERIFIED | Console runbook + mutually exclusive line-range candidates; no device key/account replaced |
| Static NAT/port forwarding/NAT66 | NOT IMPLEMENTED | No approved requirement; intentionally absent |

## Tests actually executed

Final recorded unittest execution: 2026-11-18T13:37:10.507281+00:00.
Interpreter: Python3.14.4 on Windows; Netmiko4.8.0, Paramiko5.1.0, PyYAML6.0.3
installed in project .venv. pip check: no broken requirements.
Initial sandbox package download failed with socket WinError10013; the approved
network retry installed requirements locally, without changing global Python.

| Suite | Total | Passed | Failed | Skipped |
|---|---:|---:|---:|---:|
| test_backup | 12 | 12 | 0 | 0 |
| test_documentation | 8 | 8 | 0 | 0 |
| test_idempotency | 6 | 6 | 0 | 0 |
| test_inventory | 18 | 18 | 0 | 0 |
| test_rendering | 10 | 10 | 0 | 0 |
| test_security | 23 | 23 | 0 | 0 |
| test_workflows | 35 | 35 | 0 | 0 |
| **Total unittest** | **112** | **112** | **0** | **0** |

Additional observed checks:

- verify_local.py: 12/12 PASS, including all Python compilation, actual Netmiko API
  parameters/imports, default plan determinism/three targets, help, invalid arguments
  and targets, working-directory independence, no tracked raw artifacts. No network.
- security_validation.py: STATIC PASS for 9 base +21 conditional fragments and
  comment-only proposal checks. This is NOT an IOS syntax or runtime certification.
- Existing Member2 static_audit.py: STATIC PASS. Still NOT a Cisco/EVE test PASS.
- Standard unittest discovery command: PASS after implementation/repair.
- git diff --check: PASS; no merge markers in Member3 text, no protected file hash changes.
- Raw backup/state/log directories contain only .gitkeep. QA evidence and .venv are ignored.

Local reproducible evidence (ignored, not a claim of committed runtime evidence):
`Automation/reports/offline-test-results.json`, `Automation/reports/offline-tests.txt`.
Run the commands below to regenerate on a clean checkout:

```powershell
.\.venv\Scripts\python.exe -B Automation/run_offline_tests.py
.\.venv\Scripts\python.exe -B Automation/verify_local.py
.\.venv\Scripts\python.exe -B Automation/security_validation.py
.\.venv\Scripts\python.exe -B TVI_Member2_Lightweight_Lab_v1/tests/static_audit.py
git diff --check
```

## Analyze / implement / test / repair record

1. Implemented inventory/core/CLI; initial 28 inventory/rendering tests passed.
2. Implemented mocked SSH/backups/idempotency/workflows and verified positive/negative
   paths, then implemented additive Step7 modules and packet/contract checks.
3. Expanded negative tests exposed FOUR defects: missing Snooping-global acceptance,
   missing PortSec parameter acceptance, an unapproved Guest service exception not
   rejected, and an unfamiliar IOS percent error misclassified as post-check failure.
   Fixed actual validator/CLI-error logic; retained every failing test; focused reruns passed.
4. Further source review added unknown-port rejection, explicit unknown partial count,
   best-effort partial-state diagnostics, protected unowned VLAN checks, fail-fast apply,
   actual Netmiko signature checks, single-JSON audit output and gated source directories.
5. Added documentation/path/Windows command tests, collision/disk failures and conditional
   policy boundaries; complete unittest, local smoke and upstream regression passed.

No test was removed, weakened, or marked skipped to obtain a passing result.
No source static result was promoted to runtime verification.

## Runtime limits, risks and exact handover

See [external dependencies](DEPENDENCIES.md),
[Security policy matrix](../Draft_Modules/member3_security_nat/SECURITY_POLICY_MATRIX.md),
[integration notes](../Draft_Modules/member3_security_nat/integration_notes.md).

M1 must supply real .50 backend/default route/DNS/NTP behavior, static MAC-IP-port
inventory, AP fan-out, actual SSH/AAA/VTY state and binding/reboot evidence. Existing
M1 literal credential source was not copied or modified; coordinate remediation if used.
M2 must supply campus/Management IPv4/IPv6 routing and return routes, public/synthetic
exit strategy, image/parser and bidirectional ESP evidence. Current transport-only BGP
also lacks return routes for public IPv6 Guest source traffic. M3 adds no NAT66 workaround.
Leader must approve corporate flow matrix, extra admin/IPv6 sources, Guest NTP decision,
banner wording and optional AAA/Syslog design; provide full EVE topology/console capacity
and integrate final configs/report. The ten final startup files remain empty.

NAT ACL deny is no-translation, NOT a packet drop or VPN kill switch: missing private
tunnel routes can leak untranslated traffic via a physical default. Routing/capture
verification is mandatory. DAI cannot safely protect unknown static endpoints. VTY
activation may lock out administrators if its console/route/account prerequisites are
ignored. Raw backups contain recoverable device secrets; protect NTFS permissions.
Atomic hard-link publication requires a compatible local filesystem. Older IOS SSH/
security command compatibility is unverified; no silent algorithm downgrade is made.

## Next EVE-NG sequence

1. Integrate M1/M2 LAN/WAN/routing/server base, check two-way Management/server routes
   and actual image/interface mappings from console.
2. Bootstrap/verify SSH without replacing existing accounts/keys; pin verified host keys.
3. Apply reviewed per-device safe fragments one at a time, confirm NAT, Guest dual-stack,
   DHCP continuity, Snooping/PortSec and regressions with actual clients.
4. Activate only binding-proven DAI20 and the correct VTY candidate from console;
   keep unsafe static-host VLANs and unapproved corporate ACLs disabled.
5. Perform Step9 audit/review, then authorized single-HQ-switch apply and fresh-audit
   no-op rerun; extend to remote switches only after reachability is demonstrated.
6. Test HSRP/STP/LACP path changes, Security/SSH/DHCP continuity, manual persistence,
   controlled restart and sanitized submission evidence.

Exact commands/expected observations: [Security test plan](../Draft_Modules/member3_security_nat/SECURITY_TEST_PLAN.md),
[SSH runbook](../Draft_Modules/member3_security_nat/SSH_BOOTSTRAP.md), [Step9 README](README_STEP9.md).

## Files created or modified

The following observed Git changes are in the authorized Member3/doc scope;
ignored .venv and generated QA artifacts are not listed as source changes:

- `.gitignore`
- `Automation/auto_provision.py`
- `Automation/inventory.yaml`
- `Draft_Modules/member3_security_nat/README_MEMBER3.md`
- `Draft_Modules/member3_security_nat/member3_security_nat_draft.cfg`
- `README.md`
- `Automation/DEPENDENCIES.md`
- `Automation/IMPLEMENTATION_REPORT.md`
- `Automation/README_STEP9.md`
- `Automation/automation_core.py`
- `Automation/config/baseline.yaml`
- `Automation/reports/.gitkeep`
- `Automation/requirements.lock.txt`
- `Automation/requirements.txt`
- `Automation/run_offline_tests.py`
- `Automation/security_validation.py`
- `Automation/states/.gitkeep`
- `Automation/tests/helpers.py`
- `Automation/tests/protected_manifest.json`
- `Automation/tests/test_backup.py`
- `Automation/tests/test_documentation.py`
- `Automation/tests/test_idempotency.py`
- `Automation/tests/test_inventory.py`
- `Automation/tests/test_rendering.py`
- `Automation/tests/test_security.py`
- `Automation/tests/test_workflows.py`
- `Automation/verify_local.py`
- `Draft_Modules/member3_security_nat/SECURITY_POLICY_MATRIX.md`
- `Draft_Modules/member3_security_nat/SECURITY_TEST_PLAN.md`
- `Draft_Modules/member3_security_nat/SSH_BOOTSTRAP.md`
- `Draft_Modules/member3_security_nat/conditional/DANANG-LOG-RTR01_vty_0_15.cfg`
- `Draft_Modules/member3_security_nat/conditional/DANANG-LOG-RTR01_vty_0_4.cfg`
- `Draft_Modules/member3_security_nat/conditional/DANANG-LOG-SW01_vty_0_15.cfg`
- `Draft_Modules/member3_security_nat/conditional/DANANG-LOG-SW01_vty_0_4.cfg`
- `Draft_Modules/member3_security_nat/conditional/HANOI-RND-RTR01_vty_0_15.cfg`
- `Draft_Modules/member3_security_nat/conditional/HANOI-RND-RTR01_vty_0_4.cfg`
- `Draft_Modules/member3_security_nat/conditional/HANOI-RND-SW01_dai_vlan20.cfg`
- `Draft_Modules/member3_security_nat/conditional/HANOI-RND-SW01_vty_0_15.cfg`
- `Draft_Modules/member3_security_nat/conditional/HANOI-RND-SW01_vty_0_4.cfg`
- `Draft_Modules/member3_security_nat/conditional/HANOI-RND-SW02_dai_vlan20.cfg`
- `Draft_Modules/member3_security_nat/conditional/HANOI-RND-SW02_vty_0_15.cfg`
- `Draft_Modules/member3_security_nat/conditional/HANOI-RND-SW02_vty_0_4.cfg`
- `Draft_Modules/member3_security_nat/conditional/HCMC-CORE-SW01_dai_vlan20.cfg`
- `Draft_Modules/member3_security_nat/conditional/HCMC-CORE-SW01_vty_0_15.cfg`
- `Draft_Modules/member3_security_nat/conditional/HCMC-CORE-SW01_vty_0_4.cfg`
- `Draft_Modules/member3_security_nat/conditional/HCMC-DIST-SW01_vty_0_15.cfg`
- `Draft_Modules/member3_security_nat/conditional/HCMC-DIST-SW01_vty_0_4.cfg`
- `Draft_Modules/member3_security_nat/conditional/HCMC-DIST-SW02_vty_0_15.cfg`
- `Draft_Modules/member3_security_nat/conditional/HCMC-DIST-SW02_vty_0_4.cfg`
- `Draft_Modules/member3_security_nat/conditional/HCMC-EDGE-RTR01_vty_0_15.cfg`
- `Draft_Modules/member3_security_nat/conditional/HCMC-EDGE-RTR01_vty_0_4.cfg`
- `Draft_Modules/member3_security_nat/devices/DANANG-LOG-RTR01_step7.cfg`
- `Draft_Modules/member3_security_nat/devices/DANANG-LOG-SW01_step7.cfg`
- `Draft_Modules/member3_security_nat/devices/HANOI-RND-RTR01_step7.cfg`
- `Draft_Modules/member3_security_nat/devices/HANOI-RND-SW01_step7.cfg`
- `Draft_Modules/member3_security_nat/devices/HANOI-RND-SW02_step7.cfg`
- `Draft_Modules/member3_security_nat/devices/HCMC-CORE-SW01_step7.cfg`
- `Draft_Modules/member3_security_nat/devices/HCMC-DIST-SW01_step7.cfg`
- `Draft_Modules/member3_security_nat/devices/HCMC-DIST-SW02_step7.cfg`
- `Draft_Modules/member3_security_nat/devices/HCMC-EDGE-RTR01_step7.cfg`
- `Draft_Modules/member3_security_nat/integration_notes.md`
- `Draft_Modules/member3_security_nat/proposals/corporate_acl.cfg.disabled`
- `Draft_Modules/member3_security_nat/proposals/dai_pending.cfg.disabled`
