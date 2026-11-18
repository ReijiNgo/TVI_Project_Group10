from helpers import *
from security_validation import *


class SecurityTests(BaseTest):
    def text(self,host='HANOI-RND-RTR01'):
        return (MODULE/'devices'/f'{host}_step7.cfg').read_text(encoding='utf8')
    def test_all_fragments(self):self.assertEqual(validate_all()['base_fragments'],9)
    def test_protected_sources_unchanged(self):
        manifest=json.loads((BASE/'tests/protected_manifest.json').read_text())
        for name,expected in manifest.items():
            with self.subTest(path=name):self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),expected)
    def test_no_executable_proposals(self):
        for p in (MODULE/'proposals').glob('*'):
            self.assertTrue(all(not l.strip() or l.lstrip().startswith('!') for l in p.read_text().splitlines()))
    def test_ipv4_guest_bootstrap_and_renew(self):
        rules=acl_rules(self.text(),'M3_GUEST4_IN',4)
        for src,dst in [('0.0.0.0','255.255.255.255'),('10.20.50.11','255.255.255.255'),('10.20.50.11','10.10.10.50'),('10.20.50.11','10.20.50.1')]:
            self.assertEqual(decision(rules,src,dst,'udp',68,67),'permit')
        self.assertEqual(decision(rules,'0.0.0.0','10.10.10.50','udp',68,67),'deny')
    def test_guest_private_services_not_opened(self):
        rules=acl_rules(self.text(),'M3_GUEST4_IN',4)
        for protocol,port in [('tcp',22),('udp',53),('tcp',53),('udp',123),('tcp',179)]:
            for dst in ['10.10.10.50','192.168.1.100','192.168.2.10','172.16.12.1','203.0.113.1']:
                with self.subTest(dst=dst,port=port):self.assertEqual(decision(rules,'10.20.50.11',dst,protocol,50000,port),'deny')
    def test_guest_public_access(self):
        rules=acl_rules(self.text(),'M3_GUEST4_IN',4)
        for protocol,port in [('udp',53),('tcp',53),('icmp',None)]:
            self.assertEqual(decision(rules,'10.20.50.11','8.8.8.8',protocol,50000,port),'permit')
    def test_guest_ipv4_spoofed_source(self):
        self.assertEqual(decision(acl_rules(self.text(),'M3_GUEST4_IN',4),'192.168.1.100','8.8.8.8','tcp',50000,22),'deny')
    def test_ipv6_nd_dad_and_rs(self):
        rules=acl_rules(self.text(),'M3_GUEST6_IN',6)
        for src,dst,kind in [('::','ff02::1:ff00:1234','nd-ns'),('fe80::123','ff02::2','router-solicitation'),('2001:db8:20:50::11','fe80::1','nd-na'),('fe80::123','2001:db8:20:50::1','nd-ns')]:
            self.assertEqual(decision(rules,src,dst,'icmp',icmp_type=kind),'permit')
    def test_ipv6_no_corporate_bypass_even_nd(self):
        rules=acl_rules(self.text(),'M3_GUEST6_IN',6)
        for dst in ['2001:db8:10:10::2','2001:db8:20:99::10','2001:db8:30:30::1','2001:db8:cafe:12::1','2001:db8:ffff:1::2']:
            for protocol,kind in [('tcp',None),('icmp','echo-request'),('icmp','nd-ns')]:
                self.assertEqual(decision(rules,'2001:db8:20:50::11',dst,protocol,dest_port=22,icmp_type=kind),'deny')
    def test_guest_router_advertisement_and_redirect_denied(self):
        rules=acl_rules(self.text(),'M3_GUEST6_IN',6)
        for kind in ['router-advertisement','redirect']:
            self.assertEqual(decision(rules,'fe80::123','ff02::1','icmp',icmp_type=kind),'deny')
    def test_nat_sources_and_vpn_exemption_behavior(self):
        for host in ['HCMC-EDGE-RTR01','HANOI-RND-RTR01','DANANG-LOG-RTR01']:
            rules=acl_rules(self.text(host),'M3_NAT_INTERNET',4)
            sources,_=sources_and_inside(host)
            for network in sources:
                src=str(network.network_address+10)
                self.assertEqual(decision(rules,src,'8.8.8.8','tcp',40000,443),'permit')
                for dst in ['10.10.10.50','10.20.20.1','10.30.30.1','192.168.2.10','172.16.12.1','203.0.113.5']:
                    self.assertEqual(decision(rules,src,dst,'tcp',40000,443),'deny')
            self.assertEqual(decision(rules,'10.255.255.1','8.8.8.8','tcp',40000,443),'deny')
    def test_trust_on_user_port_rejected(self):
        text=self.text('HCMC-CORE-SW01').replace('interface GigabitEthernet0/3\n no ip dhcp snooping trust','interface GigabitEthernet0/3\n ip dhcp snooping trust')
        with self.assertRaises(ValidationError):validate_base('HCMC-CORE-SW01',text,self.contract)
    def test_port_security_on_uplink_rejected(self):
        text=self.text('HANOI-RND-SW01').replace('interface Port-channel1\n ip dhcp snooping trust','interface Port-channel1\n switchport port-security\n ip dhcp snooping trust')
        with self.assertRaises(ValidationError):validate_base('HANOI-RND-SW01',text,self.contract)
    def test_premature_management_dai_rejected(self):
        with self.assertRaises(ValidationError):validate_base('HCMC-CORE-SW01',self.text('HCMC-CORE-SW01')+'ip arp inspection vlan 99\n',self.contract)
    def test_wrong_nat_role_rejected(self):
        with self.assertRaises(ValidationError):validate_base('HANOI-RND-RTR01',self.text().replace(' ip nat outside',' ip nat inside'),self.contract)
    def test_wrong_hostname_header_rejected(self):
        with self.assertRaises(ValidationError):validate_base('HANOI-RND-RTR01',self.text().replace('! TARGET: HANOI-RND-RTR01','! TARGET: OTHER'),self.contract)
    def test_contract_modification_commands_rejected(self):
        for cmd in ['ip address 10.1.1.1 255.255.255.0','shutdown','router ospf 2','crypto map OTHER','standby 10 ip 10.10.10.99','switchport trunk native vlan 1','channel-group 2 mode on']:
            with self.subTest(cmd=cmd),self.assertRaises(ValidationError):validate_base('HANOI-RND-RTR01',self.text()+cmd+'\n',self.contract)
    def test_missing_snooping_global_rejected(self):
        text=self.text('HCMC-CORE-SW01').replace('\nip dhcp snooping\n','\n')
        with self.assertRaises(ValidationError):validate_base('HCMC-CORE-SW01',text,self.contract)
    def test_missing_portsec_parameter_rejected(self):
        text=self.text('HCMC-CORE-SW01').replace(' switchport port-security violation restrict\n','')
        with self.assertRaises(ValidationError):validate_base('HCMC-CORE-SW01',text,self.contract)
    def test_guest_unapproved_service_exception_rejected(self):
        text=self.text().replace(' 50 deny ip any',' 45 permit tcp 10.20.50.0 0.0.0.127 host 10.10.10.50 eq 443\n 50 deny ip any',1)
        with self.assertRaises(ValidationError):validate_base('HANOI-RND-RTR01',text,self.contract)

    def test_unknown_acl_port_token_rejected(self):
        with self.assertRaises(ValidationError):rule('permit udp any eq misspelled any eq bootps',4)
    def test_unapproved_deny_address_rejected(self):
        text=self.text().replace(' 90 permit ip',' 85 deny ip any host 198.51.100.1\n 90 permit ip',1)
        with self.assertRaises(ValidationError):validate_base('HANOI-RND-RTR01',text,self.contract)
    def test_secret_redaction_helper(self):
        self.assertNotIn(self.creds.password,redact('exception '+self.creds.password,[self.creds.password]))
        self.assertEqual(redact('username fixture secret example'),'<'+'redacted credential line>')
