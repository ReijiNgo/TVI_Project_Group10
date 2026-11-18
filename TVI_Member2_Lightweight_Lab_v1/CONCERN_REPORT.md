# CONCERN REPORT — TVI Member 2 lightweight lab

**Version:** 1.0 / 2026-11-18. **Scope:** 6 nodes; OSPFv2/v3, eBGP, GRE over IPsec, QoS. **State:** risk assessment, NOT device test results. Exactly 10 risks, ordered from easy-to-detect installation errors to hidden D-day dangers.

## Risk dashboard

| # | Risk / failure mode | Likelihood (estimate) | Demo impact | Priority | Fast diagnostic |
|---|---|---|---|---|---|
| R01 | Downloaded `.run` upgrade instead of `.iso` installer | High (already observed) | Cannot install fresh EVE VM | P2 | Check file extension, SHA256 |
| R02 | Windows VT-x enabled but VMware nested KVM unavailable | Medium | Cisco nodes refuse to boot or crawl | P0 | `ls -l /dev/kvm`, boot 1 IOSv |
| R03 | vIOSL2 VMDK mislabeled QCOW2 / image incompatible | High (prior conversion needed) | Switch boot loop/crash | P0 | `qemu-img info`, `show version` |
| R04 | Port labels/adapter count mismatch group contract | High | Wrong physical cabling; OSPF down | P0 | `show ip interface brief`, port-map review |
| R05 | EVE-NG 7.4 Freemium 7-node running limit | Certain if full 10-node lab | Full topology cannot start concurrently | P0 D-day | Node cap on UI; count running nodes |
| R06 | IOSvL2 Layer 3/OSPFv3 parser or routed port unusable | Medium | Step 5 IPv4/IPv6 incomplete | P1 | `no switchport`, `show ip ospf neighbor` |
| R07 | BGP Established, but WAN routing/recursive GRE path wrong | Medium | Tunnel and OSPF flap / drop | P0 | `show ip route <remote-wan-ip>` |
| R08 | GRE tunnel UP, but IPsec not encrypting / route leak exposes internal data | Medium–High | Security false PASS; Step 6 failure | P0 Critical | ESP counters and packet capture |
| R09 | QoS policy accepted but voice not actually prioritized | High (IOSv uncertain) | Step 8 demo looks good but is invalid | P0 Critical | EF/AF31 counters + congestion metrics |
| R10 | Day-of-demo integration/startup drift, unsaved or conflicting configs | Medium–High | Full demo cannot reproduce results | P0 D-day | Clean restart rehearsal + evidence bundle |

**P0** means block production-like claims and resolve before the relevant final demo. Probabilities are engineering estimates, not observed failure rates.

---

## Detailed failure analysis — from EZ to hidden/dangerous

### R01 — Wrong installer (`.run` instead of `.iso`)
- **Root cause:** EVE's `Full ISO` and `Upgrade .run` links are adjacent; Windows calls both downloadable packages.
- **What you see:** VMware boot wizard cannot use `.run` as a bootable CD/DVD.
- **Detection:** File extension shown explicitly in Explorer; validate Full ISO SHA256 from vendor page.
- **Fix:** Download `Full ISO`, attach `.iso` to new VM. Never rename `.run` to `.iso`.
- **D-day gate:** EVE OS is actually installed, not just downloaded.

### R02 — VT-x enabled on Windows ≠ nested virtualization passed to VMware
- **Root cause:** The physical host exposes virtualization to Windows, but VMware hasn't exposed EPT/RVI to the EVE guest (or a host hypervisor blocks it).
- **What you see:** EVE Web UI works but IOSv nodes fail to start, or boot times are unworkable.
- **Detection:** EVE SSH `ls -l /dev/kvm`; in VMware check *Virtualize Intel VT-x/EPT or AMD-V/RVI*; actually boot 1 Router.
- **Fix:** Confirm hardware permissions with machine owner, correct nested-virtualization setting; use compatible host/platform if impossible. Do not indiscriminately disable machine security controls.
- **D-day gate:** Router and switch complete boot and CLI responds without repeated crashes.

### R03 — Cisco disk image extension lies about the format
- **Root cause:** `viosl2-Switch-1524/virtioa.qcow2` in original user ZIP was observed to be VMDK content. Renaming cannot convert it.
- **What you see:** QEMU 'invalid format', frozen boot, unexpected kernel exception or repeated Cisco restart.
- **Detection:** `qemu-img info <file>` should show actual `file format: qcow2`; check with `qemu-img check`; boot with EVE KVM, then `show version`.
- **Fix:** Convert offline with `qemu-img convert -f vmdk -O qcow2 old-file new-file`; upload resulting QCOW2 and run permission fix. Use only legitimately obtained images.
- **D-day gate:** All 6 nodes open CLI reliably; keep golden converted image with checksum.

