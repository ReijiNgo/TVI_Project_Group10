"""Conservative IOS comparisons and scoped inverse commands; no device-wide restore.

Unknown output fails closed. Comparisons deliberately prefer false mismatches to
ignoring real changes. Raw config and original banner text never enter reports.
"""
from __future__ import annotations

import re

from automation_core import AutomationError, validate_output


def config_lines(running):
    """Normalize only known show headers, separators, CRLF and trailing spaces.

    Keep command order, indentation, every non-metadata command and banner body.
    Canonical banner tokens remove delimiter/serialization differences only.
    """
    validate_output(running, 'unsupported_running_config')
    lines = running.replace('\r\n', '\n').splitlines()
    result, i, ended = [], 0, False
    while i < len(lines):
        line = lines[i].rstrip()
        i += 1
        if line.startswith('banner '):
            m = re.fullmatch(r'banner (\S+) (\^C|[^\s\x00-\x1f])(.*)', line)
            if not m: raise AutomationError('unsupported_banner_serialization')
            kind, delimiter, rest = m.groups()
            if delimiter in rest:
                body, tail = rest.split(delimiter, 1)
                if tail: raise AutomationError('unsupported_banner_serialization')
            else:
                parts = [rest] if rest else []
                while i < len(lines) and delimiter not in lines[i]:
                    parts.append(lines[i]); i += 1
                if i == len(lines): raise AutomationError('unterminated_banner')
                last, tail = lines[i].split(delimiter, 1); i += 1
                if tail.strip(): raise AutomationError('unsupported_banner_serialization')
                if last: parts.append(last)
                body = '\n'.join(parts)
            result.append(('banner', kind, body))
            continue
        if (not line or line == '!' or
                re.fullmatch(r'Building configuration\.\.\.|Current configuration\s*:\s*\d+ bytes', line) or
                re.match(r'^! (?:Last configuration change|NVRAM config last updated) ', line)):
            continue
        if ended or '\x1b' in line or '\r' in line or '\t' in line or line.startswith('%'):
            raise AutomationError('unsupported_running_config')
        if line == 'end': ended = True
        result.append(line)
    if not ended: raise AutomationError('unsupported_running_config')
    return result


def vlan_table(output):
    validate_output(output, 'unsupported_vlan_table')
    rows, current = {}, None
    for line in output.replace('\r', '').splitlines():
        if not line.strip() or re.match(r'^VLAN\s+Name\s+Status\s+Ports\s*$', line) or re.fullmatch(r'[-\s]+', line):
            continue
        m = re.fullmatch(r'\s*(\d+)\s+(\S+)\s+(active|act/unsup|suspended|act/lshut|sus/lshut)\s*(.*)', line)
        if m:
            vid, name, status, ports = m.groups(); current = int(vid)
            if current in rows: raise AutomationError('ambiguous_vlan_table')
            rows[current] = {'name':name, 'status':status, 'ports':[]}
        elif current is not None and line.startswith(' '):
            ports = line.strip()
        else: raise AutomationError('unsupported_vlan_table')
        if ports:
            entries = [p.strip() for p in ports.split(',') if p.strip()]
            if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9/.:_-]*', p) for p in entries):
                raise AutomationError('unsupported_vlan_membership')
            rows[current]['ports'].extend(entries)
    if not rows: raise AutomationError('empty_vlan_table')
    for row in rows.values(): row['ports'] = sorted(row['ports'])
    return rows


def interface_table(output):
    validate_output(output, 'unsupported_interface_table')
    rows = {}
    for line in output.replace('\r', '').splitlines():
        if not line.strip() or re.match(r'^Interface\s+IP-Address\s+OK\?\s+Method\s+Status\s+Protocol\s*$', line): continue
        m = re.fullmatch(r'(\S+)\s+(\S+)\s+(YES|NO)\s+(\S+)\s+(administratively down|up|down|reset|deleted)\s+(\S+)\s*', line)
        if not m or m[1] in rows: raise AutomationError('unsupported_interface_table')
        rows[m[1]] = m.groups()[1:]
    if not rows: raise AutomationError('empty_interface_table')
    return rows


