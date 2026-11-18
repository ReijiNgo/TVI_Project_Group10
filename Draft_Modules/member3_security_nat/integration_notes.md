# Zero-conflict integration notes

M1/M2 source, Schema, Draw.io, Report and all final startup-config placeholders are
protected by tests/protected_manifest.json hashes captured before implementation.
No IP, hostname, access membership, native999, allowed VLAN, STP, Po1, HSRP, routing,
tunnel or crypto-map change is present in M3 fragments. Deployment is MANUAL and
must be reviewed; Step9 cannot send these files.

## Specific upstream proposals (not applied)

1. M2: advertise actual HQ Vlan10/20/99 from BOTH DIST in OSPFv2 process1 and OSPFv3
   process10, passive on user SVIs. Add Hanoi .20/.50/.99 and Da Nang .30/.99 actual
   LAN prefixes to the overlay while keeping adjacency only on approved transit links.
   Do not redistribute arbitrary connected/ISP/private routes just to make a test pass.
2. M2/Leader: decide route toward synthetic 8.8.8.8/32 from HQ campus (not only EDGE).
   Existing BGP underlay advertises transport and synthetic loopbacks, not a general
   default. Preserve forward/return paths between HQ .100, remote V99 and server .50.
   No NAT fragment can create these missing routes. No new next-hop is invented here.
3. M2/Leader: resolve SHA/SHA-HMAC physical crypto-map source vs SHA256/tunnel-profile
   claims in Report/Draw.io. Current M3 preserves M2 crypto-map TVI-GRE-CMAP unchanged.
   Peers must get matching PSKs privately; do not put them in Git or QA evidence.
4. M1: DIST unused ports need BLACKHOLE/shutdown per contract; M3 deliberately does
   not alter M1 switching files. Supply actual DHCP backend, server IP/MAC/route,
   NTP service and DNS behavior, Option82 requirements, static endpoint inventory.
5. M1/Leader: resolve AP fan-out and IoT static/DHCP behavior before further L2 security.
   Observe real Po1/member trust propagation. DAI bindings are local, not automatically
   shared between access switches. Reboot/lease persistence recovery is mandatory.
6. Leader: authorize corporate flow matrix, additional admin sources, IPv6 management
   host/service addresses, banner wording, optional AAA and Syslog destination/transport.
7. Leader: integrate reviewed blocks into Configurations/; those placeholders remain
   untouched. Supply full lab export, image versions and console access; the M2 six-node
   lab excludes the LAN clients needed to verify M3.

## Deployment safeguards

Compare exact running hostname and interface map to Schema. Capture private pre-state.
Inspect existing M3_* objects and policy attachments; stop if names conflict. Do not
replace crypto-map attachments or another owner's access-group. Apply one reviewed
feature at a time from console, verify it, and preserve a fresh controller session.
All main fragments expect existing VLANs/access ports; no interface mode is changed.
A parser-accepted config is not a packet test. No static validator proves IOS syntax.

NAT deny is not a drop and not a VPN kill switch. If tunnel private routes disappear,
a physical default may forward untranslated private traffic. Do not claim fail-closed
VPN confidentiality from NAT exclusions. Verify routes, private ISP transit absence,
ESP encaps/decaps deltas and physical captures in the approved final design.

The root Report PNG remains stale (Fa ports/Gi0/4) while Schema/Draw.io use Gi1/0.
Do not wire from that old image. Report claims/evidence placeholders are Leader-owned
and intentionally preserved for a separate documentation integration change.

IPv6 Internet/synthetic public breakout also requires an approved ISP return route
for actual Guest/corporate IPv6 source prefixes. Current transport-only BGP does not
advertise those site prefixes. M2/Leader must decide the route policy; NAT66 is not
an acceptable invented workaround. Public IPv6 connectivity is NOT claimed here.
