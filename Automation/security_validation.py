"""Restricted fragment parser and first-match ACL model; NOT an IOS emulator/parser."""
from __future__ import annotations
import argparse
import hashlib
import ipaddress as ip
import json
import re
from pathlib import Path
from automation_core import ROOT, Contract, ValidationError

MODULE = ROOT/'Draft_Modules/member3_security_nat'
M1 = ROOT/'Draft_Modules/member1_switching_dhcp/devices'
M2 = ROOT/'TVI_Member2_Lightweight_Lab_v1/configs'
HARDENING = {'ip domain-name tvi.lab','ip ssh version 2','ip ssh time-out 60',
             'ip ssh authentication-retries 3','no ip http server','no service pad',
             'service timestamps log datetime msec'}
ACCESS = {'HCMC-CORE-SW01','HANOI-RND-SW01','HANOI-RND-SW02','DANANG-LOG-SW01'}
ENTERPRISE = ACCESS | {'HCMC-DIST-SW01','HCMC-DIST-SW02','HCMC-EDGE-RTR01','HANOI-RND-RTR01','DANANG-LOG-RTR01'}
PORTS = {'bootpc':68,'bootps':67,'domain':53}
SPECIAL_DENIES4 = {ip.ip_network(s) for s in ['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','203.0.113.0/24']}


def blocks(text):
    result=[]; heading=None; body=[]
    for no,line in enumerate(text.splitlines(),1):
        cmd=line.strip()
        if not cmd or cmd.startswith('!'):continue
        if cmd=='exit':
            if heading:result.append((heading,body));heading=None;body=[]
            continue
        if cmd.startswith(('interface ','ip access-list ','ipv6 access-list ','line vty ')):
            if heading:result.append((heading,body))
            heading=cmd;body=[]
        elif line.startswith(' ') and heading:body.append((no,cmd))
        else:
            if heading:result.append((heading,body));heading=None;body=[]
            result.append((cmd,[]))
    if heading:result.append((heading,body))
    return result


def m1_ports(host):
    """Expand M1 interface ranges, retaining access/trunk roles without rewriting them."""
    result={}
    p=M1/(host+'.cfg')
    for heading,body in blocks(p.read_text(encoding='utf8')):
        if not heading.startswith('interface '):continue
        spec=heading[len('interface '):].removeprefix('range ')
        names=[]
        for part in spec.split(','):
            part=part.strip()
            match=re.fullmatch(r'(GigabitEthernet\d+)/(\d+)\s*-\s*(\d+)',part)
            if match:names += [f'{match[1]}/{n}' for n in range(int(match[2]),int(match[3])+1)]
            else:names.append(part)
        for name in names:result[name]=[c for _,c in body]
    return result


def sources_and_inside(host):
    if host=='HCMC-EDGE-RTR01':
        ports=m1_ports('HCMC-DIST-SW01')
        sources=[]
        for name,commands in ports.items():
            if name in {'Vlan10','Vlan20','Vlan99'}:
                addr=next(c for c in commands if c.startswith('ip address ')).split()[2:]
                sources.append(ip.ip_interface('/'.join(addr)).network)
        return set(sources),{'GigabitEthernet0/1','GigabitEthernet0/2'}
    p=M1/(host+'_TV1_part.cfg')
    sources,inside=set(),set()
    for heading,body in blocks(p.read_text(encoding='utf8')):
        for _,cmd in body:
            if cmd.startswith('ip address '):
                sources.add(ip.ip_interface('/'.join(cmd.split()[2:])).network)
                inside.add(heading[len('interface '):])
    return sources,inside


def endpoint(tokens,index,version):
    token=tokens[index]
    if token=='any':return ip.ip_network('0.0.0.0/0' if version==4 else '::/0'),index+1
    if token=='host':return ip.ip_network(tokens[index+1]+('/32' if version==4 else '/128')),index+2
    if version==6:return ip.ip_network(token,strict=False),index+1
    wildcard=ip.IPv4Address(tokens[index+1])
    mask=ip.IPv4Address(int(wildcard)^0xffffffff)
    return ip.ip_network(token+'/'+str(mask),strict=False),index+2


def port_number(token):
    if token in PORTS:return PORTS[token]
    if token.isdigit() and 1<=int(token)<=65535:return int(token)
    raise ValidationError('unknown_acl_port')