def vlan_blocks(state):
    blocks, current = {}, None
    for line in config_lines(state['running']):
        if not isinstance(line, str): current = None; continue
        if line.startswith('vlan '):
            if not re.fullmatch(r'vlan \d+', line): raise AutomationError('unsupported_vlan_config')
            current = int(line.split()[1])
            if current in blocks: raise AutomationError('ambiguous_vlan_config')
            blocks[current] = []
        elif line.startswith(' ') and current is not None: blocks[current].append(line)
        else: current = None
    return blocks


def protected(state, device, baseline, contract):
    result, vlan = [], None
    for line in config_lines(state['running']):
        if isinstance(line, tuple):
            vlan = None
            if line[1] != 'motd' or baseline.banner is None: result.append(line)
            continue
        m = re.fullmatch(r'vlan (\d+)', line)
        if m:
            vlan = int(m[1])
            if vlan not in contract.profiles[device.profile]: result.append(line)
        elif line.startswith(' ') and vlan in contract.profiles[device.profile]:
            # Retain parent identity for every non-name VLAN setting.
            if not line.startswith(' name '): result.append((vlan, line))
        else:
            vlan = None
            if line != 'ntp server ' + baseline.ntp_server: result.append(line)
    return result


def owned(state, device, baseline, contract):
    rows = vlan_table(state['vlans'])
    return {'vlans':{v:rows.get(v, {}).get('name') for v in contract.profiles[device.profile]},
            'ntp':[l for l in config_lines(state['running']) if isinstance(l,str) and
                   re.match(r'^ntp server '+re.escape(baseline.ntp_server)+r'(?:\s|$)',l)],
            'banner':motd(state['running']) if baseline.banner is not None else None}


def motd(running):
    banners = [line[2] for line in config_lines(running) if isinstance(line,tuple) and line[1] == 'motd']
    if len(banners) > 1: raise AutomationError('ambiguous_motd')
    return banners[0] if banners else None


def local_vtp(state):
    return any(line in ('vtp mode transparent','vtp mode off') for line in config_lines(state['running']))


def consistent_vlans(rows, blocks):
    for vid, attrs in blocks.items():
        names = [a[6:] for a in attrs if a.startswith(' name ')]
        if vid not in rows or (names and names != [rows[vid]['name']]):
            raise AutomationError('vlan_sources_disagree')


def verification(before, restored, device, baseline, contract):
    checks = {}
    comparisons = {
        'full_config':lambda s:config_lines(s['running']),
        'owned_state':lambda s:owned(s,device,baseline,contract),
        'protected_state':lambda s:protected(s,device,baseline,contract),
        'interface_state':lambda s:interface_table(s['interfaces']),
        'vlan_state':lambda s:vlan_table(s['vlans']),
    }
    for name, projection in comparisons.items():
        try: checks[name] = 'MATCH' if projection(before) == projection(restored) else 'MISMATCH'
        except (AutomationError, TypeError, KeyError): checks[name] = 'UNVERIFIED'
    checks['raw_running_exact'] = before['running'] == restored['running']
    return checks


def command_units(commands):
    units, i = [], 0
    while i < len(commands):
        size = 3 if commands[i].startswith('vlan ') else 1
        units.append(commands[i:i+size]); i += size
    return units


def banner_command(text):
    # Deliberately reject multiline/control/ambiguous originals before any apply.
    if not re.fullmatch(r'[\x20-\x7e]{1,500}', text):
        raise AutomationError('original_banner_not_safely_restorable')
    delimiter = next((d for d in '^#~|@%' if d not in text), None)
    if delimiter is None: raise AutomationError('original_banner_not_safely_restorable')
    return 'banner motd '+delimiter+text+delimiter


