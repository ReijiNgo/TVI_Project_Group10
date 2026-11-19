# Step 9: live EVE-NG rollback demonstration

Prepared for Windows PowerShell. **No live run has been performed by Codex.**
The tests use fake sessions; only artifacts from your live run can prove EVE-NG
recovery. Allow 2–3 minutes for Demo B after preparing the environment. Commands
below run from the repository root and use the existing project virtualenv.

## Prepare once, before presenting

Use an isolated, approved `HANOI-RND-SW01` at `192.168.2.10`, with working SSH,
console fallback and no other configuration writers. Other enabled approved
switches are HCMC-CORE-SW01 and DANANG-LOG-SW01; a demo accepts exactly one
explicit `--device`, no groups, optional devices or batches.

Check two-way management routing, controller access, and pin the SSH host key by
verifying its fingerprint through the trusted lab console. Follow the existing
[SSH bootstrap runbook](../Draft_Modules/member3_security_nat/SSH_BOOTSTRAP.md).
Do not accept an unverified key or replace existing accounts, VTY or AAA.

On the EVE console, record the actual image/version and inspect parser support:

```cisco
show version
show vtp status
show running-config
show ip interface brief
show vlan brief
show running-config | include ^ntp server
```

Vlan99 must have 192.168.2.10 and be up/up. The VLAN and interface tables must be
complete and recognized by the script. VLAN changes require `vtp mode transparent`
or `vtp mode off` explicitly present in running-config. If not already local,
arrange the VTP mode with the switching owner **before** this demonstration;
the automation does not change it. For the NTP-only demo below, first make all
site VLANs compliant (20 RND_ENGINEERING, 50 GUEST_WIFI, 99 MANAGEMENT,
999 BLACKHOLE). Never delete these VLANs to manufacture a demo difference.

Use console context help to check the commands needed for your chosen delta:

```cisco
configure terminal
ntp server ?
no ntp server ?
end
```

The NTP demo uses only the plain `ntp server 10.10.10.50` entry. If it has options
(prefer, source, key, VRF, etc.), do not simplify that configuration for this demo.
The workflow preserves existing options and unrelated servers. For an approved
VLAN rename demonstration, confirm `vlan <id>`, `name`, and `no name` syntax on
your exact image; for creation, confirm `no vlan <id>` and no port dependencies.
MOTD is disabled by default. Banner recovery supports absent or single printable
ASCII original text; multiline/control-character originals reject an attempted
banner change before mutation. Never enable a banner merely to create a fault.

Protect the local Automation runtime directories using Windows Security
properties: restrict access to your controller account and required system/admin
accounts. Check the ACL; do not use a shared/cloud directory. For example:

```powershell
Get-Item Automation\backups,Automation\states,Automation\reports,Automation\logs | ForEach-Object { icacls $_.FullName }
Test-NetConnection 192.168.2.10 -Port 22
$env:TVI_SSH_USERNAME = Read-Host 'Existing SSH username'
```

Leave password/enable-secret environment variables unset to use the CLI's hidden
getpass prompts. Never paste passwords into commands, scripts or lecturer slides.
No credentials or raw configurations are printed by this workflow.

## Demo A — normal automation

Use unique filenames each time: artifacts are never overwritten. Offline plan is
read-only and cannot authorize apply. Audit produces the state-bound review.

```powershell
$normalTag = Get-Date -Format 'yyyyMMddTHHmmssfff'
$normalReview = "Automation/reports/hanoi-normal-$normalTag.json"
.\.venv\Scripts\python.exe -B Automation/auto_provision.py --mode plan --device HANOI-RND-SW01
.\.venv\Scripts\python.exe -B Automation/auto_provision.py --mode audit --device HANOI-RND-SW01 --out "reports/hanoi-normal-$normalTag.json"
if ($LASTEXITCODE -ne 0) { throw 'Audit failed; stop' }
Get-Content -LiteralPath $normalReview
.\.venv\Scripts\python.exe -B Automation/auto_provision.py --mode apply --device HANOI-RND-SW01 --review-plan $normalReview --confirm
if ($LASTEXITCODE -ne 0) { throw 'Apply failed; inspect its recovery report before continuing' }
.\.venv\Scripts\python.exe -B Automation/auto_provision.py --mode audit --device HANOI-RND-SW01 --out "reports/hanoi-after-normal-$normalTag.json"
(Get-Content "Automation/reports/hanoi-after-normal-$normalTag.json" -Raw | ConvertFrom-Json).targets.commands
```