def rule(line,version):
    t=line.split()
    if t and t[0].isdigit():t=t[1:]
    if t[0]=='remark':return None
    action,protocol=t[:2]
    source,i=endpoint(t,2,version);source_port=None;dest_port=None
    if i<len(t) and t[i]=='eq':source_port=port_number(t[i+1]);i+=2
    destination,i=endpoint(t,i,version)
    if i<len(t) and t[i]=='eq':dest_port=port_number(t[i+1]);i+=2
    kind=t[i] if i<len(t) else None
    if i+(1 if kind else 0)!=len(t) or action not in {'permit','deny'}:
        raise ValidationError('unsupported_acl_grammar')
    if protocol in {'tcp','udp'} and ((source_port is None and 'eq' in t[2:i]) or kind):
        # All implemented port-qualified rules must use a known port token.
        if kind:raise ValidationError('unsupported_port_grammar')
    return {'action':action,'protocol':protocol,'source':source,'destination':destination,
            'source_port':source_port,'dest_port':dest_port,'icmp_type':kind}


def acl_rules(text,name,version):
    prefix=('ip access-list extended ' if version==4 else 'ipv6 access-list ')+name
    bodies=[body for head,body in blocks(text) if head==prefix]
    if len(bodies)!=1:raise ValidationError('missing_or_duplicate_acl')
    return [r for _,c in bodies[0] if (r:=rule(c,version)) is not None]


def decision(rules,source,destination,protocol='ip',source_port=None,dest_port=None,icmp_type=None):
    src,dst=ip.ip_address(source),ip.ip_address(destination)
    for r in rules:
        if (src in r['source'] and dst in r['destination'] and r['protocol'] in {protocol,'ip','ipv6'}
                and (r['source_port'] is None or r['source_port']==source_port)
                and (r['dest_port'] is None or r['dest_port']==dest_port)
                and (r['icmp_type'] is None or r['icmp_type']==icmp_type)):
            return r['action']
    return 'deny'


def validate_base(host,text,contract):
    if host not in ENTERPRISE or not text.startswith('! TARGET: '+host+'\n'):
        raise ValidationError('fragment_target_mismatch')
    commands=[c.strip() for c in text.splitlines() if c.strip() and not c.strip().startswith('!')]
    forbidden=r'(?i)^(?:hostname |router |ipv6 router|ip(?:v6)? (?:address|route|default-gateway)|standby |spanning-tree |channel-group |encapsulation |tunnel |crypto |username |enable |aaa |shutdown$|no shutdown|switchport (?:mode|access|trunk)|line vty)'
    if any(re.match(forbidden,c) for c in commands):raise ValidationError('protected_or_credential_command')
    allowed=set(HARDENING)|{'exit'}
    if host in ACCESS:
        ports=m1_ports(host)
        trunks={name for name,c in ports.items() if 'switchport mode trunk' in c}
        servers={name for name,c in ports.items() if any('SERVER 10.10.10.50' in x for x in c)}
        clients={name for name,c in ports.items() if any(x in {'switchport access vlan 10','switchport access vlan 20','switchport access vlan 30'} for x in c)}-servers
        vlan_scope=set()
        for name in trunks:
            for c in ports[name]:
                if c.startswith('switchport trunk allowed vlan '):vlan_scope.update(map(int,c.split()[-1].split(',')))
        vlan_scope-={99,999}
        allowed |= {'ip dhcp snooping','no ip dhcp snooping information option','ip dhcp snooping vlan '+','.join(map(str,sorted(vlan_scope)))}
        required_global={'ip dhcp snooping','no ip dhcp snooping information option',
                         'ip dhcp snooping vlan '+','.join(map(str,sorted(vlan_scope)))}
        if not required_global<=set(commands):raise ValidationError('missing_snooping_globals')
        actual_trust=set();actual_sec=set();actual_arp=set()
        for head,body in blocks(text):
            if head.startswith('interface '):
                name=head[len('interface '):]
                ap_ports={n for n,c in ports.items() if 'switchport access vlan 50' in c}
                if name not in trunks|servers|clients|ap_ports:raise ValidationError('unknown_or_unowned_interface')
                for _,c in body:
                    if c=='ip dhcp snooping trust':
                        actual_trust.add(name)
                        if name not in trunks|servers:raise ValidationError('dhcp_trust_on_client')
                    elif c=='ip arp inspection trust':
                        actual_arp.add(name)
                        if name not in trunks:raise ValidationError('unapproved_arp_trust')
                    elif c.startswith('switchport port-security'):
                        if name not in clients:raise ValidationError('port_security_on_unsuitable_port')
                        actual_sec.add(name)
                        if c not in {'switchport port-security','switchport port-security maximum 2','switchport port-security mac-address sticky','switchport port-security violation restrict'}:
                            raise ValidationError('unapproved_port_security')
                    elif c not in {'no ip dhcp snooping trust','ip dhcp snooping limit rate 15','no ip arp inspection trust'}:
                        raise ValidationError('unapproved_interface_command')
                if name in clients:
                    required={'no ip dhcp snooping trust','ip dhcp snooping limit rate 15','no ip arp inspection trust',
                              'switchport port-security','switchport port-security maximum 2',
                              'switchport port-security mac-address sticky','switchport port-security violation restrict'}
                    if not required<={c for _,c in body}:raise ValidationError('incomplete_client_security')
                allowed.add(head);allowed.update(c for _,c in body)
        if actual_trust!=trunks|servers or actual_sec!=clients or actual_arp!=trunks:
            raise ValidationError('incomplete_l2_security_mapping')
        if any(c.startswith('ip arp inspection vlan') for c in commands):raise ValidationError('premature_dai')
    elif host.endswith('RTR01'):
        sources,inside=sources_and_inside(host)
        nat=acl_rules(text,'M3_NAT_INTERNET',4)
        permits={r['source'] for r in nat if r['action']=='permit' and r['destination']==ip.ip_network('0.0.0.0/0')}
        denies={r['destination'] for r in nat if r['action']=='deny'}
        if any(r['protocol']!='ip' or r['source_port'] is not None or r['dest_port'] is not None or r['icmp_type'] is not None
               or (r['action']=='deny' and r['source']!=ip.ip_network('0.0.0.0/0')) for r in nat):
            raise ValidationError('unapproved_nat_match')
        if permits!=sources or denies!=SPECIAL_DENIES4 or [r['action'] for r in nat]!=['deny']*4+['permit']*len(sources):
            raise ValidationError('nat_sources_or_exemption_order')
        nat_roles={}
        for head,body in blocks(text):
            if head=='ip access-list extended M3_NAT_INTERNET':
                allowed.add(head);allowed.update(c for _,c in body)
            elif head.startswith('interface '):
                name=head[len('interface '):]
                for _,c in body:
                    if c in {'ip nat inside','ip nat outside'}:nat_roles[name]=c
                    elif not (host=='HANOI-RND-RTR01' and name=='GigabitEthernet0/1.50' and c in {'ip access-group M3_GUEST4_IN in','ipv6 traffic-filter M3_GUEST6_IN in'}):
                        raise ValidationError('unapproved_router_interface_command')
                allowed.add(head);allowed.update(c for _,c in body)
            elif host=='HANOI-RND-RTR01' and head in {'ip access-list extended M3_GUEST4_IN','ipv6 access-list M3_GUEST6_IN'}:
                allowed.add(head);allowed.update(c for _,c in body)
        if nat_roles!={**{name:'ip nat inside' for name in inside},'GigabitEthernet0/0':'ip nat outside'}:
            raise ValidationError('incorrect_nat_roles')
        allowed.add('ip nat inside source list M3_NAT_INTERNET interface GigabitEthernet0/0 overload')
        if host=='HANOI-RND-RTR01':validate_guest(text)
    if not set(commands)<=allowed:raise ValidationError('unapproved_fragment_command')
    if not HARDENING<=set(commands):raise ValidationError('missing_safe_hardening')


