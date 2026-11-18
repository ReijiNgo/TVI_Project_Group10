from helpers import *


class RenderingTests(BaseTest):
    def test_only_site_vlans(self):
        for d in self.devices:
            commands=change_set(d,self.baseline,self.contract)
            actual={int(c.split()[1]) for c in commands if c.startswith('vlan ')}
            self.assertEqual(actual,set(self.contract.profiles[d.profile]))
            self.assertFalse(any(c.startswith(('interface ','router ','ip address','standby','switchport')) for c in commands))
    def test_plan_deterministic(self):
        self.assertEqual(make_plan(self.devices,self.baseline,self.contract),make_plan(self.devices,self.baseline,self.contract))
    def test_reject_arbitrary_commands(self):
        for command in ['interface Vlan99','ip route 0.0.0.0 0.0.0.0 Null0','username injected privilege 15','no vlan 99','vlan 666','ntp server 8.8.8.8']:
            with self.subTest(command=command),self.assertRaises(ValidationError):
                validate_commands([command],self.device,self.baseline,self.contract)
    def test_reject_nested_interface_in_vlan(self):
        with self.assertRaises(ValidationError):validate_commands(['vlan 10','interface Gi0/0','exit'],self.device,self.baseline,self.contract)
    def test_reject_newline_injection(self):
        with self.assertRaises(ValidationError):validate_commands(['ntp server 10.10.10.50\nshutdown'],self.device,self.baseline,self.contract)
    def test_unapproved_banner(self):
        d=load_yaml(BASE/'config/baseline.yaml');d['banner']={'approved':False,'text':'test'}
        p=self.folder/'baseline';p.write_text(yaml.safe_dump(d))
        with self.assertRaises(ValidationError):Baseline.read(p,self.contract)
    def test_explicit_approved_banner(self):
        d=load_yaml(BASE/'config/baseline.yaml');d['banner']={'approved':True,'text':'Authorized laboratory access only.'}
        p=self.folder/'baseline';p.write_text(yaml.safe_dump(d));b=Baseline.read(p,self.contract)
        self.assertIn('banner motd ^Authorized laboratory access only.^',change_set(self.device,b,self.contract))
    def test_syslog_not_assumed(self):
        d=load_yaml(BASE/'config/baseline.yaml');d['syslog']={'enabled':True,'host':'10.10.10.50'}
        p=self.folder/'baseline';p.write_text(yaml.safe_dump(d))
        with self.assertRaises(ValidationError):Baseline.read(p,self.contract)
    def test_aaa_not_automatically_enabled(self):
        d=load_yaml(BASE/'config/baseline.yaml');d['aaa']={'enabled':True}
        p=self.folder/'baseline';p.write_text(yaml.safe_dump(d))
        with self.assertRaises(ValidationError):Baseline.read(p,self.contract)
    def test_wrong_ntp(self):
        d=load_yaml(BASE/'config/baseline.yaml');d['ntp_server']='8.8.8.8'
        p=self.folder/'baseline';p.write_text(yaml.safe_dump(d))
        with self.assertRaises(ValidationError):Baseline.read(p,self.contract)