The last command should show an empty command list. Check running configuration,
VLAN names and NTP entry through the console too. If the initial state was already
compliant, apply is an honest no-op; no successful change is claimed. To show an
actual normal change, prepare the same approved isolated NTP difference described
below before generating Demo A's fresh review.

## Demo B — failure after a real change, then automatic recovery

The pre-demo difference is intentionally the state to which rollback must return.
On the isolated lab console, **only when the NTP entry is currently the plain
entry shown above**, remove it for this approved demonstration:

```cisco
configure terminal
no ntp server 10.10.10.50
end
show running-config | include ^ntp server
show running-config
show ip interface brief
show vlan brief
```

Do not save startup-config. Do not change AAA, Syslog, routes, interfaces or VLAN
memberships. Keep this console available. The demo should now have exactly one
pending command: `ntp server 10.10.10.50`. The automation captures the initial
configuration in both private pre.json and pre.cfg before sending that command.

In PowerShell:

```powershell
$demoTag = Get-Date -Format 'yyyyMMddTHHmmssfff'
$demoReview = "Automation/reports/hanoi-rollback-$demoTag.json"
.\.venv\Scripts\python.exe -B Automation/auto_provision.py --mode audit --device HANOI-RND-SW01 --out "reports/hanoi-rollback-$demoTag.json"
if ($LASTEXITCODE -ne 0) { throw 'Audit failed; stop' }
$demoPlan = Get-Content -LiteralPath $demoReview -Raw | ConvertFrom-Json
$demoPlan.targets.commands
if (@($demoPlan.targets).Count -ne 1 -or @($demoPlan.targets[0].commands).Count -ne 1 -or $demoPlan.targets[0].commands[0] -ne 'ntp server 10.10.10.50') { throw 'Unexpected demo delta; inspect the device and create a fresh review' }
.\.venv\Scripts\python.exe -B Automation/auto_provision.py --mode apply --device HANOI-RND-SW01 --review-plan $demoReview --confirm --demo-rollback --confirm-demo
$demoExit = $LASTEXITCODE
if ($demoExit -ne 1) { throw 'Expected apply failure exit 1; inspect actual output' }
```

This applies the first complete reviewed object, reads the device back to prove
the change, saves a `demo_changed` snapshot, then raises an application exception.
It invokes the same recovery path as a real partial failure. Echo-only or unchanged
state cannot trigger the claimed controlled fault. No arbitrary failing IOS
command is injected. The screen must report all five comparisons as MATCH and
`FINAL STATUS: APPLY FAILED / ROLLBACK VERIFIED` for a verified demonstration.
If not, present the actual failure and follow manual recovery below.

## Show proof to the lecturer

Use the exact `report_path` printed by this run. The following selects the latest
Hanoi report and guards against accidentally showing a normal/older operation:

