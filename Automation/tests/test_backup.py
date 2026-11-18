from helpers import *
from unittest.mock import patch


class BackupTests(BaseTest):
    def test_pre_backup_complete(self):
        state=self.state();path=self.store.save(self.device,'pre',state)
        self.assertEqual(json.loads(path.read_text())['state'],state)
        self.assertIn('_pre_',path.name)
    def test_empty_output_rejected(self):
        s=self.state();s['running']=''
        with self.assertRaises(AutomationError):self.store.save(self.device,'pre',s)
        self.assertFalse(list((self.folder/'backups').glob('*.json')))
    def test_truncated_config_rejected(self):
        self.session.truncated=True
        with self.assertRaises(AutomationError):self.state()
    def test_wrong_management_ip_rejected(self):
        s=self.state();s['interfaces']=s['interfaces'].replace(self.device.management_ip,'192.168.1.11')
        with self.assertRaises(AutomationError):self.store.save(self.device,'pre',s)
    def test_no_overwrite(self):
        p=self.folder/'original';atomic_write(p,'one')
        with self.assertRaises(FileExistsError):atomic_write(p,'two')
        self.assertEqual(p.read_text(),'one')
        self.assertFalse(list(self.folder.glob('.tvi-*')))
    def test_unique_backup_names(self):
        a=self.store.save(self.device,'pre',self.state());b=self.store.save(self.device,'pre',self.state())
        self.assertNotEqual(a,b)
        self.assertTrue(a.exists() and b.exists())
    def test_path_traversal_rejected(self):
        from dataclasses import replace
        bad=replace(self.device,hostname='../outside')
        with self.assertRaises(AutomationError):self.store.save(bad,'pre',self.state())
        with self.assertRaises(AutomationError):self.store.save(self.device,'../../outside',self.state())
    def test_write_failure_no_temporary_file(self):
        with patch('automation_core.os.link',side_effect=OSError('fake disk error')):
            with self.assertRaises(OSError):atomic_write(self.folder/'out','data')
        self.assertFalse(list(self.folder.glob('.tvi-*')))
    def test_disk_failure_blocks_apply(self):
        with patch.object(self.store,'save',side_effect=OSError('fake disk failure')):
            result=self.run_device()
        self.assertFalse(result.success);self.assertEqual(self.session.sent,[])
        self.assertTrue(self.session.disconnected)
    def test_post_state_created(self):
        result=self.run_device()
        self.assertTrue(result.success,result.category)
        self.assertEqual(len(result.paths),2)
        self.assertEqual({json.loads(Path(p).read_text())['stage'] for p in result.paths},{'pre','post'})

    def test_retry_filename_collision_without_overwrite(self):
        from types import SimpleNamespace
        fixed=datetime.now(timezone.utc)
        with patch('automation_core.datetime') as clock,patch('automation_core.uuid.uuid4',side_effect=[SimpleNamespace(hex='collision'),SimpleNamespace(hex='collision'),SimpleNamespace(hex='unique')]):
            clock.now.return_value=fixed
            first=self.store.save(self.device,'pre',self.state())
            original=first.read_bytes()
            second=self.store.save(self.device,'pre',self.state())
        self.assertNotEqual(first,second)
        self.assertEqual(first.read_bytes(),original)
    def test_unsafe_artifact_link_rejected(self):
        with patch('automation_core.Path.is_symlink',return_value=True),self.assertRaises(ValidationError):ArtifactStore(self.folder/'unsafe')