def validate_guest(text):
    attaches=dict(blocks(text)).get('interface GigabitEthernet0/1.50',[])
    if not {'ip access-group M3_GUEST4_IN in','ipv6 traffic-filter M3_GUEST6_IN in'}<={c for _,c in attaches}:
        raise ValidationError('guest_attachment_missing')
    v4=acl_rules(text,'M3_GUEST4_IN',4);v6=acl_rules(text,'M3_GUEST6_IN',6)
    guest4=ip.ip_network('10.20.50.0/25');any4=ip.ip_network('0.0.0.0/0')
    for r in v4:
        if r['action']=='deny':
            if r['source']!=any4 or r['destination'] not in SPECIAL_DENIES4|{any4} or r['protocol']!='ip':
                raise ValidationError('unapproved_guest_deny_address')
            continue
        public=(r['source']==guest4 and r['destination']==any4 and r['protocol']=='ip'
                and r['source_port'] is None and r['dest_port'] is None)
        dhcp=(r['protocol']=='udp' and r['source_port']==68 and r['dest_port']==67
              and r['icmp_type'] is None and ((r['source']==ip.ip_network('0.0.0.0/32') and r['destination']==ip.ip_network('255.255.255.255/32'))
              or (r['source']==guest4 and r['destination'] in {ip.ip_network(x+'/32') for x in ['255.255.255.255','10.10.10.50','10.20.50.1']})))
        if not (public or dhcp):raise ValidationError('unapproved_guest_service_exception')
    guest6=ip.ip_network('2001:db8:20:50::/64');link6=ip.ip_network('fe80::/10')
    allowed_denies6={ip.ip_network(x) for x in ['2001:db8:10::/48','2001:db8:20::/48','2001:db8:30::/48',
                    '2001:db8:cafe::/48','2001:db8:ffff::/48','fc00::/7','fe80::/10','ff00::/8','::/0']}
    for r in v6:
        if r['action']=='deny':
            if r['source']!=ip.ip_network('::/0') or r['destination'] not in allowed_denies6:
                raise ValidationError('unapproved_guest6_deny_address')
            if r['protocol']=='icmp' and r['icmp_type'] not in {'router-advertisement','redirect'}:
                raise ValidationError('unapproved_guest6_control_deny')
            continue
        public=(r['source']==guest6 and r['destination']==ip.ip_network('::/0') and r['protocol']=='ipv6')
        control=(r['protocol']=='icmp' and r['source'] in {guest6,link6,ip.ip_network('::/128')}
                 and r['destination'] in {guest6,link6,ip.ip_network('ff02::1/128'),ip.ip_network('ff02::2/128'),ip.ip_network('ff02::1:ff00:0/104')}
                 and r['icmp_type'] in {'nd-ns','nd-na','router-solicitation'})
        if not (public or control):raise ValidationError('unapproved_guest6_service_exception')
    checks=[(v4,'0.0.0.0','255.255.255.255','udp',68,67,None,'permit'),
            (v4,'10.20.50.11','10.10.10.50','udp',68,67,None,'permit'),
            (v4,'10.20.50.11','8.8.8.8','udp',50000,53,None,'permit'),
            (v6,'::','ff02::1:ff00:1234','icmp',None,None,'nd-ns','permit'),
            (v6,'fe80::123','ff02::2','icmp',None,None,'router-solicitation','permit')]
    for dst in ['10.10.10.50','10.20.20.1','10.30.30.1','192.168.1.100','192.168.2.10','192.168.3.10','172.16.12.1','172.16.13.1','10.255.255.1','203.0.113.1','203.0.113.5']:
        checks.append((v4,'10.20.50.11',dst,'tcp',50000,22,None,'deny'))
    for dst in ['2001:db8:10:10::2','2001:db8:20:99::10','2001:db8:30:99::10','2001:db8:cafe:12::1','2001:db8:ffff:1::1']:
        checks.append((v6,'2001:db8:20:50::11',dst,'tcp',50000,22,None,'deny'))
    for rules,src,dst,proto,sp,dp,kind,expected in checks:
        if decision(rules,src,dst,proto,sp,dp,kind)!=expected:raise ValidationError('guest_policy_behavior_failed')


