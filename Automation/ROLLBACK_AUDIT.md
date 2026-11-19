# Step 9 rollback workspace audit

Audit performed before implementation, 2026-11-19. Branch:
`feature/security-automation`. Existing uncommitted edits: `.gitignore`, `README.md`;
these are preserved. No AGENTS.md was found. Baseline: 112 unittest tests pass.

`auto_provision.main` validates inventory/baseline/selection and review, then
`batch` calls `operate`. `operate` connects with strict pinned SSH keys, validates
prompt/enable/hostname/management state, collects three show commands, checks the
raw state hash and exact reviewed commands, saves a pre JSON, calls one Netmiko
configuration batch, collects post state and checks desired/protected state.
`ArtifactStore` publishes fsynced files with exclusive hard links. Existing failure
handling saves a partial JSON only; Ctrl-C previously skipped even that capture.

Installed Netmiko 4.8.0 `BaseConnection.send_config_set` was inspected locally:
`error_pattern` checks output per command in both echo-verification and banner
bypass paths. It raises ConfigInvalidException before its normal exit-config-mode
step. ReadTimeout/transport loss leaves the actual applied count unknown. Recovery
must establish exec mode, recollect state and never infer success from command echo.

Step 9 owns site-approved corporate VLAN existence/name, the approved NTP server
entry and explicitly enabled MOTD only. M3 Step 7 owns separate security fragments;
they are not automation inputs. M1 owns LAN ports/SVIs/STP/HSRP/DHCP, M2 owns
routing/WAN/GRE/IPsec, and credentials/AAA/SSH are protected. The IP schema and M1
trunk sources define the contract. Configurations contains ten empty final slots.
No exact running IOS image, filesystem checkpoint support or successful replace
evidence exists locally. Whole-device replacement is therefore unjustified and
will not be used. IOS CLI/parser support remains a live preflight dependency.

Changes required: `automation_core.operate/batch/Result/ArtifactStore` for the
transaction and evidence; `auto_provision.parser/main` for double-confirmed
single-device demo gates; a focused recovery module for inverse construction and
strict comparisons; extend `tests/helpers.FakeSession` with real inverse mutations;
add state-based recovery tests; update local API checks, README/report and demo
runbook. Existing tests remain regression coverage. No Step 1–8 sources, baseline,
inventory, integrated configs or user edits need modification.
