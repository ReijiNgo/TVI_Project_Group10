from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from automation_core import *


class FakeSession:
    def __init__(self, device):
        self.device=device
        self.vlans={99:'MANAGEMENT'}
        self.ntp=False
        self.banner=None
        self.disconnected=False
        self.sent=[]
        self.calls=[]
        self.prompt=device.hostname+'#'
        self.enabled=True
        self.empty_run=False
        self.truncated=False
        self.cli_response=None
        self.echo_only=False
        self.route_drift=False
        self.extra=''
        self.vlan_unsupported=False
        self.vlan_ports={}
        self.implicit_vlan_names=set()
        self.config_count=0
        self.fail_after=None
        self.fail_exception=RuntimeError('offline injected failure')
        self.fail_once=True
        self.interface_override=None
        self.config_mode=False

    def running(self):
        out='hostname '+self.device.hostname+'\n'
        out+='vtp mode transparent\n'
        out+=''.join(f'vlan {v}\n'+('' if v in self.implicit_vlan_names else f' name {n}\n') for v,n in sorted(self.vlans.items()))
        out+='interface Vlan99\n ip address '+self.device.management_ip+' 255.255.255.0\n'
        out+='interface GigabitEthernet0/1\n switchport mode trunk\n switchport trunk native vlan 999\n'
        if self.ntp:out+='ntp server 10.10.10.50\n'
        if self.banner is not None:out+='banner motd ^C\n'+self.banner+'\n^C\n'
        out+=self.extra
        return out+('' if self.truncated else 'end\n')

    def find_prompt(self):return self.prompt
    def check_enable_mode(self):return self.enabled
    def enable(self):self.enabled=True
    def send_command(self,command,**kwargs):
        self.calls.append(command)
        if command=='show running-config':return '' if self.empty_run else self.running()
        if command=='show ip interface brief':return self.interface_override or 'Interface              IP-Address      OK? Method Status                Protocol\nVlan99                 '+self.device.management_ip+'    YES manual up                    up\n'
        if command=='show vlan brief':
            if self.vlan_unsupported:return '% Invalid input detected at marker'
            return 'VLAN Name                             Status    Ports\n'+''.join(f'{v} {n} active '+', '.join(self.vlan_ports.get(v,[]))+'\n' for v,n in sorted(self.vlans.items()))
        raise AssertionError('Unexpected command')
    def send_config_set(self,commands,**kwargs):
        self.sent.append(list(commands))
        if self.cli_response is not None:return self.cli_response
        if not self.echo_only:
            vlan=None
            for c in commands:
                self.config_mode=True
                if c.startswith('vlan '):
                    vlan=int(c.split()[1])
                    if vlan not in self.vlans:
                        self.vlans[vlan]=f'VLAN{vlan:04d}';self.implicit_vlan_names.add(vlan)
                elif c.startswith(' name '):
                    self.vlans[vlan]=c.split()[1];self.implicit_vlan_names.discard(vlan)
                elif c==' no name':
                    self.vlans[vlan]=f'VLAN{vlan:04d}';self.implicit_vlan_names.add(vlan)
                elif c=='exit':vlan=None
                elif c.startswith('no vlan '):self.vlans.pop(int(c.split()[2]),None)
                elif c=='no ntp server 10.10.10.50':self.ntp=False
                elif c.startswith('ntp server '):self.ntp=True
                elif c=='no banner motd':self.banner=None
                elif c.startswith('banner motd '):self.banner=c[len('banner motd ')+1:-1]
                else:raise AssertionError('Unauthorized mutation')
                self.config_count+=1
                if self.fail_after==self.config_count:
                    if self.fail_once:self.fail_after=None
                    raise self.fail_exception
            if self.route_drift:self.extra+='ip route 0.0.0.0 0.0.0.0 Null0\n'
        self.config_mode=False
        return '\n'.join(commands)+'\n'+self.device.hostname+'#'
    def exit_config_mode(self):self.config_mode=False;return self.prompt
    def disconnect(self):self.disconnected=True


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.contract=Contract.read()
        self.devices=load_inventory(BASE/'inventory.yaml',self.contract)
        self.device=next(d for d in self.devices if d.hostname=='HCMC-CORE-SW01')
        self.baseline=Baseline.read(BASE/'config/baseline.yaml',self.contract)
        self.store=ArtifactStore(self.folder)
        self.session=FakeSession(self.device)
        self.creds=Credentials('offline-test-user','fake-password-for-redaction-test','fake-enable-for-redaction-test')
        self.known=self.folder/'known_hosts'
        self.known.write_text('# offline fake only\n')
        self.connections=[]

    def factory(self,**kwargs):
        self.connections.append(kwargs)
        return self.session

    def state(self):return collect(self.session,self.device)
    def review(self):return make_plan([self.device],self.baseline,self.contract,{self.device.hostname:self.state()})
    def run_device(self,mode='apply',review=None,**kwargs):
        return operate(self.device,mode,self.baseline,self.contract,self.creds,self.store,self.known,
                       review if review is not None else self.review(),factory=self.factory,delay=lambda _:None,**kwargs)
    def inventory_file(self,data):
        p=self.folder/'inventory.yaml'
        p.write_text(yaml.safe_dump(data),encoding='utf8')
        return p