def validate_all():
    contract=Contract.read()
    actual={p.name.removesuffix('_step7.cfg') for p in (MODULE/'devices').glob('*.cfg')}
    if actual!=ENTERPRISE:raise ValidationError('step7_device_set_mismatch')
    for host in sorted(actual):validate_base(host,(MODULE/'devices'/f'{host}_step7.cfg').read_text(encoding='utf8'),contract)
    for p in (MODULE/'conditional').glob('*.cfg'):
        text=p.read_text(encoding='utf8');host=text.splitlines()[0].removeprefix('! TARGET: ')
        if host not in ENTERPRISE or not p.name.startswith(host+'_') or 'CONDITIONAL' not in text:raise ValidationError('conditional_target_or_gate_missing')
        cmds=[c.strip() for c in text.splitlines() if c.strip() and not c.lstrip().startswith('!')]
        if '_dai_' in p.name:
            if host not in ACCESS-{'DANANG-LOG-SW01'} or cmds!=['ip arp inspection vlan 20']:
                raise ValidationError('unsafe_dai_activation')
        elif '_vty_' in p.name:
            maximum=int(p.stem.rsplit('_',1)[-1])
            expected=['ip access-list standard M3_MGMT_VTY','10 permit host 192.168.1.100','20 deny any','exit',
                      'ipv6 access-list M3_MGMT6_VTY','deny ipv6 any any','exit',f'line vty 0 {maximum}',
                      'login local','transport input ssh','exec-timeout 10 0','access-class M3_MGMT_VTY in',
                      'ipv6 access-class M3_MGMT6_VTY in','exit']
            if maximum not in {4,15} or cmds!=expected:raise ValidationError('unsafe_vty_fragment')
        else:raise ValidationError('unknown_conditional_fragment')
    for p in (MODULE/'proposals').glob('*'):
        if any(c.strip() and not c.lstrip().startswith('!') for c in p.read_text(encoding='utf8').splitlines()):
            raise ValidationError('executable_unapproved_proposal')
    return {'base_fragments':len(actual),'conditional_fragments':len(list((MODULE/'conditional').glob('*.cfg'))),
            'status':'STATIC PASS; IOS syntax and runtime NOT VERIFIED'}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:print(json.dumps(validate_all(),indent=2));return 0
    except (ValidationError,ValueError,IndexError,KeyError) as exc:
        print('STATIC FAIL: '+(exc.category if isinstance(exc,ValidationError) else 'fragment_parse_failed'));return 1


if __name__=='__main__':raise SystemExit(main())
