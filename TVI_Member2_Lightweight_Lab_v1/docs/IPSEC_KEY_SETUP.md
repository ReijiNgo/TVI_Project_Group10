# Secure IKEv1 key setup — manual, per endpoint, BEFORE `21_ipsec` map attachment

After `20_gre_ospf` diagnostic is successful, select TWO strong random PSKs:
- PSK A: between HQ (`203.0.113.1`) and Hanoi (`203.0.113.5`)
- PSK B: between HQ (`203.0.113.1`) and Da Nang (`203.0.113.9`)

With SSH/console to the relevant node, at `configure terminal` enter commands **manually, substituting the actual secret for the illustrative token**:

HQ:
```
crypto isakmp key YOUR_PSK_A address 203.0.113.5
crypto isakmp key YOUR_PSK_B address 203.0.113.9
```
Hanoi:
```
crypto isakmp key YOUR_PSK_A address 203.0.113.1
```
Da Nang:
```
crypto isakmp key YOUR_PSK_B address 203.0.113.1
```

Do not literally enter `YOUR_PSK_A`; do not save actual values in README/ZIP/Git, do not screenshot command history or unredacted running-config. *Cisco running/startup configs can contain recoverable preshared secrets.* Protect configuration exports. Both endpoints of a peer must use the same shared key. Then apply the matching `configs/21_ipsec/*.cfg` in global config mode.

Verify:
```
show crypto isakmp sa
show crypto ipsec sa
```
Generate multiple sourced pings through the tunnel, note both ESP encaps/decaps packet counters *before* and *after*, confirm they increased. `show interface Tunnel12` being UP alone does not prove encryption. If parser says `% Invalid input`, STOP and record that feature/subcommand; don't substitute random crypto syntax without checking image support.

**Security note:** This is a closed learning lab using IKEv1 to match older Cisco IOSv image expectations, not current production VPN architecture advice. Modern production should prefer supported IKEv2 and modern suites.
