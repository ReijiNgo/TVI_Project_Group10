# Member 3 external dependencies

These items block the indicated runtime/policy portions, not offline development.

| Priority | Owner | Exact handover | Blocked portion | Already known; do not request again |
|---|---|---|---|---|
| P0 | Leader | Finance/Engineering/IoT/Management source-destination-service matrix, initiator/return flow and IPv4/IPv6 approval | Corporate ACL activation | VLANs, SVIs, prefixes and candidate attachment directions are already documented |
| P0 | M2 + Leader | Integrated OSPFv2 process1/OSPFv3 process10 campus/Management advertisements and approved Internet/synthetic endpoint route strategy; two-way show route evidence | SSH, central DHCP, NAT and cross-site tests | Existing WAN peers, ASNs, Lo0 and Tunnel12/13 mappings remain unchanged |
| P0 | M1 | Actual .50 server backend, server default route, DHCP/DNS/NTP service status and Option82 acceptance requirements | Service and Snooping runtime acceptance | Server IPv4 .50, HQ CORE Gi0/0 and helper locations are known |
| P0 | M1/Leader | Static server/AP/IoT MAC-IP-port inventory or binding proof; approval for server DAI trust vs static ARP ACL | DAI10/50/30/99 | No fake MAC/binding was created; DAI99 is excluded |
| P0 | M1/M3 + Leader | Approved router local-login bootstrap, current AAA compatibility, actual VTY ranges and verified .100 access | Conditional VTY/SSH activation without lockout | Controller 192.168.1.100 on CORE Gi1/3 is already in Draw.io; existing M1 accounts are not replaced |
| P1 | M2 + Leader | Resolve Report SHA256/profile vs M2 SHA/crypto-map discrepancy; real image/parser and bidirectional ESP deltas | VPN confidentiality acceptance | M3 preserves current M2 selectors/maps/keys |
| P1 | M1 | AP client MAC fan-out, all static IoT endpoints and real Po1 trust/binding behavior; DAI reboot recovery evidence | AP PortSec and conditional DAI | Ordinary wired client max2/restrict is implemented; AP/server/controller excluded |
| P1 | Leader | Full lab export/console access, image versions, capacity for required nodes and clients | All runtime verification | No EVE connection was initiated; M2 mini-lab excludes M3 client/server topology |
| P1 | Leader | Banner wording approval, Syslog endpoint+transport, optional AAA method-list/fallback, additional admin IPv4/IPv6 sources and IPv6 service addresses | Optional baseline features and broader management access | .50 is not assumed Syslog/AAA; IPv6 admin address is not invented |
| P2 | M1 | DIST unused-port BLACKHOLE/shutdown source completion and prior HSRP/LACP/DHCP/IPv6/SSH evidence | Full regression and submission | M1 source is protected, unchanged |
| P2 | Leader | Integrated Configurations/ build and synchronized topology PNG/report/evidence | Final submission | Ten startup placeholders and Report were intentionally not edited |

Historical Step9 source was not found in local reachable Git history before this
implementation. The new source is self-contained; recovery of an old archive is no
longer required for these offline functions. No literal credential from M1 was copied.
Guest NTP to .50 is unresolved: M1 dnsmasq advertises it globally while Guest policy
allows only approved exceptions. Keep private NTP closed until Leader resolves this.

IPv6 Internet/synthetic public breakout also requires an approved ISP return route
for actual Guest/corporate IPv6 source prefixes. Current transport-only BGP does not
advertise those site prefixes. M2/Leader must decide the route policy; NAT66 is not
an acceptable invented workaround. Public IPv6 connectivity is NOT claimed here.
