# Member 3 - Step 7 Security and Step 9 Automation

Only additive local source was implemented. No device has been configured or
runtime-verified here. [IP Schema](../../Specs/IP_Addressing_Schema.md) remains immutable.
[Step 9](../../Automation/README_STEP9.md) intentionally cannot deploy Step 7 fragments.

## Artifact classes

* `devices/<exact-hostname>_step7.cfg`: nine enterprise device-specific additive
  fragments. Preconditions still include correct base LAN/WAN configuration,
  console fallback, backup, real image parser and object-name collision review.
* `conditional/`: executable candidates with MANUAL preflight gates. Never paste
  the whole directory or both VTY range variants. Not an automatic deployment source.
* `proposals/*.cfg.disabled`: comments only, no active blanket-deny ACL or fake MAC.
* `member3_security_nat_draft.cfg`: deprecated non-executable pointer, not a duplicate implementation.

Read [policy decisions](SECURITY_POLICY_MATRIX.md), [integration notes](integration_notes.md),
[SSH bootstrap/recovery](SSH_BOOTSTRAP.md) and [test sequence](SECURITY_TEST_PLAN.md).

## NAT/PAT and Guest ACL

| Router | NAT outside | NAT inside |
|---|---|---|
| HCMC-EDGE-RTR01 | Gi0/0 | Gi0/1, Gi0/2 |
| HANOI-RND-RTR01 | Gi0/0 | Gi0/1.20, Gi0/1.50, Gi0/1.99 |
| DANANG-LOG-RTR01 | Gi0/0 | Gi0/1.30, Gi0/1.99 |

PAT matches exact site-local LAN/management subnets only. M3_NAT_INTERNET denies
RFC1918 and the simulated WAN transport range as translation destinations before
local-source Internet permits. NAT ACL deny means NO TRANSLATION, not packet drop.

M2 uses GRE over IPv4 with crypto-map TVI-GRE-CMAP on physical Gi0/0. Tunnel traffic
is routed into GRE, outer source is Gi0/0, then matched GRE outer packets are protected
by the existing IPsec map. There is no NAT marking on tunnels, no crypto selector/map
change, no static NAT and no NAT66. Exemptions also prevent private translation if
traffic selects the physical default path; they do NOT force encryption or stop a
plaintext private packet from being forwarded. Correct private routes over tunnels,
transport routes over ISP and no ISP private transit are mandatory integration gates.
The source ACL checks cannot emulate IOS NAT/GRE processing or prove encryption.

Hanoi Gi0/1.50 IN attaches M3_GUEST4_IN and M3_GUEST6_IN. IPv4 permits DHCP bootstrap,
broadcast rebinding and UDP68->67 renewal to .50/the Guest gateway; all other private
server/management/transit access is denied. Guest DNS is public 8.8.8.8 per BOTH M1
DHCP alternatives. Public Internet access is allowed only for the Guest source subnet.
No private DNS/NTP/SSH exception was invented. Guest access to .50 NTP advertised by
one DHCP alternative remains pending; do not treat DHCP options as ACL authorization.

IPv6 explicitly permits bounded on-link NS/NA, DAD and router solicitation, rejects
Guest router advertisements/redirects, blocks all three corporate site /48s, overlay,
WAN transport, ULA and non-exempt link-local/multicast destinations. Only Guest-source
public traffic reaches the final permit. Return RA/ND and ICMPv6 Packet Too Big enter
Guest via egress on this subinterface, not the inbound ACL; do not attach it OUT.
No DHCPv6 server or IPv6 DNS endpoint was invented. Router ACLs cannot stop same-VLAN
L2 attacks or authenticate ND; AP/client isolation and IPv6 first-hop protection are
separate design decisions, not claimed complete here.

## L2 scope and trust

