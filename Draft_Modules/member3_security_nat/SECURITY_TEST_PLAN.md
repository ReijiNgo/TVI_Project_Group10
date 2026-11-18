# EVE-NG Security and Automation acceptance plan

All cases below are NOT RUN. They require the integrated topology and authorized
maintenance, not just the M2 lightweight lab. Offline QA does not change these statuses.
Use sanitized evidence with timestamp, hostname, show version and configuration identity.
Keep raw running-config/credentials/PSKs private. Use only approved test endpoint IPs;
allocate no new addresses merely to match this plan.

## Order and cases

| ID | Stage | Procedure | Expected observation | Status |
|---|---|---|---|---|
| R01 | Base integration | Check show version/interfaces, VLANs/trunks, Po1, HSRP and STP before any M3 fragment | Mapping matches Schema; healthy base with backups and console fallback | NOT RUN |
| R02 | Routing/server | Show IPv4/IPv6 routes in both directions between controller .100, remote V99, relay LANs and .50; DHCP/DNS/NTP service probes | Correct forward/return private routes over tunnels, transport via ISP; actual services respond | NOT RUN |
| R03 | SSH bootstrap | Console runbook, public-key verification and fresh controller SSH | Expected hostname, working privilege and pinned key; no account/key replacement | NOT RUN |
| R04 | NAT | Apply one router fragment at a time after object/route checks; real inside client reaches ISP synthetic endpoint, compare translations/counters | Only approved local sources PAT; return traffic works; router-originated ping alone is insufficient | NOT RUN |
| R05 | VPN preservation | Generate intersite client traffic, record route, NAT table, ESP counters before/after and physical capture | Private inner sources unchanged; both encrypt/decrypt counters increase; no private/plain GRE leak | NOT RUN |
| R06 | Guest IPv4 | DORA, renewal and rebinding; public DNS UDP/TCP; negative probes to corporate, .50 non-DHCP, V99, Lo0, WAN and tunnels | DHCP succeeds; approved public service works; forbidden targets fail with correct ACL hits | NOT RUN |
| R07 | Guest IPv6 | SLAAC/DAD, NS/NA/RS and RA return; public IPv6 probe, PMTUD; negative corporate/management/overlay and rogue RA/redirect tests | ND works; no IPv6 isolation bypass; no internal service opened; inspect actual parser/counters | NOT RUN |
| R08 | Snooping/PortSec | Apply access-switch fragment; renew wired and AP clients, try controlled rogue DHCP/unexpected MAC; inspect Po1 | Legitimate leases continue; rogue DHCP dropped; restrict counter increments without unexpected port shutdown | NOT RUN |
| R09 | Conditional DAI | First inventory local DHCP bindings/static exceptions and trust; activate only eligible VLAN20; forged ARP and lease/reboot recovery | Valid ARP passes, forged ARP dropped; all legitimate hosts recover after binding loss | NOT RUN |
| R10 | Conditional VTY | Prove .100 route/account/keys first, choose real line range, apply from console, test a NEW SSH session | Controller allowed, unauthorized sources refused, console recovery works; IPv6 SSH closed pending source assignment | NOT RUN |
| R11 | Step9 | Plan, audit/review and explicit single-device apply, post-state, new audit and no-op rerun; controlled auth/timeout/failure scenarios | Complete backups, honest error status, hostname/stale-plan guards, no protected changes; no extra commands on compliant run | NOT RUN |
| R12 | Regression/persistence | Approved single-link HSRP/STP/LACP failover, restore, test management/DHCP/Security; manual save and one controlled restart | Same security after path change; config persists; measured recovery reported without general WAN-failover claim | NOT RUN |

## Cisco observation commands

Run at relevant nodes, privately where output can contain secrets:

```text
show ip interface brief
show ipv6 interface brief
show interfaces trunk
show etherchannel summary
show spanning-tree vlan 10,20,99
show standby brief
show ip ospf neighbor
show ipv6 ospf neighbor
show ip route 192.168.1.100
show ip route 192.168.2.10
show ip route 192.168.3.10
show ip route 10.10.10.50
show ip route 203.0.113.5
show ip route 203.0.113.9
show ipv6 route
show ip bgp summary
show crypto isakmp sa
show crypto ipsec sa
show ip nat statistics
show ip nat translations
show access-lists M3_NAT_INTERNET
show access-lists M3_GUEST4_IN
show ipv6 access-list M3_GUEST6_IN
show ip dhcp snooping
show ip dhcp snooping binding
show ip dhcp snooping statistics
show ip arp inspection
show ip arp inspection interfaces
show ip arp inspection statistics
show port-security
show port-security interface GigabitEthernet1/0
show ip ssh
show line
show ntp associations
show policy-map interface Tunnel12
show policy-map interface Tunnel13
```

Use the site's actual VLAN set for STP commands. On HQ, WAN tunnel destinations .5/.9
must resolve via physical ISP, never into their own tunnel. On branches verify route
to HQ WAN .1 and return route to controller. Check IPv6 routes to each exact management
address from Schema; do not infer IPv6 from IPv4 success.

Record NAT/ACL/ESP counter DELTAS around actual client traffic, not only tunnel UP/UP.
Synthetic 8.8.8.8 ping is not a DNS query and not real Internet verification. DNS
requires a running responder. Guest DHCP is permitted but Guest ICMP/DNS/NTP to .50
is intentionally blocked pending policy. Option82 is not inserted by M3; confirm
packet/server observations before changing that setting.

DAI R09 cannot run for unsafe VLAN10/50/30/99 until pending data is resolved.
Check DAI rate defaults with legitimate ARP traffic; do not increase limits blindly.
Sticky MAC persistence is a manual save decision; document legitimate VM/device moves.
Router ingress ACL cannot prevent same-L2 Guest-to-Guest or Finance-to-server traffic.

For R11 use the exact Windows commands in [Step9 README](../../Automation/README_STEP9.md).
Never claim QoS priority without marked traffic and congestion evidence from M2.
