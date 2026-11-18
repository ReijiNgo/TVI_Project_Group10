"""TVI contract validation and offline desired-state logic. No network at import time."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import os
import re
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "Automation"
MANDATORY = frozenset({"HCMC-CORE-SW01", "HANOI-RND-SW01", "DANANG-LOG-SW01"})
OPTIONAL = "HANOI-RND-SW02"
SITE_PROFILES = {"HCMC": "hcmc_access", "HANOI": "hanoi_access", "DANANG": "danang_access"}
CLI_ERROR = re.compile(r"(?im)^\s*(?:%|Error:|Invalid command|Invalid input|Incomplete command|Ambiguous command)")


class AutomationError(Exception):
    """Messages are fixed categories, never raw device output or exception payloads."""
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


class ValidationError(AutomationError):
    pass


class UniqueLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, (str, int)) or key in result:
            raise ValidationError("duplicate_or_invalid_yaml_key")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def load_yaml(path: Path):
    try:
        data = yaml.load(Path(path).read_text(encoding="utf-8-sig"), Loader=UniqueLoader)
    except ValidationError:
        raise
    except (OSError, UnicodeError, yaml.YAMLError):
        raise ValidationError("yaml_read_or_parse_failed") from None
    if not isinstance(data, dict) or not data:
        raise ValidationError("empty_or_invalid_yaml")
    return data


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Device:
    hostname: str
    management_ip: str
    device_type: str
    port: int
    site: str
    enabled: bool
    profile: str


@dataclass(frozen=True)
class Contract:
    management: dict
    vlans: dict
    profiles: dict
    ntp_server: str
    fingerprint: str

    @classmethod
    def read(cls, root: Path = ROOT):
        try:
            text = (root / "Specs/IP_Addressing_Schema.md").read_text(encoding="utf8")
            vlan_section = text.split("## 2.")[0]
            vlans = {int(k): v for k, v in re.findall(r"\*\*`(\d+)`\*\*\s*\|\s*`([A-Z_]+)`", vlan_section)}
            tail = text.split('Automation/inventory.yaml')[-1]
            management = dict(re.findall(r'`([A-Z0-9-]+)`:\s*`(\d+\.\d+\.\d+\.\d+)`', tail))
            server = re.search(r'Server.*?\*\*\s*`(10\.\d+\.\d+\.\d+)`', text.split('## 4.')[1])
            profiles = {}
            sources = {}
            for site, profile in SITE_PROFILES.items():
                host = next(h for h in MANDATORY if h.startswith(site + '-'))
                source = (root / 'Draft_Modules/member1_switching_dhcp/devices' / (host + '.cfg')).read_text(encoding='utf8')
                allowed = set()
                for csv in re.findall(r'^\s*switchport trunk allowed vlan ([\d,]+)', source, re.M):
                    allowed.update(int(v) for v in csv.split(','))
                if not allowed or not allowed <= vlans.keys():
                    raise ValidationError('contract_profile_drift')
                profiles[profile] = tuple(sorted(allowed | {999}))
                sources[host] = source
            if set(management) != MANDATORY | {OPTIONAL} or len(vlans) != 6 or not server:
                raise ValidationError('contract_format_or_scope_changed')
            return cls(management, vlans, profiles, server.group(1), digest([text, sources]))
        except (OSError, IndexError, KeyError):
            raise ValidationError('contract_unavailable') from None


def load_inventory(path: Path, contract: Contract) -> list[Device]:
    data = load_yaml(path)
    if set(data) != {'devices'} or not isinstance(data['devices'], list) or not data['devices']:
        raise ValidationError('invalid_inventory_structure')
    devices = []
    names, addresses = set(), set()
    fields = set(Device.__dataclass_fields__)
    for entry in data['devices']:
        if not isinstance(entry, dict) or set(entry) != fields:
            raise ValidationError('invalid_device_fields')
        if any(not isinstance(entry[k], str) for k in fields - {'port', 'enabled'}):
            raise ValidationError('invalid_device_field_types')
        host, addr = entry['hostname'], entry['management_ip']
        if host in names or addr in addresses:
            raise ValidationError('duplicate_device_or_address')
        names.add(host); addresses.add(addr)
        try:
            ipaddress.IPv4Address(addr)
        except ValueError:
            raise ValidationError('invalid_management_ip') from None
        if contract.management.get(host) != addr:
            raise ValidationError('hostname_ip_contract_mismatch')
        site = host.split('-')[0]
        if entry['site'] != site or entry['profile'] != SITE_PROFILES.get(site):
            raise ValidationError('device_profile_mismatch')
        if entry['device_type'] != 'cisco_ios':
            raise ValidationError('unsupported_device_type')
        if type(entry['port']) is not int or not 1 <= entry['port'] <= 65535:
            raise ValidationError('invalid_ssh_port')
        if type(entry['enabled']) is not bool or (entry['enabled'] and host not in MANDATORY):
            raise ValidationError('unexpected_enabled_target')
        devices.append(Device(**entry))
    if not MANDATORY <= names or any(not d.enabled for d in devices if d.hostname in MANDATORY):
        raise ValidationError('mandatory_target_missing_or_disabled')
    return sorted(devices, key=lambda d: d.hostname)


def select_devices(devices, names=(), group=None, include_optional=False, explicit=False):
    if names and group:
        raise ValidationError('choose_devices_or_group')
    if len(set(names)) != len(names):
        raise ValidationError('duplicate_selection')
    if explicit and not names and not group:
        raise ValidationError('explicit_target_required')
    if group and group not in SITE_PROFILES:
        raise ValidationError('unknown_group')
    chosen = [d for d in devices if (d.hostname in names if names else (d.site == group and d.enabled if group else d.enabled))]
    if names and set(names) != {d.hostname for d in chosen}:
        raise ValidationError('unknown_target')
    if not chosen or any(not d.enabled and not (include_optional and d.hostname == OPTIONAL and d.hostname in names) for d in chosen):
        raise ValidationError('target_disabled_or_empty')
    return chosen


@dataclass(frozen=True)
class Baseline:
    ntp_server: str
    banner: str | None = None

    @classmethod
    def read(cls, path: Path, contract: Contract):
        d = load_yaml(path)
        if set(d) != {'version', 'ntp_server', 'banner', 'aaa', 'syslog'} or type(d['version']) is not int or d['version'] != 1:
            raise ValidationError('invalid_baseline_structure')
        if d['ntp_server'] != contract.ntp_server:
            raise ValidationError('unapproved_ntp_server')
        for feature in ['aaa', 'syslog']:
            if d[feature] != {'enabled': False} or type(d[feature]['enabled']) is not bool:
                raise ValidationError(feature + '_requires_external_approval')
        banner = d['banner']
        if banner is not None:
            if (not isinstance(banner, dict) or set(banner) != {'approved', 'text'} or banner['approved'] is not True
                    or not isinstance(banner['text'], str) or not re.fullmatch(r'[\x20-\x7E]{1,500}', banner['text']) or '^' in banner['text']):
                raise ValidationError('unapproved_or_unsafe_banner')
            banner = banner['text']
        return cls(d['ntp_server'], banner)


def running_hostname(running: str) -> str:
    hosts = re.findall(r'^hostname ([A-Za-z0-9-]+)\s*$', running, re.M)
    if len(hosts) != 1:
        raise AutomationError('missing_or_ambiguous_hostname')
    return hosts[0]


def validate_output(output, category='invalid_command_output'):
    if not isinstance(output, str) or not output.strip() or CLI_ERROR.search(output) or '--More--' in output or '\x00' in output:
        raise AutomationError(category)
    return output


def validate_snapshot(device: Device, state: dict):
    for k in ('running', 'interfaces'):
        validate_output(state.get(k), 'incomplete_backup')
    run = state['running'].replace('\r', '')
    if not re.search(r'^end\s*$', run, re.M) or run.strip().splitlines()[-1].strip() != 'end':
        raise AutomationError('truncated_running_config')
    if running_hostname(run) != device.hostname:
        raise AutomationError('hostname_mismatch')
    if not re.search(r'^Interface\s+IP-Address\s+', state['interfaces'], re.M):
        raise AutomationError('invalid_interface_table')
    if not re.search(r'^Vlan99\s+' + re.escape(device.management_ip) + r'\s+.*\bup\s+up\s*$', state['interfaces'], re.M):
        raise AutomationError('management_interface_mismatch_or_down')
    if state.get('vlans') is not None:
        validate_output(state['vlans'])
        if not re.search(r'^VLAN\s+Name\s+', state['vlans'], re.M):
            raise AutomationError('invalid_vlan_table')


def vlan_names(state: dict) -> dict[int, str]:
    names = {}
    lines = state['running'].splitlines()
    for i, line in enumerate(lines):
        m = re.fullmatch(r'vlan (\d+)', line.strip())
        if m and i + 1 < len(lines):
            n = re.fullmatch(r'\s+name (\S+)', lines[i + 1])
            if n: names[int(m.group(1))] = n.group(1)
    for line in (state.get('vlans') or '').splitlines():
        m = re.match(r'^\s*(\d+)\s+(\S+)\s+(?:active|act/unsup|suspended)\b', line)
        if m: names[int(m.group(1))] = m.group(2)
    return names


def banner_text(running: str):
    lines = running.replace('\r', '').splitlines()
    for i, line in enumerate(lines):
        if line.startswith('banner motd '):
            raw = line[len('banner motd '):]
            delimiter = '^C' if raw.startswith('^C') else raw[:1]
            rest = raw[len(delimiter):]
            if delimiter in rest: return rest.split(delimiter)[0]
            parts = [rest] if rest else []
            for other in lines[i+1:]:
                if delimiter in other:
                    if other.split(delimiter)[0]: parts.append(other.split(delimiter)[0])
                    return '\n'.join(parts)
                parts.append(other)
    return None


def change_set(device: Device, baseline: Baseline, contract: Contract, state: dict | None = None) -> list[str]:
    existing = vlan_names(state) if state else {}
    commands = []
    for vlan in contract.profiles[device.profile]:
        if existing.get(vlan) != contract.vlans[vlan]:
            commands += [f'vlan {vlan}', f' name {contract.vlans[vlan]}', 'exit']
    if not state or not re.search(r'^ntp server ' + re.escape(baseline.ntp_server) + r'(?:\s|$)', state['running'], re.M):
        commands += ['ntp server ' + baseline.ntp_server]
    if baseline.banner is not None and (not state or banner_text(state['running']) != baseline.banner):
        commands += ['banner motd ^' + baseline.banner + '^']
    validate_commands(commands, device, baseline, contract)
    return commands


def validate_commands(commands, device, baseline, contract):
    if not isinstance(commands, list) or any(not isinstance(c, str) or '\n' in c or '\r' in c for c in commands):
        raise ValidationError('unsafe_commands')
    i = 0
    while i < len(commands):
        cmd = commands[i]
        m = re.fullmatch(r'vlan (\d+)', cmd)
        if m:
            vlan = int(m.group(1))
            if vlan not in contract.profiles[device.profile] or commands[i:i+3] != [cmd, ' name ' + contract.vlans[vlan], 'exit']:
                raise ValidationError('unauthorized_vlan_commands')
            i += 3
        elif cmd == 'ntp server ' + baseline.ntp_server or (baseline.banner is not None and cmd == 'banner motd ^' + baseline.banner + '^'):
            i += 1
        else:
            raise ValidationError('unauthorized_configuration')


def make_plan(devices, baseline, contract, states=None):
    states = states or {}
    return {'format': 1, 'contract_sha256': contract.fingerprint, 'baseline_sha256': digest(baseline.__dict__),
            'targets': [{'device': d.__dict__, 'state_sha256': digest(states[d.hostname]) if d.hostname in states else None,
                         'commands': change_set(d, baseline, contract, states.get(d.hostname))} for d in devices]}


# Raw configurations belong only in private, ignored runtime directories.
def atomic_write(path: Path, text: str):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.tvi-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf8', newline='\n') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        # link publishes an already-complete file and fails if destination exists.
        # NTFS and local POSIX filesystems support this; no overwrite fallback.
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class ArtifactStore:
    def __init__(self, root: Path = BASE):
        self.root = Path(root).resolve()
        for folder in ('backups', 'states', 'logs', 'reports'):
            target = self.root / folder
            target.mkdir(parents=True, exist_ok=True)
            if target.is_symlink() or target.resolve().parent != self.root:
                raise ValidationError('unsafe_artifact_directory')

    def save(self, device: Device, stage: str, state: dict) -> Path:
        validate_snapshot(device, state)
        if not re.fullmatch(r'[A-Z0-9-]{1,64}', device.hostname) or stage not in {'pre','post','audit','partial'}:
            raise ValidationError('unsafe_artifact_name')
        folder = 'backups' if stage == 'pre' else 'states'
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        for _ in range(5):
            path = self.root / folder / f'{device.hostname}_{stamp}_{stage}_{uuid.uuid4().hex}.json'
            if path.parent.resolve() != self.root / folder:
                raise ValidationError('artifact_path_traversal')
            try:
                atomic_write(path, json.dumps({'hostname':device.hostname, 'stage':stage, 'state':state}, indent=2)+'\n')
                return path
            except FileExistsError:
                continue
        raise AutomationError('backup_collision')

    def event(self, device, mode, success, category, elapsed, paths, changes, partial=False):
        # No free-form exception, command output, credentials or running-config fields.
        entry = {'timestamp':datetime.now(timezone.utc).isoformat(), 'device':device.hostname,
                 'operation':mode, 'success':bool(success), 'error_category':category,
                 'elapsed_seconds':round(elapsed,3), 'backup_paths':[str(p) for p in paths],
                 'changes_applied':changes, 'partial_configuration_possible':partial}
        path = self.root / 'logs' / ('event_' + uuid.uuid4().hex + '.json')
        atomic_write(path, json.dumps(entry,sort_keys=True)+'\n')
        return path


@dataclass(repr=False, frozen=True)
class Credentials:
    username: str
    password: str
    secret: str = ''

    def __repr__(self):
        return 'Credentials(<redacted>)'


def redact(text: str, secrets=()):
    value = str(text)
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        value = value.replace(secret, '<redacted>')
    value = re.sub(r'(?im)^.*\b(?:password|secret|community|isakmp key)\b.*$', '<redacted credential line>', value)
    return value


def netmiko_factory(**kwargs):
    try:
        from netmiko import ConnectHandler
    except ImportError:
        raise AutomationError('netmiko_not_installed') from None
    # Third-party DEBUG logs can contain raw channel/configuration data.
    for name in ('netmiko', 'paramiko'):
        logging.getLogger(name).disabled = True
    return ConnectHandler(**kwargs)


def error_category(exc: Exception):
    if isinstance(exc, AutomationError): return exc.category
    name = type(exc).__name__
    if name in {'NetmikoAuthenticationException','AuthenticationException','BadAuthenticationType','PasswordRequiredException'}:
        return 'authentication_failed'
    if isinstance(exc, TimeoutError) or name in {'NetmikoTimeoutException','ReadTimeout'}: return 'ssh_timeout'
    if name in {'BadHostKeyException','SSHException'}: return 'host_key_or_ssh_transport_failed'
    if isinstance(exc, ConnectionError): return 'connection_failed'
    if isinstance(exc, OSError): return 'filesystem_or_transport_failed'
    if name in {'ConfigInvalidException'}: return 'cisco_cli_error'
    if isinstance(exc, ValueError): return 'privilege_or_validation_failed'
    return 'unexpected_failure'


def connect(device, credentials, factory, known_hosts: Path, attempts=2, delay=time.sleep):
    for attempt in range(attempts):
        try:
            return factory(host=device.management_ip, port=device.port, device_type=device.device_type,
                           username=credentials.username, password=credentials.password, secret=credentials.secret,
                           ssh_strict=True, system_host_keys=False, alt_host_keys=True, alt_key_file=str(known_hosts),
                           conn_timeout=10, auth_timeout=15, banner_timeout=15, read_timeout_override=30,
                           allow_agent=False, use_keys=False)
        except Exception as exc:
            # Retry connection establishment only. Authentication/host-key/config errors are not retried.
            if error_category(exc) not in {'ssh_timeout','connection_failed'} or attempt+1 == attempts:
                raise
            delay(0.25 * (attempt+1))
    raise AutomationError('connection_failed')


def collect(session, device):
    state = {'running':session.send_command('show running-config', read_timeout=30),
             'interfaces':session.send_command('show ip interface brief', read_timeout=30)}
    vlans = session.send_command('show vlan brief', read_timeout=30)
    state['vlans'] = None if CLI_ERROR.search(vlans or '') else vlans
    validate_snapshot(device, state)
    return state


def protected_projection(state, device, baseline, contract):
    """Exclude only owned desired settings; compare every other running-config block."""
    lines = state['running'].replace('\r','').splitlines()
    result, i = [], 0
    while i < len(lines):
        line = lines[i]
        if re.match(r'^(?:Building configuration|Current configuration|! Last configuration|! NVRAM)',line):
            i += 1; continue
        if line == 'ntp server ' + baseline.ntp_server:
            i += 1; continue
        m = re.fullmatch(r'vlan (\d+)', line)
        if m and int(m.group(1)) in contract.profiles[device.profile]:
            i += 1
            while i < len(lines) and lines[i].startswith(' '):
                if not lines[i].strip().startswith('name '): result.append(lines[i])
                i += 1
            continue
        if baseline.banner is not None and line.startswith('banner motd '):
            raw = line[len('banner motd '):]; delimiter = '^C' if raw.startswith('^C') else raw[:1]
            i += 1
            if delimiter not in raw[len(delimiter):]:
                while i < len(lines) and delimiter not in lines[i]: i += 1
                i += 1
            continue
        if line.strip() and line.strip() != '!': result.append(line.rstrip())
        i += 1
    return result


@dataclass
class Result:
    hostname: str
    success: bool = False
    category: str = 'pending'
    changes: int | None = 0
    partial: bool = False
    recovery_capture: str = 'not_needed'
    paths: list = field(default_factory=list)
    state: dict | None = field(default=None, repr=False)

    def summary(self):
        return {k:v for k,v in self.__dict__.items() if k != 'state'}


def validate_review(plan, devices, baseline, contract):
    if not isinstance(plan, dict) or set(plan) != {'format','contract_sha256','baseline_sha256','targets'}:
        raise ValidationError('invalid_review_plan')
    if plan['format'] != 1 or plan['contract_sha256'] != contract.fingerprint or plan['baseline_sha256'] != digest(baseline.__dict__):
        raise ValidationError('review_contract_or_baseline_changed')
    targets = plan['targets']
    if not isinstance(targets,list) or len(targets) != len(devices):
        raise ValidationError('review_target_mismatch')
    for d,t in zip(devices,targets):
        if not isinstance(t,dict) or set(t) != {'device','state_sha256','commands'} or t['device'] != d.__dict__:
            raise ValidationError('review_target_mismatch')
        if not isinstance(t['state_sha256'],str) or not re.fullmatch(r'[0-9a-f]{64}',t['state_sha256']):
            raise ValidationError('audit_based_review_required')
        validate_commands(t['commands'],d,baseline,contract)


def operate(device, mode, baseline, contract, credentials, store, known_hosts, review=None,
            factory=netmiko_factory, delay=time.sleep):
    if mode not in {'audit','apply'}:
        raise ValidationError('invalid_live_mode')
    result = Result(device.hostname)
    start, session, mutated = time.monotonic(), None, False
    try:
        if mode == 'apply': validate_review(review,[device],baseline,contract)
        session = connect(device, credentials, factory, known_hosts, delay=delay)
        prompt = session.find_prompt().strip()
        if prompt not in {device.hostname+'#',device.hostname+'>'}:
            raise AutomationError('hostname_mismatch')
        if not session.check_enable_mode():
            try:
                session.enable()
            except Exception:
                raise AutomationError('privilege_escalation_failed') from None
            if not session.check_enable_mode(): raise AutomationError('privilege_escalation_failed')
        before = collect(session,device)
        result.state = before
        commands = change_set(device,baseline,contract,before)
        if mode == 'apply':
            target = review['targets'][0]
            if target['state_sha256'] != digest(before) or target['commands'] != commands:
                raise AutomationError('stale_or_modified_review')
            if before['vlans'] is None: raise AutomationError('vlan_preflight_unsupported')
        path = store.save(device,'pre' if mode == 'apply' else 'audit',before)
        result.paths.append(str(path))
        if mode == 'audit':
            result.success, result.category = True, 'audited'
        elif not commands:
            result.success, result.category = True, 'compliant_no_changes'
        else:
            validate_commands(commands,device,baseline,contract)
            mutated = True
            response = session.send_config_set(commands,cmd_verify=True,error_pattern=CLI_ERROR.pattern,read_timeout=30)
            validate_output(response,'cisco_cli_error')
            after = collect(session,device)
            result.paths.append(str(store.save(device,'post',after)))
            if change_set(device,baseline,contract,after): raise AutomationError('postcheck_baseline_failed')
            owned = set(contract.profiles[device.profile])
            unowned_before = {v:n for v,n in vlan_names(before).items() if v not in owned}
            unowned_after = {v:n for v,n in vlan_names(after).items() if v not in owned}
            if (unowned_before != unowned_after or protected_projection(before,device,baseline,contract) != protected_projection(after,device,baseline,contract)
                    or before['interfaces'].split() != after['interfaces'].split()):
                raise AutomationError('protected_configuration_changed')
            result.state = after
            result.success, result.category, result.changes = True, 'applied_running_only', len(commands)
    except KeyboardInterrupt:
        result.category, result.partial = 'interrupted', mutated
        if mutated:
            result.changes = None
            result.recovery_capture = 'not_attempted_after_interrupt'
    except Exception as exc:
        result.category, result.partial = error_category(exc), mutated
        if mutated:
            result.changes = None
            try:
                partial_state = collect(session,device)
                result.paths.append(str(store.save(device,'partial',partial_state)))
                result.recovery_capture = 'saved'
            except Exception as recovery_error:
                result.recovery_capture = 'failed:' + error_category(recovery_error)
    finally:
        if session is not None:
            try: session.disconnect()
            except Exception:
                result.success = False
                result.category = 'disconnect_failed'
        try:
            store.event(device,mode,result.success,result.category,time.monotonic()-start,result.paths,result.changes,result.partial)
        except Exception:
            result.success, result.category = False, 'execution_log_write_failed'
    return result


def batch(devices, mode, baseline, contract, credentials, store, known_hosts, review=None, factory=netmiko_factory, delay=time.sleep):
    if mode == 'apply': validate_review(review,devices,baseline,contract)
    results = []
    for i,d in enumerate(devices):
        single_review = dict(review,targets=[review['targets'][i]]) if review else None
        r = operate(d,mode,baseline,contract,credentials,store,known_hosts,single_review,factory,delay)
        results.append(r)
        if r.category == 'interrupted' or (mode == 'apply' and not r.success):
            results.extend(Result(other.hostname,category='not_attempted_after_failure') for other in devices[i+1:])
            break
    code = 130 if any(r.category == 'interrupted' for r in results) else (0 if all(r.success for r in results) else 1)
    return results,code