| Switch | Snooping VLANs | DHCP trusted ports | DAI trusted ports | Port Security |
|---|---|---|---|---|
| HQ CORE | 10,20 | Gi0/0 server; Gi0/1-2 uplinks | Gi0/1-2 | Gi0/3, Gi1/0-1 |
| Hanoi SW01 | 20,50 | Gi0/1; Gi0/2-3 and Po1 | Gi0/1; Gi0/2-3 and Po1 | Gi1/0-1 |
| Hanoi SW02 | 20,50 | Gi0/2-3 and Po1 | Gi0/2-3 and Po1 | Gi1/0-1 |
| Da Nang SW01 | 30 | Gi0/1 | Gi0/1 | Gi1/0-1 |

Client ports are explicitly untrusted. DHCP rate15pps applies only to known wired
client ports. AP fan-out is unknown: no restrictive AP MAC/rate limit. Port Security
uses max2/sticky/restrict, allowing a small workstation/VM variation while logging
violations without err-disabling the entire port. Verify legitimate MAC counts before
use. No Port Security on server/controller/AP/trunks/Po members. No port membership,
PortFast/BPDU Guard, STP, native999, allowed-VLAN or LACP changes are made.
Hanoi SW02 Gi0/1 stays unused/shutdown under M1; this module does not touch it.

Option82 insertion is explicitly disabled on these access switches: no approved
Option82 consumer exists and M1 relay fragments do not establish acceptance of
Option82 with giaddr0 from downstream snooping. This compatible baseline leaves DHCP
relay/server settings untouched; do not add allow-untrusted or trust-all on user ports.
If M1 later requires Option82, a coordinated relay/server design and DORA regression
must replace this choice. M1 IOS server trust-all alone is not proof of relay behavior.

DAI trust commands alone do NOT enable inspection. DAI VLAN20 activation is separate
for HQ CORE and Hanoi SW01/02, gated on all relevant actual bindings or approved
static exceptions and binding recovery after reboot. No active DAI for VLAN10,50,30
or99: missing static server/AP/IoT data are listed in proposals/dai_pending.cfg.disabled.
DHCP trust on HQ server Gi0/0 is NOT DAI trust. No redundant ARP ACL is manufactured
for a trusted interface; an approved ARP ACL is needed only for statics entering
untrusted interfaces. DIST Snooping/DAI are intentionally absent.

## Hardening and merge procedure

Nine base fragments set SSHv2/timeouts, disable plain HTTP/PAD and add log timestamps.
They do not create accounts, alter enable secret, generate keys, enable AAA or attach
VTY policy. The existing M1 local users are preserved. Router SSH remains unusable
until console bootstrap creates an approved account/key and routing is correct.
ISP is outside these nine enterprise fragments; coordinate any ISP changes with M2/Leader.

Check exact hostname, backup, inspect existing M3_* objects and attachments; STOP on
collision and review an explicit object update. Enter global configuration mode via
console and apply only the matching reviewed fragment. Files omit hostname, conf t,
end, write memory and reset commands. Do not concatenate raw startup/module files:
M1 fragments end in end, while M2 fragments expect global configuration context.
Stop on any unsupported command; don't silently substitute interface/crypto settings.

All corporate SVI ACL decisions remain unapproved, including equivalent policies on
both HQ DIST switches. Those comments do not authorize attaching an empty ACL.
VTY conditional files permit IPv4 controller 192.168.1.100 only and close IPv6 SSH
until authorized source addresses exist. Choose actual VTY range and prove alternate
console/new controller session before restricting it; existing AAA needs a separate
method-list-compatible review. See the console runbook.

Static validator: [security_validation.py](../../Automation/security_validation.py).
It is a restricted grammar/packet-match model, not a Cisco IOS syntax validator.
Reference: [Cisco GRE/IPsec NAT](https://www.cisco.com/c/en/us/support/docs/ip/generic-routing-encapsulation-gre/9221-quicktip.html),
[Cisco Snooping](https://www.cisco.com/c/en/us/support/docs/ip/dynamic-host-configuration-protocol-dhcp-dhcpv6/217055-operate-and-troubleshoot-dhcp-snooping.html).