### R04 — Physical interface mapping inconsistent
- **Root cause:** Group contract uses `Fa0/1..Fa0/24` for access devices, but Cisco IOSvL2 has GigabitEthernet interfaces (Cisco docs: up to 16). EVE template adapter count may not expose required Gi0/2 or Gi0/4.
- **What you see:** `% Invalid interface`, target interface missing or OSPF peers don't see each other despite green wires.
- **Detection:** Compare `show ip interface brief` to `docs/physical_links.csv`; inspect EVE node interface dropdown **before adding wires**.
- **Fix:** This 6-node lab ONLY uses Gi0/1 on DIST, leaves Access mapping untouched. For full integration obtain leader-approved port-map contract revision; do not silently change VLAN trunk wiring.
- **D-day gate:** Export approved physical link table + screenshot of topology labels.

### R05 — Freemium node-count dead end
- **Root cause:** EVE-NG 7.4 Freemium limits simultaneous QEMU nodes to 7; full TVI baseline is 10 network devices + endpoints.
- **What you see:** Full topology exists on canvas but can't start all required routers/switches; failover and end-to-end demo can't be shown.
- **Detection:** Count *running* nodes and check vendor EVE edition limit.
- **Fix:** Use this **6-node** lab only for Member 2; conduct integrated demo using licensed EVE, GNS3 or adequately provisioned CML. Do not bypass license checks.
- **D-day gate:** Final demo platform can run all essential nodes simultaneously during a full rehearsal.

### R06 — L3 switch / OSPFv3 compatibility surprise
- **Root cause:** EVE release does not determine actual IOSvL2 feature parser; IOSvL2 routed ports, IPv6 routing and OSPFv3 may vary by build.
- **What you see:** `ip routing`, `no switchport`, `ipv6 ospf 10 area 0` rejected, or neighbor remains DOWN/INIT/EXSTART.
- **Detection:** `show version`, parser `?` help, `show ip ospf interface brief`, `show ipv6 ospf neighbor`, interface counters and masks.
- **Fix:** Verify DIST `Gi0/1` L3 routed mode and matching link subnet; adjust syntax only after confirming IOS release; separate IPv4 and IPv6 evidence.
- **D-day gate:** HQ two OSPFv2 neighbors FULL **and** OSPFv3 neighbors proven, not assumed.

### R07 — BGP looks healthy, tunnels still fail (or route recursively)
- **Root cause:** Peering ISP only proves neighbor reachability. GRE destination `203.0.113.5`/`.9` must resolve via physical ISP WAN route. A leaked private prefix or OSPF recursive next-hop can route tunnel destination *into its own tunnel*.
- **What you see:** `show ip bgp summary` Established, but `Tunnel12`/`13` line protocol flaps; OSPF routes disappear intermittently.
- **Detection:** On HQ `show ip route 203.0.113.5`, `.9`; remote edge route to `.1`; route next-hop must point **physical Gi0/0 and ISP**, never Tunnel.
- **Fix:** This mini-lab BGP permits only WAN transport prefixes and a synthetic ISP loopback; no BGP origin of site-private `10.x` prefixes. Keep tunnel and transport separated.
- **D-day gate:** WAN routes use ISP; site-loopback routes use GRE tunnel; repeated test stable.

### R08 — Tunnel UP/UP is not proof of IPsec confidentiality
- **Root cause:** GRE can run unencrypted. PSK mismatch, IKE proposal mismatch, incorrect interesting-traffic ACL or wrong crypto map attachment means ESP encryption never occurs. Mixing NAT and BGP may create a separate plaintext path.
- **What you see:** Tunnel ping succeeds, but `show crypto ipsec sa` counters are stuck at zero or ESP associations absent; raw GRE might be seen on physical WAN capture.
- **Detection:** Compare encaps/decaps *before and after real routed traffic*. Capture physical Gi0/0 where possible: ESP/IKE expected, not exposed GRE. Check `show crypto isakmp sa`.
- **Fix:** Match IKE/transform configuration and peer PSKs; crypto ACL matches GRE physical source/destination; map applied to Gi0/0; prevent site-private traffic propagation over ISP; coordinate NAT exemption with Member 3 at integration.
- **D-day gate:** Encrypt/decrypt BOTH directions actually increment; no claim of secure VPN based on tunnel UP alone.

