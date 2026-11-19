# TVI Step 9 - safe network automation

Status: source and fake-session workflows are offline tested. No live SSH, audit,
apply, IOS parser or EVE-NG data plane has been verified during implementation.
See [implementation evidence](IMPLEMENTATION_REPORT.md) and [dependencies](DEPENDENCIES.md).
Automatic scoped rollback is implemented and offline tested. For exact live
commands, preparation and evidence inspection see [EVE-NG rollback demo](DEMO_ROLLBACK_EVE.md).
The initial code/ownership/capability audit is in [rollback audit](ROLLBACK_AUDIT.md).

## Windows installation

Run PowerShell from the repository root. Python 3.10+ is required (implementation
was tested with Python 3.14.4). No activation script or execution-policy change is needed.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Automation/requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -B -m unittest discover -s Automation/tests -v
.\.venv\Scripts\python.exe -B Automation/security_validation.py
.\.venv\Scripts\python.exe -B TVI_Member2_Lightweight_Lab_v1/tests/static_audit.py
.\.venv\Scripts\python.exe -B Automation/verify_local.py
```

[requirements.txt](requirements.txt) declares direct dependencies. The observed
[requirements.lock.txt](requirements.lock.txt) records the installed dependency versions.
Unit tests use unittest/fakes, not pytest or EVE-NG. Netmiko is imported lazily by
live modes; plan requires only PyYAML and the local contract sources.

## Contract and inventory

[inventory.yaml](inventory.yaml) has four approved management switches. The three
mandatory switches are enabled; HANOI-RND-SW02 stays disabled and requires both
`--device HANOI-RND-SW02` and `--include-optional` for selection. Enabling it in YAML
is rejected. Groups are HCMC, HANOI, DANANG, selecting enabled targets only.
The full inventory is validated before selection or any SSH activity.

Fields: hostname, management_ip, device_type (`cisco_ios` only, SSH), integer port
1..65535, site, strict boolean enabled, profile. Only contract hostname/IP pairs
are accepted. Baseline VLAN sets are derived from M1's actual trunk allowed lists
plus BLACKHOLE; VLAN names and NTP endpoint come from the immutable Schema.

* HCMC: 10,20,99,999; Hanoi: 20,50,99,999; Da Nang: 30,99,999.
* Existing unrelated VLANs and their state are preserved; no port membership changes.
* The optional switch is never selected through a group or by default.

## Offline plan (default)

```powershell
.\.venv\Scripts\python.exe -B Automation/auto_provision.py
.\.venv\Scripts\python.exe -B Automation/auto_provision.py --mode plan --device HCMC-CORE-SW01
.\.venv\Scripts\python.exe -B Automation/auto_provision.py --mode plan --device HANOI-RND-SW02 --include-optional
```

This validates and prints deterministic JSON potential changes without SSH, credential
prompts or runtime writes. No current state is assumed: `state_sha256` is null.
Such a desired-only plan is deliberately rejected by apply. It is not a live diff.
Use `--out reports/desired-plan.json` to publish a NEW plan file without overwriting.
Paths default to the Automation directory independent of shell working directory.

## Credentials and host keys (for a later authorized lab session)

SSHv2 must already be bootstrapped. Use the [console runbook](../Draft_Modules/member3_security_nat/SSH_BOOTSTRAP.md).
Set only a username if desired; passwords/optional enable secret are securely prompted
on an interactive terminal. For unattended use, the supported environment variables are
`TVI_SSH_USERNAME`, `TVI_SSH_PASSWORD`, `TVI_ENABLE_SECRET`; do not put their values
in scripts, Git, screenshots, terminal transcripts or shell history. No .env file is loaded.
Non-interactive execution without required credentials fails without connecting.

```powershell
$env:TVI_SSH_USERNAME = Read-Host 'Approved SSH username'
```

Populate the controller user's OpenSSH known_hosts only AFTER comparing the device's
public-key fingerprint through a trusted console/administrator. Audit/apply require
an existing nonempty known_hosts file. Netmiko uses strict host-key checking and
never automatically accepts unknown keys. `--known-hosts` can name a verified file;
it does not authorize bypassing host-key checks. Older IOS SSH algorithm compatibility
must be tested; the program never silently downgrades crypto or replaces RSA keys.

## Read-only audit and review

The following commands are instructions for a future authorized lab session, not
commands executed during development:

```powershell
.\.venv\Scripts\python.exe -B Automation/auto_provision.py --mode audit --device HCMC-CORE-SW01 --out reports/hq-review.json
```

Audit obtains running-config, IPv4 interface brief and VLAN brief. Running-config
also supplies NTP/banner/management settings. Unsupported VLAN brief is recorded as
unavailable in audit, but blocks apply. Mandatory outputs must be nonempty, complete,
not paginated, and contain the expected hostname and up/up Vlan99 management IP.
Audit may enter privileged EXEC using the supplied enable secret; it never calls
send_config_set, changes AAA/credentials, or writes startup-config.

The new review file contains commands plus current-state, contract, baseline and
inventory identity bindings. Inspect its exact targets and command list. Audit stdout
is one JSON result object; without `--out` it embeds the review under `review`.
Partial audit failure returns nonzero and does not publish an apply review file.

## Explicit apply (future lab only)

```powershell
.\.venv\Scripts\python.exe -B Automation/auto_provision.py --mode apply --device HCMC-CORE-SW01 --review-plan Automation/reports/hq-review.json --confirm
```

`--review-plan` is resolved by the shell working directory; `--out` is relative to
Automation. Use an absolute review path when invoking from another directory.
An explicit device list OR approved site group, confirmation and audit-based review
are all required. Never substitute a desired-only offline plan for an audit review.

Order: validate all input -> strict SSH -> prompt identity -> optional enable ->
collect/validate complete state -> reject stale/tampered review -> atomic pre-backup ->
read back JSON and private CFG backup -> allowlisted commands only -> collect/save
post-state -> desired-state AND protected-state checks. Any error after mutation
starts enters scoped recovery; successful rollback still returns failed apply.
A fully compliant reviewed state is a successful no-op and sends zero config commands.
A second run needs a fresh audit/review; reusing the old pre-change review fails stale.

Apply changes RUNNING configuration only. It never saves startup-config, automatically
rolls back another member's configuration, provisions users, generates keys or loads
Step 7 files. After manual validation the integration owner can save the device.
A failed apply stops the remaining batch; unattempted targets are explicitly reported.

## Automatic rollback and verified recovery

Before apply, strict parsers validate running config, VLAN membership and interface
tables. A VLAN delta requires explicit `vtp mode transparent` or `vtp mode off`
in running-config; server/client/default/unknown mode is rejected to prevent
cross-device propagation. Existing changed VLAN names must be safely representable.
An attempted banner change requires an absent or safely restorable single-line
ASCII original; multiline/control/ambiguous text fails before any mutation.
No change to baseline, inventory or Step 7 is required for rollback.

On failure, leave config mode (Netmiko may have raised before exiting), validate
identity, collect/save partial state, and derive compensation from the pre-state
and current device state. Reverse touched objects: restore/remove MOTD, remove
only the newly added plain approved NTP entry, restore original VLAN names or
remove newly created VLANs. New VLAN removal requires empty membership, no extra
attributes, unchanged interface config and local VTP mode. Original implicit
default VLAN names use `no name`. Foreign owned-object edits become conflicts;
unrelated drift is preserved and prevents strict verification.

Transport loss permits one recovery reconnect/retry with the same strict host-key
policy, prompt/enable and snapshot identity checks. Remaining inverses are rebuilt
from the actual device state, never blindly replayed. CLI rejection stops inverse
commands. Recollect all three show commands and save a restored snapshot even
when possible recovery is incomplete.

Verification reports normalized full config, owned state, protected state,
interface state and VLAN state separately. All five must MATCH, no conflicts or
CLI rejection may remain, and restored snapshot/report evidence must be durable
to report `verified`. Raw exact running equality is informational only. Known
show headers/timestamps, separators, CRLF/trailing spaces outside banners and
banner delimiters are normalized; command order, indentation, payload text and
all other commands are retained. Tables compare IP/status/protocol/method and
VLAN existence/name/status/ports; unknown output is UNVERIFIED. Comparisons
cannot prove dataplane reachability, NTP synchronization or uncollected state.

| Apply outcome | recovery_status | Exit |
|---|---|---|
| Successful apply or no-op | not_needed | 0 |
| Rejected before mutation | not_needed | 1 for device preflight, 2 for CLI validation |
| Failed apply, restored and verified | verified | 1 |
| Recovery attempted with mismatch/conflict/rejected command | incomplete | 1 |
| Recovery impossible, unsupported output or missing durable proof | unverified | 1 |
| First Ctrl-C; best-effort recovery if mutation possible | actual recovery result | 130 |

Demo requires `--mode apply --device <one enabled approved hostname>`, an audited
`--review-plan`, `--confirm`, `--demo-rollback` AND `--confirm-demo`. It applies one
complete allowlisted object and proves the delta through readback before raising
`controlled_demo_failure`. No pending change rejects the demo. It uses the real
transaction path. Demo adds human-readable progress before the final JSON; audit
and ordinary apply retain JSON stdout. No live demo is run by local test scripts.

## Declarative scope

[baseline.yaml](config/baseline.yaml) enables NTP at the contract server. MOTD is
null by default: exact wording is not approved in repository. To opt in after approval,
set banner to a mapping with `approved: true` and a single printable ASCII `text`
(no caret, newline or command delimiter). VLAN/NTP/banner drift is compared to actual
state, including IOS's `^C` banner serialization. Already-correct values produce no commands.

AAA and Syslog stay disabled. Enabling either is rejected until an approved method-list/
server/transport design is implemented and reviewed. In particular 10.10.10.50 is NOT
assumed to be Syslog or AAA. Generic provisioning never mutates management authentication.

The command grammar rejects all IP/interface/routing/default-gateway/HSRP/STP/LACP/
trunk/tunnel/crypto/account/VTY changes. Post-check also detects changes to protected
running configuration, unowned VLAN names and interface status.

## Runtime artifacts and errors

* `backups/`: complete pre-change JSON plus private readable `.cfg`, both read back before mutation.
* `states/`: audit, post, partial, restored and demo_changed JSON snapshots.
* `logs/`: per-device structured JSON events with timestamp, category, elapsed time,
  paths, command count and partial-configuration flag; never raw output/exception payloads.
* `reports/`: reviewed plans, per-operation rollback reports and generated local QA results.

Each apply report carries hostname/operation UUID/times, snapshot paths,
authorized command submissions (banner text redacted), mutation possibility and
observed state, original failure category, rollback status, category comparisons,
diff counts without content, conflicts/recovery errors and manual steps. A bulk
submission is an upper bound on attempted commands, not an exact execution trace.
Config command echo never proves applied count after failure (`null`). Report
and snapshot write failures are explicit; missing proof cannot claim verified
recovery. Retain pre-backups unchanged. Reports never include raw configs,
original banner content, inverse names/text or raw exception messages.

All are ignored by Git except .gitkeep. Raw backups can contain recoverable secrets:
use a local NTFS directory restricted to the controller account (verify its ACL in
Windows Security properties), never shared/cloud folders; ignore rules are not access
control or encryption. Existing M1 literal credentials are an upstream handover item.
No live backup/credential was collected in this implementation task.

Names include hostname, UTC microsecond timestamp, pre/post/audit stage and UUID.
Atomic publication uses a temporary file, fsync and exclusive hard link (NTFS/local
POSIX filesystem required); existing files are never overwritten. Temporary files are
removed on failure. Invalid/traversing names and symlink/junction escape paths fail.
Network shares without hard-link support fail closed before mutation.

Failures: malformed input/review/local preflight exits 2; per-device SSH/auth/CLI/
backup/post-check failure exits 1; interruption exits 130; success/no-op exits 0.
Only transient connection establishment is retried, once; recovery can reconnect
and recalculate inverses after transport loss as described above. Authentication,
host-key and CLI failures do not authorize command replay. Sessions are closed
after use. Any IOS `%`
response is treated conservatively as a CLI failure; inspect privately via console.
A partial apply has an unknown applied-command count (`null`), not an invented zero.
The pre-backup remains for operator recovery. Best-effort partial capture and
automatic recovery run after failure, including first Ctrl-C after mutation.
A second recovery interrupt is unverified; killing the process/controller can
prevent recovery entirely. Keep console access and use the runbook's manual
steps. Never use erase/reload/startup merge/configure replace as automatic fallback.

## Network prerequisites and limits

M1 LAN + M2 WAN fragments still require integration. Campus/Management OSPFv2/v3
advertisements and return routes, DHCP/DNS/NTP service availability, SSH bootstrap,
correct EVE interface mapping and host-key pinning must precede live use. Synthetic
ISP 8.8.8.8 is not proof of a DNS service or real Internet access. Local post-checks
verify configuration, not NTP synchronization, end-to-end reachability or failover.

Reference: [Netmiko API](https://ktbyers.github.io/netmiko/docs/netmiko/base_connection.html).
