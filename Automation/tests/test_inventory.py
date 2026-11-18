from helpers import *
import copy


class InventoryTests(BaseTest):
    def data(self):return load_yaml(BASE/'inventory.yaml')
    def reject(self,data):
        with self.assertRaises(ValidationError):load_inventory(self.inventory_file(data),self.contract)
    def test_valid_inventory(self):
        self.assertEqual(len(self.devices),4)
        self.assertEqual({d.hostname for d in self.devices if d.enabled},MANDATORY)
    def test_empty_yaml(self):
        p=self.folder/'empty';p.write_text('')
        with self.assertRaises(ValidationError):load_inventory(p,self.contract)
    def test_yaml_parse_error(self):
        p=self.folder/'bad';p.write_text('devices: [')
        with self.assertRaises(ValidationError):load_inventory(p,self.contract)
    def test_yaml_duplicate_keys(self):
        p=self.folder/'bad';p.write_text('devices: []\ndevices: []\n')
        with self.assertRaises(ValidationError):load_inventory(p,self.contract)
    def test_wrong_structure(self):self.reject({'devices':{}})
    def test_missing_hostname(self):
        d=self.data();del d['devices'][0]['hostname'];self.reject(d)
    def test_duplicate_hostname(self):
        d=self.data();d['devices'].append(copy.deepcopy(d['devices'][0]));self.reject(d)
    def test_duplicate_ip(self):
        d=self.data();d['devices'][1]['management_ip']=d['devices'][0]['management_ip'];self.reject(d)
    def test_wrong_ip(self):
        d=self.data();d['devices'][0]['management_ip']='192.168.1.11';self.reject(d)
    def test_unsupported_type(self):
        d=self.data();d['devices'][0]['device_type']='cisco_ios_telnet';self.reject(d)
    def test_invalid_ports(self):
        for port in (0,65536,True,'22'):
            with self.subTest(port=port):
                d=self.data();d['devices'][0]['port']=port;self.reject(d)
    def test_profile_mismatch(self):
        d=self.data();d['devices'][0]['profile']='hanoi_access';self.reject(d)
    def test_unknown_enabled_target(self):
        d=self.data();d['devices'][-1]['enabled']=True;self.reject(d)
    def test_mandatory_missing(self):
        d=self.data();d['devices'].pop(0);self.reject(d)
    def test_boolean_enabled_required(self):
        d=self.data();d['devices'][0]['enabled']='true';self.reject(d)
    def test_optional_requires_explicit_optin(self):
        with self.assertRaises(ValidationError):select_devices(self.devices,[OPTIONAL])
        self.assertEqual(select_devices(self.devices,[OPTIONAL],include_optional=True)[0].hostname,OPTIONAL)
        self.assertNotIn(OPTIONAL,[d.hostname for d in select_devices(self.devices,group='HANOI',include_optional=True)])
    def test_apply_requires_target(self):
        with self.assertRaises(ValidationError):select_devices(self.devices,explicit=True)
    def test_contract_profiles_scoped(self):
        self.assertEqual(self.contract.profiles['hcmc_access'],(10,20,99,999))
        self.assertEqual(self.contract.profiles['hanoi_access'],(20,50,99,999))
        self.assertEqual(self.contract.profiles['danang_access'],(30,99,999))
