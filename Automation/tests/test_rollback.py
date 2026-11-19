from helpers import *
from unittest.mock import patch
import contextlib
import copy
import io
import auto_provision
from rollback import (compensation, config_lines, interface_table, preflight, protected,
                      verification, vlan_table)


class RollbackTests(BaseTest):
    def assert_restored(self, before, result):
        self.assertFalse(result.success)
        self.assertTrue(result.rollback_attempted)
        self.assertEqual(result.recovery_status,'verified',result.summary())
        self.assertEqual(self.state(),before)
        for key in ('full_config','owned_state','protected_state','interface_state','vlan_state'):
            self.assertEqual(result.verification[key],'MATCH')
        report=json.loads(Path(result.report_path).read_text())
        self.assertFalse(report['apply_success'])
        self.assertTrue(Path(report['pre_snapshot']).exists())
        self.assertTrue(Path(report['pre_config']).exists())
        self.assertTrue(Path(report['restored_snapshot']).exists())
        self.assertEqual(report['diff_summary']['canonical_lines_added'],0)

    def compliant(self):
        self.session.vlans.update({v:self.contract.vlans[v] for v in self.contract.profiles[self.device.profile]})
        self.session.ntp=True

    def test_first_command_creates_vlan_then_failure_restores_absence(self):
        before=self.state();self.session.fail_after=1
        r=self.run_device()
        self.assert_restored(before,r)
        self.assertTrue(r.mutation_observed)
        partial=json.loads(Path(next(p for p in r.paths if '_partial_' in p)).read_text())['state']
        self.assertIn(10,vlan_table(partial['vlans']))
        self.assertIn(['no vlan 10'],self.session.sent)

    def test_multiple_partial_changes_restore_all(self):
        before=self.state();self.session.fail_after=8
        r=self.run_device();self.assert_restored(before,r)
        partial=json.loads(Path(next(p for p in r.paths if '_partial_' in p)).read_text())['state']
        self.assertIn(10,vlan_table(partial['vlans']));self.assertIn(999,vlan_table(partial['vlans']))

    def test_existing_vlan_name_and_membership_restored(self):
        self.compliant();self.session.vlans[20]='OLD_ENGINEERING'
        self.session.vlan_ports[20]=['Gi0/3','Gi1/1']
        before=self.state();self.session.fail_after=2
        r=self.run_device();self.assert_restored(before,r)
        self.assertEqual(self.session.vlan_ports[20],['Gi0/3','Gi1/1'])
        self.assertIn(['vlan 20',' name OLD_ENGINEERING','exit'],self.session.sent)

    def test_implicit_default_vlan_name_restored_without_explicit_name(self):
        self.compliant();self.session.vlans[20]='VLAN0020';self.session.implicit_vlan_names.add(20)
        before=self.state();self.session.fail_after=2
        r=self.run_device();self.assert_restored(before,r)
        self.assertIn(['vlan 20',' no name','exit'],self.session.sent)

    def test_ntp_added_then_removed(self):
        self.compliant();self.session.ntp=False
        before=self.state();self.session.fail_after=1
        r=self.run_device();self.assert_restored(before,r)
        self.assertIn(['no ntp server 10.10.10.50'],self.session.sent)

    def test_existing_ntp_options_and_unrelated_servers_preserved(self):
        self.session.extra='ntp server 10.10.10.50 prefer\nntp server 192.0.2.20\n'
        before=self.state();self.session.fail_after=5
        r=self.run_device();self.assert_restored(before,r)
        self.assertFalse(any(c.startswith('no ntp') for batch in self.session.sent for c in batch))

    def test_banner_original_exact_text_restored_with_safe_delimiter(self):
        self.compliant();self.baseline=Baseline(self.baseline.ntp_server,'Approved lab notice')
        self.session.banner='Original ^ notice with spaces  '
        before=self.state();self.session.fail_after=1
        r=self.run_device();self.assert_restored(before,r)
        self.assertEqual(self.session.banner,'Original ^ notice with spaces  ')

    def test_new_banner_removed(self):
        self.compliant();self.baseline=Baseline(self.baseline.ntp_server,'Approved notice')
        before=self.state();self.session.fail_after=1
        r=self.run_device();self.assert_restored(before,r)
        self.assertIn(['no banner motd'],self.session.sent)

    def test_multiline_original_banner_rejected_before_mutation(self):
        self.baseline=Baseline(self.baseline.ntp_server,'Approved notice')
        self.session.banner='Original\nsecond line'
        r=self.run_device()
        self.assertEqual(r.category,'original_banner_not_safely_restorable')
        self.assertFalse(r.rollback_attempted);self.assertEqual(self.session.sent,[])

    def test_cisco_error_after_real_mutation_recovers(self):
        before=self.state();self.session.fail_after=2
        self.session.fail_exception=AutomationError('cisco_cli_error')
        r=self.run_device();self.assert_restored(before,r)
        self.assertEqual(r.category,'cisco_cli_error')

    def test_postcheck_failure_restores_state(self):
        before=self.state();original=self.session.send_config_set
        def send(commands,**kw):
            output=original(commands,**kw)
            if not any(c.startswith('no ') for c in commands):self.session.ntp=False
            return output
        with patch.object(self.session,'send_config_set',side_effect=send):r=self.run_device()
        self.assertEqual(r.category,'postcheck_baseline_failed');self.assert_restored(before,r)

    def test_rejected_rollback_never_verified(self):
        before=self.state();self.session.fail_after=2
        original=self.session.send_config_set
        def send(commands,**kw):
            if commands[0].startswith('no '):return '% Invalid input detected at marker'
            return original(commands,**kw)
        with patch.object(self.session,'send_config_set',side_effect=send):r=self.run_device()
        self.assertEqual(r.recovery_status,'incomplete');self.assertNotEqual(self.state(),before)
        self.assertEqual(r.verification['owned_state'],'MISMATCH')

    def test_transport_loss_during_rollback_reconnects_and_rederives(self):
        before=self.state();self.session.fail_after=8
        original=self.session.send_config_set;lost=[]
        def send(commands,**kw):
            output=original(commands,**kw)
            if commands[0].startswith('no ') and not lost:
                lost.append(True);raise ConnectionError(self.creds.password)
            return output
        with patch.object(self.session,'send_config_set',side_effect=send):r=self.run_device()
        self.assert_restored(before,r);self.assertEqual(len(self.connections),2)
        for connection in self.connections:
            self.assertTrue(connection['ssh_strict']);self.assertTrue(connection['alt_host_keys'])
        # The inverse that completed before the channel dropped isn't replayed.
        self.assertEqual(sum(b==['no vlan 999'] for b in self.session.sent),1)

    def test_lost_connection_cannot_reconnect_is_unverified(self):
        review=self.review();original=self.session.send_config_set
        def send(commands,**kw):
            original(commands,**kw)
            self.session.send_command=lambda *a,**k:(_ for _ in ()).throw(ConnectionError())
            raise ConnectionError()
        calls=[]
        def factory(**kwargs):
            calls.append(kwargs)
            if len(calls)>1:raise ConnectionError(self.creds.password)
            return self.session
        with patch.object(self.session,'send_config_set',side_effect=send):
            r=operate(self.device,'apply',self.baseline,self.contract,self.creds,self.store,self.known,
                      review,factory=factory,delay=lambda _:None)
        self.assertEqual(r.recovery_status,'unverified')
        self.assertTrue(all(v=='UNVERIFIED' for v in r.verification.values()))
        self.assertTrue(json.loads(Path(r.report_path).read_text())['manual_steps'])

    def test_unrelated_route_drift_preserved_and_reported(self):
        self.session.route_drift=True
        r=self.run_device()
        self.assertEqual(r.category,'protected_configuration_changed')
        self.assertEqual(r.recovery_status,'incomplete')
        self.assertIn('ip route ',self.session.running())
        self.assertEqual(r.verification['owned_state'],'MATCH')
        self.assertEqual(r.verification['protected_state'],'MISMATCH')
        self.assertFalse(any(c.startswith(('ip ','interface ','router ','crypto ','username ','line ')) for b in self.session.sent for c in b))

    def test_foreign_owned_name_is_not_overwritten(self):
        self.compliant();self.session.vlans[20]='ORIGINAL'
        original=self.session.send_config_set
        def send(commands,**kw):
            output=original(commands,**kw)
            self.session.vlans[20]='CONCURRENT_NAME'
            raise RuntimeError()
        with patch.object(self.session,'send_config_set',side_effect=send):r=self.run_device()
        self.assertEqual(r.recovery_status,'incomplete')
        self.assertEqual(self.session.vlans[20],'CONCURRENT_NAME')
        self.assertEqual(len(self.session.sent),1)

    def test_new_vlan_with_ports_not_removed(self):
        original=self.session.send_config_set
        def send(commands,**kw):
            output=original(commands,**kw)
            self.session.vlan_ports[10]=['Gi0/4'];raise RuntimeError()
        with patch.object(self.session,'send_config_set',side_effect=send):r=self.run_device()
        self.assertEqual(r.recovery_status,'incomplete')
        self.assertNotIn(['no vlan 10'],self.session.sent)
        self.assertIn(10,self.session.vlans)

    def test_snapshot_mismatch_never_verified(self):
        self.session.fail_after=1;original=self.session.send_command
        def show(command,**kw):
            out=original(command,**kw)
            if command=='show ip interface brief' and self.session.config_count>1:
                out+='GigabitEthernet0/2 unassigned YES unset down down\n'
            return out
        with patch.object(self.session,'send_command',side_effect=show):r=self.run_device()
        self.assertEqual(r.recovery_status,'incomplete')
        self.assertEqual(r.verification['interface_state'],'MISMATCH')

    def test_ctrl_c_after_mutation_runs_recovery(self):
        before=self.state();self.session.fail_after=2;self.session.fail_exception=KeyboardInterrupt()
        r=self.run_device();self.assert_restored(before,r)
        self.assertEqual(r.category,'interrupted')

    def test_second_interrupt_is_unverified(self):
        self.session.fail_after=2;self.session.fail_exception=KeyboardInterrupt()
        with patch.object(self.session,'exit_config_mode',side_effect=KeyboardInterrupt):r=self.run_device()
        self.assertEqual(r.category,'interrupted');self.assertEqual(r.recovery_status,'unverified')
        self.assertTrue(self.session.disconnected)

    def test_demo_actual_delta_readback_and_evidence(self):
        before=self.state();output=[]
        r=self.run_device(demo=True,progress=output.append)
        self.assert_restored(before,r)
        self.assertEqual(r.category,'controlled_demo_failure')
        report=json.loads(Path(r.report_path).read_text())
        self.assertTrue(report['controlled_failure_injected'])
        changed=json.loads(Path(report['demo_changed_snapshot']).read_text())['state']
        self.assertNotEqual(changed,before)
        self.assertIn('ROLLBACK VERIFIED','\n'.join(output))
        self.assertEqual(self.session.sent[0],['vlan 10',' name EXEC_FINANCE','exit'])

    def test_demo_no_delta_rejected(self):
        self.compliant();r=self.run_device(demo=True)
        self.assertEqual(r.category,'demo_requires_safe_pending_change')
        self.assertFalse(r.rollback_attempted);self.assertEqual(self.session.sent,[])

    def test_demo_echo_only_does_not_claim_injection(self):
        self.session.echo_only=True;r=self.run_device(demo=True)
        self.assertEqual(r.category,'demo_change_not_proven')
        self.assertFalse(json.loads(Path(r.report_path).read_text())['controlled_failure_injected'])

    def test_cli_demo_authorization_gates_before_network(self):
        variants=[['--demo-rollback'],['--confirm-demo'],
                  ['--mode','apply','--device',self.device.hostname,'--demo-rollback'],
                  ['--mode','apply','--group','HCMC','--demo-rollback','--confirm-demo'],
                  ['--mode','apply','--device',self.device.hostname,'--device','HANOI-RND-SW01','--demo-rollback','--confirm-demo'],
                  ['--mode','apply','--device',self.device.hostname,'--demo-rollback','--confirm-demo','--confirm']]
        for args in variants:
            with self.subTest(args=args),contextlib.redirect_stderr(io.StringIO()):
                code=auto_provision.main(args,factory=lambda **_:self.fail('unexpected SSH'))
                self.assertEqual(code,2)

    def test_cli_confirmed_demo_nonzero_and_restored(self):
        before=self.state();path=self.folder/'reports/review.json'
        atomic_write(path,json.dumps(self.review()))
        with contextlib.redirect_stdout(io.StringIO()):
            code=auto_provision.main(['--mode','apply','--device',self.device.hostname,'--review-plan',str(path),
                '--confirm','--demo-rollback','--confirm-demo','--known-hosts',str(self.known),
                '--artifact-root',str(self.folder)],factory=self.factory,credential_provider=lambda:self.creds)
        self.assertEqual(code,1);self.assertEqual(self.state(),before)

    def test_backup_readback_failure_blocks_mutation(self):
        with patch.object(self.store,'verify_prebackup',side_effect=OSError(self.creds.password)):
            r=self.run_device()
        self.assertEqual(self.session.sent,[]);self.assertFalse(r.rollback_attempted)

    def test_missing_backup_readback_blocks_mutation(self):
        with patch.object(self.store,'save',return_value=self.folder/'missing.json'):r=self.run_device()
        self.assertEqual(self.session.sent,[]);self.assertFalse(r.rollback_attempted)

    def test_report_failure_after_mutation_fails_closed(self):
        before=self.state();self.session.fail_after=2
        with patch.object(self.store,'recovery_report',side_effect=OSError(self.creds.password)):r=self.run_device()
        self.assertEqual(self.state(),before)
        self.assertEqual(r.recovery_status,'unverified');self.assertFalse(r.success)

    def test_sensitive_banner_config_and_exception_not_in_shared_evidence(self):
        self.compliant();self.baseline=Baseline(self.baseline.ntp_server,'private approved banner')
        self.session.banner='private original banner';self.session.extra='username fixture secret private-credential\n'
        self.session.fail_after=1;self.session.fail_exception=RuntimeError(self.creds.password)
        r=self.run_device()
        shared=''.join(p.read_text() for folder in ('logs','reports') for p in (self.folder/folder).glob('*.json'))
        for secret in ('private approved banner','private original banner','private-credential',self.creds.password,self.creds.secret):
            self.assertNotIn(secret,shared)
        self.assertEqual(r.recovery_status,'verified')

    def test_vlan_change_requires_local_vtp_mode(self):
        original=self.session.running
        with patch.object(self.session,'running',side_effect=lambda:original().replace('vtp mode transparent\n','')):
            r=self.run_device()
        self.assertEqual(r.category,'vlan_changes_require_local_vtp_mode');self.assertEqual(self.session.sent,[])

    def test_vtp_drift_blocks_vlan_recovery(self):
        self.session.ntp=True  # Isolate VLAN compensation from independent NTP undo.
        original=self.session.send_config_set;running=self.session.running
        def send(commands,**kw):
            original(commands,**kw)
            self.session.running=lambda:running().replace('vtp mode transparent','vtp mode server')
            raise RuntimeError()
        with patch.object(self.session,'send_config_set',side_effect=send):r=self.run_device()
        self.assertEqual(r.recovery_status,'incomplete')
        self.assertEqual(len(self.session.sent),1)

    def test_successful_apply_evidence_failure_triggers_recovery(self):
        before=self.state()
        with patch.object(self.store,'recovery_report',side_effect=OSError()):r=self.run_device()
        self.assertEqual(self.state(),before)
        self.assertFalse(r.success);self.assertEqual(r.recovery_status,'unverified')

    def test_successful_apply_log_failure_triggers_recovery(self):
        before=self.state()
        with patch.object(self.store,'event',side_effect=OSError()):r=self.run_device()
        self.assertEqual(self.state(),before)
        self.assertFalse(r.success);self.assertTrue(r.rollback_attempted)

    def test_cfg_runtime_artifact_ignored(self):
        import subprocess
        proc=subprocess.run(['git','check-ignore','Automation/backups/example_pre.cfg'],cwd=ROOT,capture_output=True)
        self.assertEqual(proc.returncode,0)

    def test_normal_success_and_idempotent_rerun_do_not_rollback(self):
        first=self.run_device();second=self.run_device()
        self.assertTrue(first.success);self.assertTrue(second.success)
        self.assertFalse(first.rollback_attempted);self.assertFalse(second.rollback_attempted)
        self.assertEqual(second.category,'compliant_no_changes')
        self.assertEqual(second.changes,0)
        self.assertFalse(change_set(self.device,self.baseline,self.contract,self.state()))

    def test_commands_inside_banner_are_not_configuration_or_capability(self):
        self.session.banner='vtp mode transparent\nntp server 10.10.10.50\nvlan 10\n name EXEC_FINANCE'
        state=self.state();state['running']=state['running'].replace('vtp mode transparent\n','',1)
        commands=change_set(self.device,self.baseline,self.contract,state)
        self.assertIn('ntp server 10.10.10.50',commands)
        self.assertIn('vlan 10',commands)
        with self.assertRaises(AutomationError) as exc:preflight(state,commands,self.device,self.baseline,self.contract)
        self.assertEqual(exc.exception.category,'vlan_changes_require_local_vtp_mode')

    def test_new_vlan_not_deleted_if_interface_config_changed(self):
        original=self.session.send_config_set
        def send(commands,**kw):
            original(commands,**kw)
            self.session.extra+='interface GigabitEthernet0/4\n switchport access vlan 10\n'
            raise RuntimeError()
        with patch.object(self.session,'send_config_set',side_effect=send):r=self.run_device()
        self.assertEqual(r.recovery_status,'incomplete')
        self.assertNotIn(['no vlan 10'],self.session.sent)
        self.assertIn('switchport access vlan 10',self.session.running())

    def test_ambiguous_recovery_vlan_sources_do_not_authorize_delete(self):
        self.session.fail_after=2;original=self.session.send_command
        def show(command,**kw):
            out=original(command,**kw)
            if command=='show vlan brief' and self.session.config_count:
                out=out.replace('10 EXEC_FINANCE active','10 CONCURRENT active')
            return out
        with patch.object(self.session,'send_command',side_effect=show):r=self.run_device()
        self.assertEqual(r.recovery_status,'unverified')
        self.assertNotIn(['no vlan 10'],self.session.sent)

    def test_missing_restored_evidence_cannot_be_verified(self):
        before=self.state();self.session.fail_after=2;original=self.store.save
        def save(device,stage,state):
            if stage=='restored':raise OSError()
            return original(device,stage,state)
        with patch.object(self.store,'save',side_effect=save):r=self.run_device()
        self.assertEqual(self.state(),before)
        self.assertEqual(r.recovery_status,'unverified')
        self.assertEqual(r.verification['full_config'],'MATCH')

    def test_broken_progress_sink_does_not_prevent_recovery(self):
        before=self.state()
        def broken_console(message):raise BrokenPipeError()
        r=self.run_device(demo=True,progress=broken_console)
        self.assert_restored(before,r)

    def test_batch_failure_after_mutation_stops_remaining(self):
        targets=[d for d in self.devices if d.enabled]
        sessions={d.hostname:FakeSession(d) for d in targets}
        states={d.hostname:collect(sessions[d.hostname],d) for d in targets}
        review=make_plan(targets,self.baseline,self.contract,states)
        sessions[targets[0].hostname].fail_after=2
        calls=[]
        def factory(**kw):
            calls.append(kw['host']);return next(s for s in sessions.values() if s.device.management_ip==kw['host'])
        results,code=batch(targets,'apply',self.baseline,self.contract,self.creds,self.store,self.known,review,factory,lambda _:None)
        self.assertEqual(code,1);self.assertEqual(len(calls),1)
        self.assertEqual(results[0].recovery_status,'verified')
        self.assertEqual(collect(sessions[targets[0].hostname],targets[0]),states[targets[0].hostname])
        self.assertTrue(all(r.category=='not_attempted_after_failure' for r in results[1:]))