### R09 — QoS "PASS" is a false positive on IOSv
- **Root cause:** Cisco documents IOSv QoS as not officially verified/supported. ESP may alter classification visibility; service-policy on Tunnel can be rejected or work without real priority scheduling. No congestion means LLQ cannot demonstrate benefit.
- **What you see:** Policy exists but no EF/AF31 hits; or counters rise while voice suffers just as much as bulk traffic.
- **Detection:** `show policy-map interface Tunnel12/13`, send **DSCP EF/AF31-marked** traffic, verify separate counters, then create controlled congestion and compare voice jitter/loss/latency if the image supports shaping/queues.
- **Fix:** Isolate QoS stage; test `qos pre-classify` / alternate physical-WAN policy *only after* parser/feature audit. If supported data-plane proof is impossible, document limitation and seek alternate approved image/platform; never fake successful QoS.
- **D-day gate:** QoS classification and congestion evidence captured. Accept only PARTIAL if no congestion proof.

### R10 — Rehearsal works, D-day integration does not
- **Root cause:** Member 1's HSRP/LACP/SVI and Member 3's NAT/ACL modify routes/interfaces; Member 2's standalone configs later overwrite those changes. Running-config not saved; VM/IP addresses change; console/snapshots contain secrets.
- **What you see:** Demo reboot loses settings, full topology OSPF neighbors disappear, crypto PSKs don't match, DHCP guest ACL blocks expected traffic or EVE does not start all nodes.
- **Detection:** Golden image checksums, `show startup-config`, all-router `show` after controlled reboot, full topology cold-start rehearsal, time-boxed 15-minute runbook, explicit member handoff diff.
- **Fix:** Merge **per-feature configuration blocks**, not whole device config from separate modules; review immutable IP Schema changes with leader; back up redacted configs, preserve `.unl` lab, verify platform capacity. Prepare short fallback demonstration evidence if live node fails (but don't present saved screenshots as live PASS).
- **D-day gate:** Clean start to evidence in a full rehearsal, configs persisted, no raw secrets shared, and all owners sign off.

---

## GO / NO-GO checklist for Member 2 demo

1. **GO for Step 5** only if HQ OSPFv2/v3 neighbors and reachability have CLI captures.
2. **GO for BGP** only if 3 eBGP sessions Established and remote **WAN** endpoints route via ISP.
3. **GO for VPN** only if Tunnel12/13 have OSPF adjacencies **and ESP counters rising**.
4. **GO for QoS claims** only if EF/AF31 classes have counted flows; claims about *priority under congestion* require observed congestion comparison.
5. **GO for D-day** only if all needed nodes start simultaneously on chosen platform and startup configs survive a controlled restart.

## Evidence to collect and owners

| Priority | Owner | Must capture |
|---|---|---|
| P0 | Member 2 | `show version` of Router/Switch; `show ip interface brief`; `show ip ospf neighbor` + IPv6 equivalent |
| P0 | Member 2 | `show ip bgp summary`, `show ip route` to WAN destinations and private loopbacks |
| P0 | Member 2 | before/after ESP counters on both endpoints; `show policy-map interface` + marked traffic |
| P0 | Leader/Member 4 | Final topology capacity, integration build, reboot demo rehearsal |
| P1 | Member 1 | HSRP/Link aggregation changes don't overwrite HQ routed `Gi0/1`, `Gi0/2` |
| P1 | Member 3 | NAT/ACL excludes protected site-to-site traffic, permits IKE/ESP/GRE as needed |

## Sources and assumptions

Project-sourced: assignment PDF, `TVI_Project_Group10-main.zip`, `Specs/IP_Addressing_Schema.md`, prior E2E draft. No group files were modified. Exact model/image features need boot confirmation.

Vendor checks (at time of drafting):
- EVE 7.4 Freemium node limit: https://www.eve-ng.net/index.php/features-compare/
- IOSv 2.6 feature list (IPSec supported; QoS not officially tested): https://developer.cisco.com/docs/modeling-labs/2-6/iosv/
- IOSvL2: up to 16 GigabitEthernet interfaces: https://developer.cisco.com/docs/modeling-labs/2-6/iosvl2/
- EVE download/release notes: https://www.eve-ng.net/index.php/download/

**Not proven here:** image actual support, real ESP data plane, real LLQ under congestion, failover, full-network integration, public Internet connectivity. No fake `PASS` results have been generated.
