from helpers import *


class IdempotencyTests(BaseTest):
    def test_second_apply_no_mutation(self):
        first=self.run_device();self.assertTrue(first.success,first.category)
        second=self.run_device()
        self.assertTrue(second.success,second.category)
        self.assertEqual(second.changes,0)
        self.assertEqual(len(self.session.sent),1)
    def test_existing_extra_vlans_preserved(self):
        self.session.vlans[30]='LOGISTICS_OPS'
        result=self.run_device();self.assertTrue(result.success,result.category)
        self.assertEqual(self.session.vlans[30],'LOGISTICS_OPS')
        self.assertFalse(any(c=='vlan 30' for c in self.session.sent[0]))
    def test_correct_name_no_change(self):
        self.assertNotIn('vlan 99',change_set(self.device,self.baseline,self.contract,self.state()))
    def test_wrong_vlan_name_is_repaired(self):
        self.session.vlans[99]='wrong'
        self.assertIn(' name MANAGEMENT',change_set(self.device,self.baseline,self.contract,self.state()))
    def test_ntp_prefer_already_compliant(self):
        s=self.state();s['running']=s['running'].replace('end\n','ntp server 10.10.10.50 prefer\nend\n')
        self.assertNotIn('ntp server 10.10.10.50',change_set(self.device,self.baseline,self.contract,s))
    def test_banner_ios_delimiter(self):
        self.assertEqual(banner_text('banner motd ^C\nLab access only\n^C\n'),'Lab access only')
        b=Baseline(self.contract.ntp_server,'Lab access only')
        first=operate(self.device,'apply',b,self.contract,self.creds,self.store,self.known,
                      make_plan([self.device],b,self.contract,{self.device.hostname:self.state()}),self.factory,lambda _:None)
        self.assertTrue(first.success,first.category)
        self.assertEqual(change_set(self.device,b,self.contract,self.state()),[])