class ComparisonTests(BaseTest):
    def compare(self,a,b):return verification(a,b,self.device,self.baseline,self.contract)

    def test_full_config_normalizes_only_known_noise(self):
        a=self.state();b=copy.deepcopy(a)
        b['running']='Building configuration...\n\nCurrent configuration : 1234 bytes\n! Last configuration change at 01:02:03 UTC\n!\n'+b['running'].replace('\n','  \r\n')
        checks=self.compare(a,b)
        self.assertEqual(checks['full_config'],'MATCH');self.assertFalse(checks['raw_running_exact'])

    def test_full_config_does_not_hide_security_routing_or_order_changes(self):
        a=self.state()
        for command in ('ip route 0.0.0.0 0.0.0.0 Null0','router ospf 2','username someone secret hidden',' ip access-group OTHER in'):
            b=copy.deepcopy(a);b['running']=b['running'].replace('end\n',command+'\nend\n')
            with self.subTest(command=command):
                self.assertEqual(self.compare(a,b)['full_config'],'MISMATCH')
                self.assertEqual(self.compare(a,b)['protected_state'],'MISMATCH')

    def test_banner_payload_spaces_preserved(self):
        a=self.state();b=copy.deepcopy(a)
        a['running']=a['running'].replace('end\n','banner motd ^C\nNotice  \n^C\nend\n')
        b['running']=b['running'].replace('end\n','banner motd #Notice  #\nend\n')
        self.assertEqual(self.compare(a,b)['full_config'],'MATCH')
        b['running']=b['running'].replace('Notice  #','Notice #')
        self.assertEqual(self.compare(a,b)['full_config'],'MISMATCH')

    def test_unsupported_serialization_unverified(self):
        a=self.state();b=copy.deepcopy(a);b['running']=b['running'].replace('end\n','banner motd ^C\nnever closes\nend\n')
        self.assertEqual(self.compare(a,b)['full_config'],'UNVERIFIED')

    def test_vlan_membership_wrapping_normalizes_but_membership_changes_fail(self):
        a='VLAN Name Status Ports\n20 RND_ENGINEERING active Gi0/1, Gi0/2\n99 MANAGEMENT active\n'
        b='VLAN Name Status Ports\n---- ---- ---- ----\n20 RND_ENGINEERING active Gi0/2,\n                                       Gi0/1\n99 MANAGEMENT active\n'
        self.assertEqual(vlan_table(a),vlan_table(b))
        self.assertNotEqual(vlan_table(a),vlan_table(b.replace('Gi0/1','Gi0/3')))

    def test_interface_ips_status_protocol_and_method_are_compared(self):
        a=self.state()
        for old,new in (('YES manual','YES NVRAM'),(' up',' down'),(self.device.management_ip,'192.0.2.1')):
            b=copy.deepcopy(a);b['interfaces']=b['interfaces'].replace(old,new)
            self.assertEqual(self.compare(a,b)['interface_state'],'MISMATCH')

    def test_vlan_attribute_parent_identity_is_protected(self):
        a=self.state();b=copy.deepcopy(a)
        a['running']=a['running'].replace('vlan 99\n','vlan 99\n state suspend\n')
        b['running']=b['running'].replace('vlan 99\n','vlan 20\n state suspend\nvlan 99\n')
        self.assertNotEqual(protected(a,self.device,self.baseline,self.contract),protected(b,self.device,self.baseline,self.contract))
