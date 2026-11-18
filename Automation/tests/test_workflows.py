from helpers import *
from unittest.mock import patch
import contextlib
import io
import auto_provision


class WorkflowTests(BaseTest):
    def test_plan_zero_ssh(self):
        factory=lambda **_:self.fail('plan opened SSH')
        with contextlib.redirect_stdout(io.StringIO()):code=auto_provision.main([],factory=factory,credential_provider=lambda:self.fail('plan prompted'))
        self.assertEqual(code,0)
    def test_plan_rejected_for_apply_without_connection(self):
        plan=make_plan([self.device],self.baseline,self.contract)
        result=self.run_device(review=plan)
        self.assertFalse(result.success);self.assertEqual(self.connections,[])
    def test_hostname_mismatch_blocks_apply(self):
        self.session.prompt='OTHER-DEVICE#'
        result=self.run_device()
        self.assertEqual(result.category,'hostname_mismatch');self.assertEqual(self.session.sent,[])
        self.assertTrue(self.session.disconnected)
    def test_running_hostname_mismatch(self):
        review=self.review();self.session.extra='hostname OTHER-DEVICE\n'
        result=self.run_device(review=review)
        self.assertFalse(result.success);self.assertEqual(self.session.sent,[])
    def test_audit_readonly(self):
        result=self.run_device('audit')
        self.assertTrue(result.success);self.assertEqual(self.session.sent,[])
    def test_audit_vlan_unsupported(self):
        self.session.vlan_unsupported=True
        result=self.run_device('audit')
        self.assertTrue(result.success,result.category)
        self.assertIsNone(result.state['vlans'])
    def test_apply_vlan_unsupported(self):
        self.session.vlan_unsupported=True
        result=self.run_device()
        self.assertFalse(result.success);self.assertEqual(self.session.sent,[])
    def test_pre_backup_empty_blocks_apply(self):
        review=self.review();self.session.empty_run=True
        result=self.run_device(review=review)
        self.assertFalse(result.success);self.assertEqual(self.session.sent,[])
    def test_timeout_retry_exhausted(self):
        calls=[]
        def fail(**kw):calls.append(kw);raise TimeoutError('fake-sensitive-payload')
        result=operate(self.device,'audit',self.baseline,self.contract,self.creds,self.store,self.known,factory=fail,delay=lambda _:None)
        self.assertEqual(result.category,'ssh_timeout');self.assertEqual(len(calls),2)
    def test_authentication_never_retried(self):
        class NetmikoAuthenticationException(Exception):pass
        calls=[]
        def fail(**kw):calls.append(kw);raise NetmikoAuthenticationException(self.creds.password)
        result=operate(self.device,'audit',self.baseline,self.contract,self.creds,self.store,self.known,factory=fail)
        self.assertEqual(result.category,'authentication_failed');self.assertEqual(len(calls),1)
    def test_transient_timeout_then_success(self):
        calls=[]
        def transient(**kw):
            calls.append(kw)
            if len(calls)==1:raise TimeoutError()
            return self.session
        result=operate(self.device,'audit',self.baseline,self.contract,self.creds,self.store,self.known,factory=transient,delay=lambda _:None)
        self.assertTrue(result.success);self.assertEqual(len(calls),2)
    def test_privilege_failure(self):
        self.session.enabled=False
        with patch.object(self.session,'enable',side_effect=ValueError(self.creds.secret)):
            result=self.run_device()
        self.assertEqual(result.category,'privilege_escalation_failed');self.assertEqual(self.session.sent,[])
    def test_cli_errors_detected(self):
        self.session.cli_response='% Invalid input detected at marker'
        result=self.run_device()
        self.assertFalse(result.success);self.assertTrue(result.partial)
        self.assertEqual(result.category,'cisco_cli_error')
    def test_echo_not_success(self):
        self.session.echo_only=True
        result=self.run_device()
        self.assertFalse(result.success);self.assertEqual(result.category,'postcheck_baseline_failed')
    def test_protected_route_drift_detected(self):
        self.session.route_drift=True
        result=self.run_device()
        self.assertFalse(result.success);self.assertEqual(result.category,'protected_configuration_changed')
    def test_review_stale(self):
        review=self.review();self.session.extra='ip routing\n'
        result=self.run_device(review=review)
        self.assertFalse(result.success);self.assertEqual(self.session.sent,[])
    def test_review_tampered(self):
        review=self.review();review['targets'][0]['commands'].append('shutdown')
        result=self.run_device(review=review)
        self.assertFalse(result.success);self.assertEqual(self.connections,[])
    def test_structured_logs_no_secrets(self):
        self.session.extra='username fixture secret '+self.creds.password+'\n'
        result=self.run_device('audit');self.assertTrue(result.success)
        logs=''.join(p.read_text() for p in (self.folder/'logs').glob('*.json'))
        for secret in (self.creds.username,self.creds.password,self.creds.secret,'username fixture secret'):
            self.assertNotIn(secret,logs)
        self.assertNotIn(self.creds.password,repr(self.creds))
    def test_raw_exception_not_logged(self):
        def fail(**kw):raise RuntimeError(self.creds.password)
        result=operate(self.device,'audit',self.baseline,self.contract,self.creds,self.store,self.known,factory=fail)
        self.assertFalse(result.success)
        self.assertNotIn(self.creds.password,''.join(p.read_text() for p in (self.folder/'logs').glob('*.json')))
    def test_partial_batch_nonzero(self):
        targets=[d for d in self.devices if d.enabled]
        sessions={d.management_ip:FakeSession(d) for d in targets}
        def factory(**kw):
            if kw['host']==targets[0].management_ip:raise TimeoutError()
            return sessions[kw['host']]
        results,code=batch(targets,'audit',self.baseline,self.contract,self.creds,self.store,self.known,factory=factory,delay=lambda _:None)
        self.assertEqual(code,1);self.assertEqual(sum(r.success for r in results),2)
    def test_interrupt_cleanup(self):
        review=self.review()
        with patch.object(self.session,'send_config_set',side_effect=KeyboardInterrupt):
            result=self.run_device(review=review)
        self.assertEqual(result.category,'interrupted');self.assertTrue(result.partial)
        self.assertTrue(self.session.disconnected)
    def test_ssh_hostkeys_strict(self):
        self.run_device('audit')
        self.assertTrue(self.connections[0]['ssh_strict'])
        self.assertTrue(self.connections[0]['alt_host_keys'])
    def test_cli_invalid_mode(self):
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as exc:
            auto_provision.main(['--mode','bogus'])
        self.assertEqual(exc.exception.code,2)
    def test_cli_apply_requires_confirmation_before_network(self):
        with contextlib.redirect_stderr(io.StringIO()):
            code=auto_provision.main(['--mode','apply','--device',self.device.hostname],factory=lambda **_:self.fail('connected'))
        self.assertEqual(code,2)
    def test_cli_invalid_inventory_before_network(self):
        path=self.folder/'empty';path.write_text('')
        with contextlib.redirect_stderr(io.StringIO()):
            code=auto_provision.main(['--mode','audit','--inventory',str(path)],factory=lambda **_:self.fail('connected'))
        self.assertEqual(code,2)
    def test_output_path_traversal(self):
        with contextlib.redirect_stderr(io.StringIO()):code=auto_provision.main(['--out','../outside.json'])
        self.assertEqual(code,2)

    def test_any_percent_cli_error_fails_closed(self):
        self.session.cli_response='% VLAN_CREATE_FAIL: resource unavailable'
        result=self.run_device()
        self.assertEqual(result.category,'cisco_cli_error')

    def test_mutation_failure_count_is_unknown(self):
        self.session.cli_response='% Failed'
        r=self.run_device()
        self.assertIsNone(r.changes)
        log=json.loads(next((self.folder/'logs').glob('*.json')).read_text())
        self.assertIsNone(log['changes_applied'])
        self.assertTrue(log['partial_configuration_possible'])
    def test_netmiko_config_invalid_exception(self):
        class ConfigInvalidException(Exception):pass
        review=self.review()
        with patch.object(self.session,'send_config_set',side_effect=ConfigInvalidException(self.creds.password)):
            r=self.run_device(review=review)
        self.assertEqual(r.category,'cisco_cli_error')
        self.assertTrue(r.partial)
    def test_cli_audit_review_then_fake_apply(self):
        out=self.folder/'reports/review.json'
        common=['--device',self.device.hostname,'--known-hosts',str(self.known),'--artifact-root',str(self.folder)]
        with contextlib.redirect_stdout(io.StringIO()):
            code=auto_provision.main(['--mode','audit',*common,'--out',str(out)],factory=self.factory,credential_provider=lambda:self.creds)
        self.assertEqual(code,0)
        self.assertTrue(out.exists())
        with contextlib.redirect_stdout(io.StringIO()):
            code=auto_provision.main(['--mode','apply',*common,'--review-plan',str(out),'--confirm'],factory=self.factory,credential_provider=lambda:self.creds)
        self.assertEqual(code,0)
        self.assertEqual(len(self.session.sent),1)
    def test_cli_audit_stdout_single_json(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            code=auto_provision.main(['--mode','audit','--device',self.device.hostname,'--known-hosts',str(self.known),'--artifact-root',str(self.folder)],factory=self.factory,credential_provider=lambda:self.creds)
        self.assertEqual(code,0)
        self.assertIn('review',json.loads(output.getvalue()))
    def test_cli_known_hosts_required_no_connection(self):
        with contextlib.redirect_stderr(io.StringIO()):
            code=auto_provision.main(['--mode','audit','--known-hosts',str(self.folder/'missing')],factory=lambda **_:self.fail('connected'))
        self.assertEqual(code,2)
    def test_apply_batch_failure_stops_remaining_devices(self):
        targets=[d for d in self.devices if d.enabled]
        sessions={d.hostname:FakeSession(d) for d in targets}
        states={d.hostname:collect(sessions[d.hostname],d) for d in targets}
        plan=make_plan(targets,self.baseline,self.contract,states)
        sessions[targets[0].hostname].cli_response='% Failed'
        calls=[]
        def factory(**kw):
            calls.append(kw['host'])
            return next(s for s in sessions.values() if s.device.management_ip==kw['host'])
        results,code=batch(targets,'apply',self.baseline,self.contract,self.creds,self.store,self.known,plan,factory,lambda _:None)
        self.assertEqual(code,1);self.assertEqual(len(calls),1)
        self.assertEqual(results[-1].category,'not_attempted_after_failure')

    def test_partial_failure_forensic_capture(self):
        self.session.cli_response='% Failed'
        r=self.run_device()
        self.assertFalse(r.success)
        self.assertEqual(r.recovery_capture,'saved')
        self.assertTrue(any('_partial_' in p for p in r.paths))
    def test_partial_capture_failure_not_hidden(self):
        review=self.review()
        self.session.cli_response='% Failed'
        original=self.store.save
        def save(device,stage,state):
            if stage=='partial':raise OSError('fake private payload')
            return original(device,stage,state)
        with patch.object(self.store,'save',side_effect=save):r=self.run_device(review=review)
        self.assertEqual(r.category,'cisco_cli_error')
        self.assertEqual(r.recovery_capture,'failed:filesystem_or_transport_failed')
