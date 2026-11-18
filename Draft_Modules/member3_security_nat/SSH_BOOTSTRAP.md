# Console SSH bootstrap, VTY gates and recovery

MANUAL FUTURE LAB RUNBOOK. Nothing here was run on devices during development.
Do not paste commands with angle-bracket placeholders. Use an independently reachable
console and private running/startup backup. Never export passwords or PSKs in evidence.

## 1. Inspect first, on each exact device

```text
show version
show running-config | include ^hostname
show ip interface brief
show ipv6 interface brief
show ip ssh
show crypto key mypubkey rsa
show line
show running-config | section line vty
show running-config | section aaa
show running-config | include ^username
```

Last command contains credential hashes/values: view privately, never capture in report.
Determine actual VTY maximum from image/console (0..4 or 0..15 are prepared candidates;
if different, STOP and review the actual supported range). Do not assume both exist.
Observe local account privilege and current AAA method lists. Existing six M1 switch
accounts remain unchanged; notify M1 about source literal credentials without exposing them.
Routers need an approved local administrative account if none exists. Create it
interactively at console using a privately entered secret, not a checked-in command.
Do not change an existing account, AAA or enable secret as part of generic Step9.

## 2. Keys and baseline

Hostname must already match Schema. Apply only that device's safe hardening fragment.
If keys already exist, do NOT regenerate them. If no key exists, generate an approved
2048-bit RSA key interactively at console only after authorization for that lab node:

```text
crypto key generate rsa general-keys modulus 2048
```

The key command is not in any automatic or base fragment. Inspect IOS `?` if syntax
is unsupported; preserve domain tvi.lab and existing keys. Recheck `show ip ssh`;
`ip ssh version 2` alone is not evidence of a working SSH server.

## 3. Controller reachability and key pinning

M2 must first complete forward and return routes. From device check route to
192.168.1.100 and sourced reachability using the approved management address.
From controller test a fresh SSH session and verify the public-key fingerprint against
the trusted console/administrator before adding it to known_hosts. Do not run automation
with auto-accepted unknown host keys. Never downgrade algorithms without image review.

## 4. Conditional VTY restriction

Choose exactly one matching conditional/<hostname>_vty_0_4.cfg OR _vty_0_15.cfg,
only if its range matches all real VTYs and local login is already tested.
If AAA is configured, do NOT paste login local blindly: coordinate an approved
method-list-compatible variant and test fallback first. IPv4 permits only controller
192.168.1.100, which is established in the approved topology. Other admin IPv4 sources
need Leader approval. IPv6 VTY denies all until an approved admin IPv6 address exists.
This intentionally blocks IPv6 SSH, not IPv6 routing or ND.

Keep console and existing session open. Apply the reviewed VTY candidate, then establish
a NEW SSH session from .100. Verify privilege and that unauthorized sources are refused.
Do not close the console before this succeeds. No login block-for command was added:
shared-admin lockout behavior is not approved.

## 5. Recover from console

Do not reset the device, replace keys or delete accounts. Restore the specific previous
VTY/AAA/access-class stanza from the private pre-backup. If the only error was the
new management access-class, remove that attachment on the same actual VTY range
with `no access-class M3_MGMT_VTY in` / `no ipv6 access-class M3_MGMT6_VTY in`,
then restore the approved prior access policy; do not leave access broadly open.
For partial baseline apply, inspect the pre-backup and manually reverse only M3-owned
VLAN/name/NTP/banner changes. Never restore a fragment as a full startup-config.
Save configuration only after fresh-login, security and reachability checks pass.
