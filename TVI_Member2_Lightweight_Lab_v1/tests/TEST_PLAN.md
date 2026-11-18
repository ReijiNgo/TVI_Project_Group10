# Member 2 acceptance tests — capture observed PASS/FAIL, never infer

For evidence create `evidence/Txx_<node>_<yyyymmdd>.png` or `.txt`; do not include PSKs. Every test starts as NOT RUN.

| ID | Stage | Node and command | PASS condition | Status |
|---|---|---|---|---|
| T01 | 00 | All: `show version`, `show ip interface brief`, `show ipv6 interface brief` | Correct images + Gi names, WAN+HQ links up/up | NOT RUN |
| T02 | 00 | HQ: `show ip ospf neighbor` | DIST01 `.11` and DIST02 `.12` FULL | NOT RUN |
| T03 | 00 | DIST01/02: `show ip route ospf`; source ping to other switch loopback | Reach peer via HQ OSPF | NOT RUN |
| T04 | 00 | HQ: `show ipv6 ospf neighbor`; IPv6 pings to loopback `2001:DB8:10:FFFF::11` & `::12` | OSPFv3 FULL and IPv6 reachability | NOT RUN |
| T05 | 10 | ISP: `show ip bgp summary`; edge peers too | 3 eBGP sessions Established; prefix count not state Idle/Active | NOT RUN |
| T06 | 10 | HQ: `show ip route 203.0.113.5`, `show ip route 203.0.113.9`; Hanoi: route `203.0.113.1`; pings | All remote WAN peer IPs reachable **via ISP** before GRE | NOT RUN |
| T07 | 20 | HQ: `show interfaces Tunnel12`, `show interfaces Tunnel13`; `show ip ospf neighbor` | Tunnel up/up and branch adjacencies FULL | NOT RUN |
| T08 | 20 | HQ: `show ip route 10.255.255.2`, `show ip route 10.255.255.3`; sourced loopback pings | Branch Loopback IPv4 routes via Tunnel12/13 | NOT RUN |
| T09 | 20 | HQ: `show ipv6 ospf neighbor`; `show ipv6 route ospf` | OSPFv3 tunnel adjacency and remote IPv6 loopbacks | NOT RUN |
| T10 | 21 | HQ and branches: `show crypto isakmp sa`, `show crypto ipsec sa` before pings | IKE established (e.g. QM_IDLE for IKEv1), IPsec SAs exist | NOT RUN |
| T11 | 21 | 20+ sourced pings to remote *loopbacks*, `show crypto ipsec sa` before/after | Both encaps/decaps rise on HQ and peer; no plaintext GRE seen if capture is available | NOT RUN |
| T12 | 30 | Router: `show policy-map interface Tunnel12` and Tunnel13 | Policy accepted; voice/video class present; test flows hit expected counters | NOT RUN |
| T13 | 30 | Extended ping / source loopback, `Type of service` 184 (EF) and 104 (AF31) separately | Separate class counters rise; this is NOT proof of lower latency under congestion | NOT RUN |
| T14 | end | All: `copy running-config startup-config`, then controlled reboot of *one* node | Config persists and routing reconverges; avoid rebooting entire topology at once | NOT RUN |
| T15 | end | Change one HQ OSPF link by shutting **one** routed interface; restore after | Other HQ distribution OSPF path still works; no claim of general WAN failover | NOT RUN |

## Short D-day CLI sequence

At HQ:
```
show ip interface brief
show ip ospf neighbor
show ipv6 ospf neighbor
show ip bgp summary
show ip route 10.255.255.2
show ip route 10.255.255.3
show interface Tunnel12
show interface Tunnel13
show crypto isakmp sa
show crypto ipsec sa
show policy-map interface Tunnel12
show policy-map interface Tunnel13
```

At ISP:
```
show ip bgp summary
show ip bgp
```

At Hanoi and Da Nang:
```
show ip ospf neighbor
show ip route ospf
show crypto ipsec sa
show policy-map interface
```

## DSCP traffic demonstration (CLI-dependent)

Cisco interactive extended ping example from HQ:
```
ping
Protocol [ip]:
Target IP address: 10.255.255.2
Repeat count [5]: 50
Datagram size [100]: 200
Timeout in seconds [2]:
Extended commands [n]: y
Source address or interface: Loopback0
Type of service [0]: 184
... accept defaults
```
Run again with Type of service 104. `184 = EF (46 << 2)`, `104 = AF31 (26 << 2)`. Check `show policy-map interface Tunnel12` counter deltas. If the parser/QoS tunnel policy rejects it or packets go to default class, record FAIL and switch to a supported test approach. A proper Step-8 QoS rubric proof additionally needs congestion test and preferably latency/loss measurement.

## Safe shutdown restoration for T15

**Never shutdown both HQ distribution uplinks at once.** Under maintenance permission, on HQ:
```
configure terminal
interface GigabitEthernet0/1
 shutdown
end
```
Observe impact, then:
```
configure terminal
interface GigabitEthernet0/1
 no shutdown
end
```
A single-link failover test is not proof of full site failover; record what remained reachable and what went offline.
