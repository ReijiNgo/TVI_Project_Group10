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
    from rollback import config_lines
    names = {}
    lines = [line for line in config_lines(state['running']) if isinstance(line,str)]
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
    from rollback import config_lines, motd
    existing = vlan_names(state) if state else {}
    commands = []
    for vlan in contract.profiles[device.profile]:
        if existing.get(vlan) != contract.vlans[vlan]:
            commands += [f'vlan {vlan}', f' name {contract.vlans[vlan]}', 'exit']
    if not state or not any(isinstance(line,str) and re.match(r'^ntp server ' + re.escape(baseline.ntp_server) + r'(?:\s|$)', line)
                            for line in config_lines(state['running'])):
        commands += ['ntp server ' + baseline.ntp_server]
    if baseline.banner is not None and (not state or motd(state['running']) != baseline.banner):
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
        if not re.fullmatch(r'[A-Z0-9-]{1,64}', device.hostname) or stage not in {'pre','post','audit','partial','restored','demo_changed'}:
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

    def verify_prebackup(self, path, state):
        """Publish human-readable private backup and read both files back before write."""
        if json.loads(path.read_text(encoding='utf8'))['state'] != state:
            raise AutomationError('backup_readback_failed')
        cfg = path.with_suffix('.cfg')
        atomic_write(cfg, state['running'])
        if cfg.read_text(encoding='utf8') != state['running'].replace('\r\n','\n'):
            raise AutomationError('backup_readback_failed')
        return cfg

    def recovery_report(self, device, operation_id, report):
        path = self.root / 'reports' / f'{device.hostname}_{operation_id}_rollback_report.json'
        if path.parent.resolve() != self.root / 'reports':
            raise ValidationError('artifact_path_traversal')
        atomic_write(path, json.dumps(report,indent=2,sort_keys=True)+'\n')
        return path

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
    recovery_status: str = 'not_needed'
    rollback_attempted: bool = False
    mutation_observed: bool | None = False
    verification: dict = field(default_factory=dict)
    backup_cfg: str | None = None
    report_path: str | None = None
    evidence_error: str | None = None
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


def authorize_session(session, device):
    prompt = session.find_prompt().strip()
    if prompt not in {device.hostname+'#',device.hostname+'>'}:
        raise AutomationError('hostname_mismatch')
    if not session.check_enable_mode():
        try: session.enable()
        except Exception: raise AutomationError('privilege_escalation_failed') from None
        if not session.check_enable_mode(): raise AutomationError('privilege_escalation_failed')


