from helpers import *
import ast
import shlex
import auto_provision


class DocumentationTests(BaseTest):
    def docs(self):
        return list(BASE.glob('*.md'))+list((ROOT/'Draft_Modules/member3_security_nat').glob('*.md'))+[ROOT/'README.md']
    def test_local_markdown_links_resolve(self):
        for p in self.docs():
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text(encoding='utf8')):
                if target.startswith(('https://','http://','#')):continue
                with self.subTest(document=p.name,target=target):self.assertTrue((p.parent/target.split('#')[0]).exists())
    def test_documented_cli_arguments_parse_without_execution(self):
        count=0
        for p in self.docs():
            for line in p.read_text(encoding='utf8').splitlines():
                if line.startswith('.\\.venv\\Scripts\\python.exe -B Automation/auto_provision.py'):
                    args=shlex.split(line.split('Automation/auto_provision.py',1)[1])
                    auto_provision.parser().parse_args(args);count+=1
        self.assertGreaterEqual(count,5)
    def test_documented_python_script_paths_exist(self):
        for p in self.docs():
            for target in re.findall(r'(?:-B\s+)([A-Za-z0-9_/]+\.py)',p.read_text(encoding='utf8')):
                with self.subTest(target=target):self.assertTrue((ROOT/target).is_file())
    def test_every_member3_python_compiles(self):
        for p in list(BASE.glob('*.py'))+list((BASE/'tests').glob('*.py')):
            compile(p.read_text(encoding='utf8'),str(p),'exec')
    def test_no_active_secret_in_device_fragments(self):
        for p in (ROOT/'Draft_Modules/member3_security_nat').rglob('*.cfg'):
            for line in p.read_text(encoding='utf8').splitlines():
                if line.lstrip().startswith('!'):continue
                self.assertIsNone(re.search(r'(?i)\b(?:username|enable secret|isakmp key|password)\b',line))
    def test_no_raw_runtime_artifacts_in_git(self):
        import subprocess
        r=subprocess.run(['git','ls-files','Automation/backups/*.json','Automation/states/*.json','Automation/logs/*.json'],cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(r.stdout.strip(),'')
    def test_runtime_artifacts_ignored_but_keepfiles_not_ignored(self):
        import subprocess
        for directory in ['backups','states','logs','reports']:
            r=subprocess.run(['git','check-ignore',f'Automation/{directory}/fake-runtime.json'],cwd=ROOT,capture_output=True)
            self.assertEqual(r.returncode,0)
            r=subprocess.run(['git','check-ignore',f'Automation/{directory}/.gitkeep'],cwd=ROOT,capture_output=True)
            self.assertEqual(r.returncode,1)
    def test_conditional_policies_not_automation_inputs(self):
        source=(BASE/'automation_core.py').read_text(encoding='utf8')
        self.assertNotIn('send_config_from_file',source)
        self.assertNotIn('member3_security_nat',source)
        self.assertNotIn('save_config(',source)
