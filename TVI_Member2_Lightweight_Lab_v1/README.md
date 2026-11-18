# TVI / Member 2: 6-node lightweight EVE-NG lab

**Status: PRE-BOOT, NOT VERIFIED.** No packet was run through real Cisco IOSv or IOSvL2 here. Never call it PASS before observing EVE-NG CLI output.

## Purpose and boundary
Test **Step 5 OSPFv2/v3**, **Step 6 eBGP + GRE/IPsec**, **Step 8 QoS EF/AF31** with 6 nodes, 5 physical wires. Independent of Member 1's HSRP/LACP/VLAN and Member 3's ACL/NAT. No DHCP server, PC, branch VLANs, production credentials or real public Internet in this mini-lab. This is NOT the full Assignment-2 topology.

Cisco image versions **inferred from file names/previous logs**, not independently verified: IOSv Router `15.9(3)M3`, IOSvL2 `15.2(4.0.55)E`. Check with `show version`.

EVE-NG Freemium 7.4.0-2 currently permits **7 running nodes**; the lab has 6 (4 vIOS routers and 2 IOSvL2 switches). This leaves only one slot for a network test VM unless VPCS exception applies. Resource capacity still matters.

## Physical construction (exact group contract)

| Link | From | To | Network |
|---|---|---|---|
| L1 | ISP `Gi0/0` | HQ `Gi0/0` | 203.0.113.0/30 |
| L2 | ISP `Gi0/1` | Hanoi `Gi0/0` | 203.0.113.4/30 |
| L3 | ISP `Gi0/2` | Da Nang `Gi0/0` | 203.0.113.8/30 |
| L4 | HQ `Gi0/1` | DIST01 `Gi0/1` | 10.10.254.0/30 |
| L5 | HQ `Gi0/2` | DIST02 `Gi0/1` | 10.10.254.4/30 |

No physical wire for Tunnel12 or Tunnel13! They are logical GRE interfaces routed *over ISP*. See `docs/topology.mmd`.

**Critical EVE setup:** reserve enough interfaces: ISP and HQ need >=3 data interfaces exposed as `Gi0/0..Gi0/2`; DIST switches need `Gi0/1`. Verify node adapter count and CLI mapping; Cisco switch images may expose `Gi0/0` as management. `show ip interface brief` and `show interfaces description` take precedence over GUI assumptions.

## Cisco image deployment (use authorized images only)

- Router QEMU folder: `vios-Router-1593M3` (prefix `vios-`), disk file must be a real QCOW2 named `virtioa.qcow2`.
- Switch QEMU folder: `viosl2-Switch-1524` (prefix `viosl2-`), disk must be actual QCOW2. The supplied switch image originally looked like VMDK *despite the .qcow2 extension*; use a verified converted image, not a renamed VMDK.
- After SFTP upload, from EVE shell: `/opt/unetlab/wrappers/unl_wrapper -a fixpermissions`. (Check installation-specific path before use.)
- EVE-NG VM itself requires functioning KVM: `ls -l /dev/kvm` and QEMU node successful boot.

## Stage-by-stage execution (DON'T mass-paste all files)

**For each Cisco node:** open console, `enable`, `terminal length 0`, `show version`, `show ip interface brief`, `show ipv6 interface brief`, `show running-config | include hostname`. Verify interface names and no existing conflicting config. Back up before modifications. In global config mode `configure terminal`, paste *the contents* of that node's file, then `end` and run test commands. You can paste file contents in the EVE HTML5 console; automation transfer is not included in this package.

1. **Stage `00_base`** — all six nodes. Wire and test HQ OSPF: HQ ↔ DIST01/DIST02 should show `FULL`, IPv4/IPv6 loopback reachability. WAN peer links ping directly. See `tests/TEST_PLAN.md` T01–T04.
2. **Stage `10_ebgp`** — four routers only. ISP advertises **only WAN transport /30s and synthetic 8.8.8.8** to branches, **not private corporate networks**. Check eBGP Established and routes to remote WAN tunnel endpoints. T05–T06.
3. **Stage `20_gre_ospf`** — HQ, Hanoi, Da Nang. The tunnel is **not encrypted yet**. Only generate dummy lab pings; this diagnostic interval must not carry real data. OSPF IPv4/IPv6 across Tunnel12/13; verify routes to `10.255.255.2`, `.3` and HQ `.11`, `.12` use Tunnel, not ISP. T07–T09.
4. **Stage `21_ipsec`** — HQ, Hanoi, Da Nang. First **manually configure equal PSKs on both peers**, then apply IPsec config (crypto map) from file. See `docs/IPSEC_KEY_SETUP.md`; NEVER store PSKs in Git. Generate pings; require ESP encrypt AND decrypt counters increment. T10–T11.
5. **Stage `30_qos`** — HQ/Hanoi/Da Nang. **Experimental**: IOSv may reject tunnel policy or not prioritize in data plane; a parser-accepted policy and counters only show classification, **not LLQ under congestion**. Verify IOS CLI compatibility and packet counters, then test contention separately if feasible. T12–T13.
6. Save proven configs: `copy running-config startup-config` on each device; export configs and capture screenshots after reboot. T14–T15. Backups containing IKE keys must be protected/redacted before sharing.

## Meaningful results expected
- OSPF HQ FULL on two peers; OSPF branch adjacencies FULL on two GRE tunnels.
- Exactly 3 eBGP IPv4 peers established (ISP facing HQ/Hanoi/Da Nang); 3 IPv6 peers optional to validate as a separate test.
- ISP route table must NOT be used as the transit path for private `10.10/16`, `10.20/16`, `10.30/16` networks; those belong across encrypted overlay for real traffic.
- ESP counters prove data plane IPsec, not tunnel line protocol alone.
- QoS EF/AF31 policy binds and counts are *preliminary*; meaningful VoIP priority requires load + queue metrics.

## Differences from full group project — intentional
- No access-port `Fa0/1..Fa0/24` which conflict with IOSvL2 (Cisco documents only GigabitEthernet). We do **not** silently edit the immutable IP Schema.
- No HSRP, LACP, DHCP relay, Guest ACL, PAT, WLC, EVPN-VXLAN, real server, large topology, BGP supernet origination or site LAN VLANs. They require integration with Members 1/3/4 and the full lab. Some full rubric items remain untested in this mini-lab.
- Loopbacks are the traffic endpoints; they do not replace representative LAN clients.
- `203.0.113.0/24` and `2001:DB8::/32` are documentation prefixes and are used only within the isolated lab. `8.8.8.8` is **a locally simulated loopback** at ISP, not actual Google DNS.

Check `CONCERN_REPORT.md` before demo; see `tests/TEST_PLAN.md` for objective evidence checklist. The deliverable is a **test harness**, not proof of success.