def operate(device, mode, baseline, contract, credentials, store, known_hosts, review=None,
            factory=netmiko_factory, delay=time.sleep, *, demo=False, progress=None):
    from rollback import (command_units, compensation, diff_summary, interface_table,
                          owned, preflight, protected, safe_commands, verification, vlan_table)
    if mode not in {'audit','apply'}:
        raise ValidationError('invalid_live_mode')
    result = Result(device.hostname)
    start, session, mutated = time.monotonic(), None, False
    started = datetime.now(timezone.utc).isoformat()
    operation_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'_'+uuid.uuid4().hex
    before, pre_path, restored_path, restored_state = None, None, None, None
    attempted, recovery_errors, conflicts = [], [], []
    demo_injected, demo_proof, logged = False, None, False

    def say(message):
        # A broken console/progress sink must never prevent device recovery.
        if progress:
            try: progress(message)
            except Exception: pass

    def send(commands_to_send):
        response = session.send_config_set(commands_to_send,cmd_verify=True,
                                           error_pattern=CLI_ERROR.pattern,read_timeout=30)
        validate_output(response,'cisco_cli_error')

    def recovery_read(reconnect=False):
        nonlocal session
        if not reconnect:
            try:
                # Netmiko can raise before its normal exit_config_mode call.
                session.exit_config_mode()
                authorize_session(session,device)
                return collect(session,device)
            except Exception:
                pass
        if session is not None:
            try: session.disconnect()
            except Exception: pass
        session = connect(device,credentials,factory,known_hosts,delay=delay)
        authorize_session(session,device)
        return collect(session,device)

    def recover():
        nonlocal restored_path, restored_state, conflicts
        result.success, result.changes = False, None
        result.rollback_attempted, result.recovery_status = True, 'unverified'
        result.mutation_observed = None
        result.verification = {k:'UNVERIFIED' for k in ('full_config','owned_state','protected_state','interface_state','vlan_state')}
        try:
            say('[5/7] Starting automatic rollback of Step 9-owned settings')
            current = recovery_read()
            result.mutation_observed = owned(before,device,baseline,contract) != owned(current,device,baseline,contract)
            try:
                result.paths.append(str(store.save(device,'partial',current)))
                result.recovery_capture = 'saved'
            except Exception as exc:
                result.recovery_capture = 'failed:'+error_category(exc)
            for attempt in range(2):
                inverses, conflicts = compensation(before,current,attempted,device,baseline,contract)
                try:
                    for inverse in inverses: send(inverse)
                    break
                except Exception as exc:
                    category = error_category(exc)
                    recovery_errors.append(category)
                    if category not in {'ssh_timeout','connection_failed','host_key_or_ssh_transport_failed','filesystem_or_transport_failed'} or attempt:
                        break
                    # An ambiguous write is never replayed blindly. Reconnect and
                    # derive remaining inverses from the device's actual state.
                    current = recovery_read(reconnect=True)
            say('[6/7] Re-auditing restored device configuration')
            restored = recovery_read()
            restored_state = restored
            result.verification = verification(before,restored,device,baseline,contract)
            try:
                restored_path = str(store.save(device,'restored',restored))
                result.paths.append(restored_path)
            except Exception as exc:
                result.evidence_error = 'restored_snapshot:'+error_category(exc)
            required = ('full_config','owned_state','protected_state','interface_state','vlan_state')
            matches = all(result.verification.get(k) == 'MATCH' for k in required)
            # Recovered transient transport failures are acceptable only with all
            # comparisons and a durable restored snapshot; CLI rejection is not.
            rejected = any(e not in {'ssh_timeout','connection_failed','host_key_or_ssh_transport_failed','filesystem_or_transport_failed'} for e in recovery_errors)
            if matches and not conflicts and not rejected and restored_path:
                result.recovery_status, result.state = 'verified', restored
            elif any(result.verification.get(k) == 'MISMATCH' for k in required) or rejected or conflicts:
                result.recovery_status = 'incomplete'
            for key in required: say('      '+key+': '+result.verification[key])
        except (Exception, KeyboardInterrupt) as exc:
            recovery_errors.append('recovery_interrupted' if isinstance(exc,KeyboardInterrupt) else error_category(exc))
            result.recovery_status = 'unverified'

    try:
        if demo and (mode != 'apply' or device.hostname not in MANDATORY):
            raise ValidationError('demo_requires_one_approved_device')
        if mode == 'apply': validate_review(review,[device],baseline,contract)
        say('[1/7] Connecting to '+device.hostname)
        session = connect(device, credentials, factory, known_hosts, delay=delay)
        authorize_session(session,device)
        say('[2/7] Capturing initial device configuration')
        before = collect(session,device)
        result.state = before
        commands = change_set(device,baseline,contract,before)
        if mode == 'apply':
            target = review['targets'][0]
            if target['state_sha256'] != digest(before) or target['commands'] != commands:
                raise AutomationError('stale_or_modified_review')
            if before['vlans'] is None: raise AutomationError('vlan_preflight_unsupported')
            preflight(before,commands,device,baseline,contract)
            if demo and not commands: raise AutomationError('demo_requires_safe_pending_change')
        path = store.save(device,'pre' if mode == 'apply' else 'audit',before)
        result.paths.append(str(path))
        if mode == 'apply':
            pre_path = str(path)
            result.backup_cfg = str(store.verify_prebackup(path,before))
            say('      PRE-BACKUP SAVED (JSON and CFG readback verified)')
            say('[3/7] Validating reviewed change set: REVIEW APPROVED')
        if mode == 'audit':
            result.success, result.category = True, 'audited'
        elif not commands:
            result.success, result.category = True, 'compliant_no_changes'
        else:
            validate_commands(commands,device,baseline,contract)
            say('[4/7] Applying authorized configuration')
            attempted = command_units(commands)[0] if demo else commands[:]
            mutated = True
            send(attempted)
            if demo:
                changed = collect(session,device)
                # Readback, not command echo, must prove the authorized unit took effect.
                if (owned(before,device,baseline,contract) == owned(changed,device,baseline,contract) or
                        protected(before,device,baseline,contract) != protected(changed,device,baseline,contract) or
                        interface_table(before['interfaces']) != interface_table(changed['interfaces']) or
                        any(c in change_set(device,baseline,contract,changed) for c in attempted if c != 'exit')):
                    raise AutomationError('demo_change_not_proven')
                demo_proof = str(store.save(device,'demo_changed',changed))
                result.paths.append(demo_proof)
                demo_injected = True
                say('      Authorized change readback verified; CONTROLLED FAILURE INJECTED')
                raise AutomationError('controlled_demo_failure')
            after = collect(session,device)
            result.paths.append(str(store.save(device,'post',after)))
            if change_set(device,baseline,contract,after): raise AutomationError('postcheck_baseline_failed')
            old_vlans, new_vlans = vlan_table(before['vlans']), vlan_table(after['vlans'])
            profile = contract.profiles[device.profile]
            if (any(new_vlans.get(v) != row for v,row in old_vlans.items() if v not in profile) or
                    any(v not in old_vlans and v not in profile for v in new_vlans) or
                    any(v in profile and (new_vlans.get(v,{}).get('ports') != row['ports'] or new_vlans.get(v,{}).get('status') != row['status']) for v,row in old_vlans.items()) or
                    any(row['ports'] or row['status'] != 'active' for v,row in new_vlans.items() if v not in old_vlans) or
                    protected(before,device,baseline,contract) != protected(after,device,baseline,contract) or
                    interface_table(before['interfaces']) != interface_table(after['interfaces'])):
                raise AutomationError('protected_configuration_changed')
            result.state = after
            result.mutation_observed = owned(before,device,baseline,contract) != owned(after,device,baseline,contract)
            result.success, result.category, result.changes = True, 'applied_running_only', len(commands)
        try:
            store.event(device,mode,True,result.category,time.monotonic()-start,result.paths,result.changes)
            logged = True
        except Exception: raise AutomationError('execution_log_write_failed') from None
    except (Exception, KeyboardInterrupt) as exc:
        result.success = False
        result.category, result.partial = ('interrupted' if isinstance(exc,KeyboardInterrupt) else error_category(exc)), mutated
        if mutated: recover()
    finally:
        if session is not None:
            try: session.disconnect()
            except Exception:
                if result.success:
                    result.success, result.category, result.partial = False, 'disconnect_failed', mutated
                    if mutated: recover()
                result.evidence_error = 'disconnect_failed'
                try: session.disconnect()
                except Exception: pass
        if mode == 'apply':
            say('[7/7] Saving transaction and recovery evidence')
            report = {'hostname':device.hostname,'operation_id':operation_id,'started_at':started,
                      'ended_at':datetime.now(timezone.utc).isoformat(),'pre_snapshot':pre_path,
                      'pre_config':result.backup_cfg,'restored_snapshot':restored_path,
                      'snapshot_paths':result.paths,'authorized_commands_submitted':safe_commands(attempted),
                      'applied_command_count':result.changes,'failure_category':None if result.success else result.category,
                      'mutation_possible':mutated,'mutation_observed':result.mutation_observed,
                      'rollback_attempted':result.rollback_attempted,'recovery_status':result.recovery_status,
                      'apply_success':result.success,'verification':result.verification,
                      'recovery_errors':recovery_errors,'conflicts':conflicts,'partial_capture':result.recovery_capture,
                      'diff_summary':{'available':False,'config_content_included':False},
                      'evidence_error':result.evidence_error,'demo_requested':demo,
                      'controlled_failure_injected':demo_injected,'demo_changed_snapshot':demo_proof,
                      'limitations':['No IOS parser certification or end-to-end traffic test. Output comparison covers collected state only.',
                                     'No concurrent writers permitted. Unknown output or missing snapshots prevents strict verification.'],
                      'manual_steps':[] if result.success or result.recovery_status == 'verified' or not mutated else
                          ['Stop batch and concurrent writers. Keep console access. Inspect private pre/partial/restored snapshots.',
                           'Restore only unresolved owned objects from pre.cfg; preserve foreign changes. Re-audit before any new apply.',
                           'Do not reload, erase, save startup-config or perform whole-device replacement as an automatic fallback.']}
            if restored_path:
                try: report['diff_summary'] = diff_summary(before,restored_state)
                except Exception: report['diff_summary'] = {'available':False,'config_content_included':False}
            try: result.report_path = str(store.recovery_report(device,operation_id,report))
            except (Exception,KeyboardInterrupt):
                result.evidence_error = 'recovery_report_write_failed'
                if result.success and mutated:
                    result.success, result.category, result.partial = False, 'recovery_report_write_failed', True
                    recover()
                    try: session.disconnect()
                    except Exception: pass
                if result.recovery_status == 'verified': result.recovery_status = 'unverified'
                result.success = False
        if not logged or not result.success:
            try: store.event(device,mode,result.success,result.category,time.monotonic()-start,result.paths,result.changes,result.partial)
            except Exception:
                result.evidence_error = 'execution_log_write_failed'
                result.success = False
        if demo:
            say('FINAL STATUS: '+('APPLY SUCCESSFUL' if result.success else
                'APPLY FAILED / '+{'verified':'ROLLBACK VERIFIED','incomplete':'RECOVERY FAILED',
                                  'unverified':'RECOVERY UNVERIFIED','not_needed':'ROLLBACK UNNECESSARY'}[result.recovery_status]))
    return result


def batch(devices, mode, baseline, contract, credentials, store, known_hosts, review=None, factory=netmiko_factory, delay=time.sleep, *, demo=False, progress=None):
    if demo and (mode != 'apply' or len(devices) != 1 or devices[0].hostname not in MANDATORY):
        raise ValidationError('demo_requires_one_approved_device')
    if mode == 'apply': validate_review(review,devices,baseline,contract)
    results = []
    for i,d in enumerate(devices):
        single_review = dict(review,targets=[review['targets'][i]]) if review else None
        r = operate(d,mode,baseline,contract,credentials,store,known_hosts,single_review,factory,delay,demo=demo,progress=progress)
        results.append(r)
        if r.category == 'interrupted' or (mode == 'apply' and not r.success):
            results.extend(Result(other.hostname,category='not_attempted_after_failure') for other in devices[i+1:])
            break
    code = 130 if any(r.category == 'interrupted' for r in results) else (0 if all(r.success for r in results) else 1)
    return results,code
