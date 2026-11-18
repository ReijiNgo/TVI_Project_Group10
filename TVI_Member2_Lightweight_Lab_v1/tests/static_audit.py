#!/usr/bin/env python3
"""Only checks file consistency. Does NOT emulate IOS or certify functionality."""
from pathlib import Path
import csv, sys
root=Path(__file__).resolve().parents[1]
base=root/'configs/00_base'
expected={'ISP-CORE-RTR01','HCMC-EDGE-RTR01','HCMC-DIST-SW01','HCMC-DIST-SW02','HANOI-RND-RTR01','DANANG-LOG-RTR01'}
fail=[]
actual={f.stem for f in base.glob('*.cfg')}
if actual!=expected:fail.append(f'00_base mismatch missing={expected-actual} extra={actual-expected}')
links=list(csv.DictReader((root/'docs/physical_links.csv').open(encoding='utf8')))
if len(links)!=5:fail.append(f'5 physical links expected, got {len(links)}')
seen=set()
for l in links:
 for item in [('device_A','interface_A'),('device_B','interface_B')]:
  endpoint=(l[item[0]],l[item[1]])
  if endpoint in seen:fail.append(f'Duplicate physical port: {endpoint}')
  seen.add(endpoint)
 if l['device_A'] not in expected or l['device_B'] not in expected:fail.append(f'Unknown node: {l}')
required={'configs/10_ebgp':4,'configs/20_gre_ospf':3,'configs/21_ipsec':3,'configs/30_qos':3}
for d,n in required.items():
 count=len(list((root/d).glob('*.cfg')))
 if count!=n:fail.append(f'{d}: expected {n}, got {count}')
for p in (root/'configs').rglob('*.cfg'):
 s=p.read_text(encoding='utf8')
 if 'YOUR_PSK' in s or any(line.strip().startswith('crypto isakmp key ') for line in s.splitlines() if not line.lstrip().startswith('!')):fail.append(f'Credential-like line in deliverable: {p}')
 if p.parent.name=='10_ebgp' and 'network 10.' in s:fail.append(f'Private BGP announcement: {p}')
 if p.parent.name=='00_base' and f'hostname {p.stem}' not in s:fail.append(f'Missing hostname: {p}')
 if p.parent.name=='20_gre_ospf' and ('tunnel source GigabitEthernet0/0' not in s or 'router ospf 1' not in s):fail.append(f'GRE incomplete: {p}')
if fail:
 print('STATIC AUDIT FAILED (does not test Cisco runtime)')
 for f in fail:print(' - '+f)
 sys.exit(1)
print('STATIC AUDIT PASSED: six-node inventory, five physical links, staged files, no hardcoded IKE secrets, no BGP private prefix origination.')
print('THIS IS NOT A CISCO/EVE TEST PASS. Inspect actual CLI and traffic to claim operational PASS.')
