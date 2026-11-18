# Security policy and approval matrix

Contract inputs: [Schema](../../Specs/IP_Addressing_Schema.md),
[current topology](../../Specs/TVI_Network_Topology.drawio),
[M1 DHCP alternatives](../member1_switching_dhcp/dhcp_server/dnsmasq.conf).
Executable, conditional and non-executable policies are different artifact classes.
Step9 never ingests any of them; it provisions only its own allowlisted baseline.

| ID | Requirement/source | Attachment | Implementation/status | Decision still required |
|---|---|---|---|---|
| G4 | Guest Internet-only, DHCP central, public DNS in M1 pools | Hanoi Gi0/1.50 IN | devices/HANOI-RND-RTR01_step7.cfg; IMPLEMENTED + OFFLINE TESTED | IOS parser, DORA/renew, routing and actual DNS service runtime |
| G6 | Same isolation for dual-stack Guest | Same interface, IPv6 IN | Bounded ND/RS/DAD, no corporate/management/overlay/underlay access; IMPLEMENTED + OFFLINE TESTED | Actual SLAAC/PMTUD; no invented DHCPv6 or internal DNS endpoint |
| NAT | Per-site local Internet PAT without private VPN translation | Router Gi0/0 outside; inside per README | Exact local sources and ordered destination exemptions; IMPLEMENTED + OFFLINE TESTED | Routes, private source preservation, IOS packet order and ESP counters |
| FIN | Protect Finance, containing shared service server .50 | Proposed DIST01/02 Vlan10 OUT, identical policies | proposals/corporate_acl.cfg.disabled; BLOCKED BY EXTERNAL DEPENDENCY | Approved initiators/ports for engineers, logistics, admins; service exceptions and return traffic |
| ENG-HQ | Engineering restrictions | Proposed BOTH DIST Vlan20 IN | Comment-only proposal; BLOCKED BY EXTERNAL DEPENDENCY | Finance/server/IoT/Internet permissions, not a blanket deny |
| ENG-HN | Engineering restrictions | Proposed Hanoi Gi0/1.20 IN | Comment-only proposal; BLOCKED BY EXTERNAL DEPENDENCY | Same business matrix, IPv4/IPv6 and return traffic |
| IOT | Logistics/IoT restrictions | Proposed Da Nang Gi0/1.30 IN | Comment-only proposal; BLOCKED BY EXTERNAL DEPENDENCY | Required application server addresses/ports, DNS/NTP and admin access |
| MGMT-NET | Protect Management networks | Proposed DIST Vlan99 OUT, branch Gi0/1.99 OUT | Comment-only proposal; BLOCKED BY EXTERNAL DEPENDENCY | Complete admin/application source matrix and service needs |
| MGMT-VTY | Approved controller is 192.168.1.100, topology node hq_vlan99_zone | All actual VTY lines on nine devices | conditional range variants; IMPLEMENTED BUT UNVERIFIED | Two-way .100 routing, local login/AAA compatibility, real line range; other admins and IPv6 source assignments |
| L2 | Snooping/Port Security on access switches | README trust table | devices/ files; IMPLEMENTED + OFFLINE TESTED | Legitimate MAC count, parser, lease/Po1 regression |
| DAI20 | DHCP-engineering clients with established bindings | HQ CORE/Hanoi switches VLAN20 | conditional/*_dai_vlan20.cfg; IMPLEMENTED BUT UNVERIFIED | Observe every local binding/static exception and reboot recovery before activation |
| DAI-STATIC | Server/AP/IoT static endpoints unknown | VLAN10/50/30, no activation | proposals/dai_pending.cfg.disabled; BLOCKED BY EXTERNAL DEPENDENCY | Exact MAC/IP/port inventory; server-port trust vs ARP ACL approval |
| DAI99 | Static management hosts | No attachment | BLOCKED BY EXTERNAL DEPENDENCY | Full static-management strategy; never enable DAI99 now |
| AUTH | Preserve existing users, enable secrets, keys and AAA | Console runbook; conditional VTY | IMPLEMENTED BUT UNVERIFIED | Approved router local accounts, existing AAA policy and public-key enrollment |
| EXTRA | AAA/Syslog/banner wording | Step9 opt-in config | Banner supported but disabled; AAA/Syslog BLOCKED BY EXTERNAL DEPENDENCY | Exact banner text, AAA method list and fallback; Syslog endpoint/transport; none inferred from .50 |

DHCP exception permits only UDP68->67 Guest renewal/bootstrap. It does not permit
DNS, NTP, SSH, BGP, IKE or general IP to a private endpoint. Guest public DNS is
8.8.8.8 per both source DHCP pools, but ISP's loopback alone provides no DNS service.
M1 dnsmasq advertises .50 NTP globally; the IOS Guest pool does not contain that option.
Leader must reconcile the Guest NTP service decision; isolation stays closed meanwhile.

Corporate policies must account for authorized DHCP relay UDP67->67 (including relay
interface source addresses), DNS UDP/TCP53, NTP UDP123, SSH TCP22, ICMP/ICMPv6 errors
and return flows. If filtering routed links, preserve OSPF, HSRP, BGP, IKE/ESP and
GRE as appropriate to that location. These are design checks, not indiscriminate
Guest permits. Do not filter inter-VLAN Finance solely on EDGE: DIST routes locally.
Same-VLAN Finance/server traffic requires an additional design if isolation is intended.
