"""Run local import/compile/CLI checks only; never invoke a live audit or apply."""
from __future__ import annotations
import importlib
import inspect
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from automation_core import BASE, ROOT


def main():
    observations=[]
    def check(name,condition):
        observations.append({'check':name,'passed':bool(condition)})
    sources=list(BASE.glob('*.py'))+list((BASE/'tests').glob('*.py'))
    for p in sources:compile(p.read_text(encoding='utf8'),str(p),'exec')
    check('compile_all_member3_python',True)
    import netmiko, yaml
    from netmiko.base_connection import BaseConnection
    from netmiko.cisco.cisco_ios import CiscoIosSSH
    for name in ['automation_core','auto_provision','security_validation']:importlib.import_module(name)
    check('imports_without_network',True)
    params=inspect.signature(BaseConnection.__init__).parameters
    check('netmiko_connection_parameters',{'ssh_strict','alt_host_keys','alt_key_file','read_timeout_override'}<=set(params))
    params=inspect.signature(CiscoIosSSH.send_config_set).parameters
    check('netmiko_config_error_detection_parameters',{'error_pattern','read_timeout','cmd_verify'}<=set(params))
    def run(*args,cwd=ROOT):
        return subprocess.run([sys.executable,'-B',str(BASE/'auto_provision.py'),*args],cwd=cwd,capture_output=True,text=True,encoding='utf8')
    first=run();second=run()
    check('default_plan_success',first.returncode==0)
    check('default_plan_deterministic',first.stdout==second.stdout)
    data=json.loads(first.stdout)
    check('default_plan_three_targets',len(data['targets'])==3 and all(t['state_sha256'] is None for t in data['targets']))
    help_result=run('--help');check('cli_help',help_result.returncode==0 and '--review-plan' in help_result.stdout)
    bad=run('--mode','invalid');check('invalid_argument_exit2',bad.returncode==2)
    unknown=run('--device','OTHER');check('invalid_target_exit2',unknown.returncode==2)
    with tempfile.TemporaryDirectory() as folder:
        elsewhere=run(cwd=folder)
        check('working_directory_independent',elsewhere.returncode==0 and elsewhere.stdout==first.stdout)
    check('no_sensitive_artifacts_tracked',subprocess.run(['git','ls-files','Automation/backups/*.json','Automation/states/*.json','Automation/logs/*.json'],cwd=ROOT,capture_output=True,text=True).stdout.strip()=='')
    output={'python':sys.version.split()[0],'netmiko':netmiko.__version__,'pyyaml':yaml.__version__,
            'total':len(observations),'passed':sum(x['passed'] for x in observations),'checks':observations,
            'network_connections':0,'runtime_verification':'NOT RUN'}
    print(json.dumps(output,indent=2))
    return 0 if all(x['passed'] for x in observations) else 1


if __name__=='__main__':raise SystemExit(main())