def preflight(before, commands, device, baseline, contract):
    config_lines(before['running']); interface_table(before['interfaces'])
    rows, blocks = vlan_table(before['vlans']), vlan_blocks(before)
    if rows.get(99, {}).get('name') is None: raise AutomationError('management_vlan_missing')
    consistent_vlans(rows,blocks)
    for unit in command_units(commands):
        cmd = unit[0]
        if cmd.startswith('vlan '):
            if not local_vtp(before):
                raise AutomationError('vlan_changes_require_local_vtp_mode')
            vid = int(cmd.split()[1])
            if vid in rows and (not re.fullmatch(r'[A-Za-z0-9_.:-]{1,32}',rows[vid]['name']) or rows[vid]['status'] != 'active'):
                raise AutomationError('original_vlan_not_safely_restorable')
        elif cmd.startswith('banner motd '):
            text = motd(before['running'])
            if text is not None: banner_command(text)


def interface_config(state):
    result, inside = [], False
    for line in config_lines(state['running']):
        if not isinstance(line,str): inside = False; continue
        if not line.startswith(' '): inside = line.startswith('interface ')
        if inside: result.append(line)
    return result


def compensation(before, current, commands, device, baseline, contract):
    """Only restore touched objects in pre/approved intermediate states.

    A concurrent edit is a conflict, never permission to overwrite that edit.
    New VLAN deletion additionally requires no ports, no extra attributes, and
    unchanged interface config. A conflict doesn't prevent other safe inverses.
    """
    old, now = vlan_table(before['vlans']), vlan_table(current['vlans'])
    blocks = vlan_blocks(current)
    consistent_vlans(now,blocks)
    units, conflicts = [], []
    for unit in reversed(command_units(commands)):
        cmd = unit[0]
        if cmd.startswith('vlan '):
            vid = int(cmd.split()[1]); original, actual = old.get(vid), now.get(vid)
            if original == actual: continue
            if not local_vtp(current):
                conflicts.append('vtp_mode_changed'); continue
            expected = {contract.vlans[vid]} if original else {contract.vlans[vid],f'VLAN{vid:04d}'}
            if actual is None or actual['name'] not in expected:
                conflicts.append('vlan_concurrent_or_missing'); continue
            if original is not None:
                if actual['status'] != original['status'] or actual['ports'] != original['ports']:
                    conflicts.append('vlan_membership_changed'); continue
                original_attrs = vlan_blocks(before).get(vid,[])
                rename = (' no name' if original['name'] == f'VLAN{vid:04d}' and
                          not any(a.startswith(' name ') for a in original_attrs) else ' name '+original['name'])
                units.append([f'vlan {vid}',rename,'exit'])
            elif (actual['status'] != 'active' or actual['ports'] or
                  any(not a.startswith(' name ') for a in blocks.get(vid,[])) or
                  interface_config(before) != interface_config(current)):
                conflicts.append('new_vlan_not_safe_to_remove')
            else: units.append([f'no vlan {vid}'])
        elif cmd.startswith('ntp server '):
            old_ntp = owned(before,device,baseline,contract)['ntp']
            new_ntp = owned(current,device,baseline,contract)['ntp']
            if old_ntp == new_ntp: continue
            if not old_ntp and new_ntp == [cmd]: units.append(['no '+cmd])
            else: conflicts.append('ntp_concurrent_change')
        elif cmd.startswith('banner motd '):
            previous, actual = motd(before['running']), motd(current['running'])
            if previous == actual: continue
            if actual != baseline.banner: conflicts.append('banner_concurrent_change'); continue
            units.append(['no banner motd'] if previous is None else [banner_command(previous)])
    return units, conflicts


def safe_commands(commands):
    return ['banner motd <redacted>' if c.startswith('banner motd ') else c for c in commands]


def diff_summary(before, restored):
    """Counts only: even a redacted textual diff could disclose private banner data."""
    import difflib
    a, b = config_lines(before['running']), config_lines(restored['running'])
    removed = added = 0
    for tag, i, j, k, l in difflib.SequenceMatcher(a=a,b=b,autojunk=False).get_opcodes():
        if tag != 'equal': removed += j-i; added += l-k
    return {'canonical_lines_removed':removed,'canonical_lines_added':added,
            'config_content_included':False}