```powershell
$reportFile = Get-ChildItem Automation/reports/HANOI-RND-SW01_*_rollback_report.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$recovery = Get-Content -LiteralPath $reportFile.FullName -Raw | ConvertFrom-Json
if (-not $recovery.demo_requested -or -not $recovery.controlled_failure_injected -or $recovery.recovery_status -ne 'verified') { throw 'Latest report is not a verified injected-failure demo' }
$recovery | Select-Object hostname,operation_id,started_at,ended_at,failure_category,mutation_possible,mutation_observed,rollback_attempted,recovery_status,apply_success,controlled_failure_injected
$recovery.verification | Format-List
$recovery.diff_summary | Format-List
$recovery | Select-Object pre_config,pre_snapshot,demo_changed_snapshot,restored_snapshot
$pre = Get-Content -LiteralPath $recovery.pre_snapshot -Raw | ConvertFrom-Json
$changed = Get-Content -LiteralPath $recovery.demo_changed_snapshot -Raw | ConvertFrom-Json
$restored = Get-Content -LiteralPath $recovery.restored_snapshot -Raw | ConvertFrom-Json
[pscustomobject]@{
    BeforeNtp = $pre.state.running -match '(?m)^ntp server 10\.10\.10\.50\s*$'
    ChangedNtp = $changed.state.running -match '(?m)^ntp server 10\.10\.10\.50\s*$'
    RestoredNtp = $restored.state.running -match '(?m)^ntp server 10\.10\.10\.50\s*$'
    RawConfigEqual = ($pre.state.running -ceq $restored.state.running)
}
Get-Item -LiteralPath $recovery.pre_config,$recovery.pre_snapshot,$recovery.demo_changed_snapshot,$recovery.restored_snapshot,$reportFile.FullName | Select-Object Name,Length,LastWriteTime
```

For this prepared NTP scenario, BeforeNtp/ChangedNtp/RestoredNtp should be
False/True/False. RawConfigEqual may be false because of IOS timestamps; the
mandatory canonical full-config check must still be MATCH. Do not substitute a
raw checksum for semantic proof. The report contains counts of changed canonical
lines, never sensitive line contents. Keep pre.cfg and JSON snapshots private;
show sanitized report fields, not the full configuration, on the projector.

For a fresh independent read-only check after recovery:

```powershell
.\.venv\Scripts\python.exe -B Automation/auto_provision.py --mode audit --device HANOI-RND-SW01 --out "reports/hanoi-after-rollback-$demoTag.json"
(Get-Content "Automation/reports/hanoi-after-rollback-$demoTag.json" -Raw | ConvertFrom-Json).targets.commands
```

That review should again propose NTP: rollback restored the pre-demo missing entry.
The console can independently confirm it with `show running-config | include
^ntp server`, `show ip interface brief`, and `show vlan brief`.

## Cleanup and manual recovery

To return the intentionally prepared device to the approved baseline, inspect
the **new** after-rollback review, then apply normally:

```powershell
.\.venv\Scripts\python.exe -B Automation/auto_provision.py --mode apply --device HANOI-RND-SW01 --review-plan "Automation/reports/hanoi-after-rollback-$demoTag.json" --confirm
Remove-Item Env:TVI_SSH_USERNAME -ErrorAction SilentlyContinue
Remove-Item Env:TVI_SSH_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:TVI_ENABLE_SECRET -ErrorAction SilentlyContinue
```

Only the integration owner should persist running-config after independent
validation. Preserve artifacts until assessment; they are ignored by Git, not
encrypted. Do not publish raw backups or expired reviews.

If recovery is incomplete/unverified, stop other writers and the batch. Use the
EVE console; inspect the exact report's `manual_steps`, `conflicts`,
`recovery_errors` and private pre/partial/restored snapshots. For this NTP-only
demo, restoring the original snapshot means removing **only** the newly added
plain entry if still present:

```cisco
show running-config | include ^ntp server
configure terminal
no ntp server 10.10.10.50
end
show running-config
show ip interface brief
show vlan brief
```

Do not remove an entry somebody else changed. For other deltas, restore original
VLAN names and banner from pre.cfg individually; remove a new VLAN only after
checking current ports, SVIs, trunk dependencies and VTP mode with the switching
owner. Never paste the full backup as a merge, perform configure replace, copy
startup into running, erase or reload as a recovery shortcut. Preserve foreign
drift and involve its owner. Re-audit and compare before accepting recovery.

First Ctrl-C after mutation requests best-effort automatic recovery and returns
130. A second interrupt during recovery marks it unverified. Process kill, lost
controller power or unrecoverable SSH cannot guarantee automatic compensation;
use the console and preserved backup. Unknown IOS output, VLAN membership drift,
concurrent edits, CLI rejection, missing durable evidence or any comparison
mismatch must never be presented as verified recovery. No whole-device restore
or startup-config write is an automatic fallback.
