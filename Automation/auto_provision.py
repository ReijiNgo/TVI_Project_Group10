"""Windows-compatible CLI. plan is offline; live changes require a state-bound audit review."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from automation_core import (BASE, ArtifactStore, AutomationError, Baseline, Contract, Credentials,
                             ValidationError, atomic_write, batch, load_inventory, make_plan,
                             select_devices, validate_review)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('plan','audit','apply'),default='plan')
    p.add_argument('--inventory',type=Path,default=BASE/'inventory.yaml')
    p.add_argument('--baseline',type=Path,default=BASE/'config/baseline.yaml')
    p.add_argument('--device',action='append',default=[],help='Exact hostname; repeat for a reviewed explicit batch')
    p.add_argument('--group',choices=('HCMC','HANOI','DANANG'))
    p.add_argument('--include-optional',action='store_true',help='Allow an explicitly named disabled optional target')
    p.add_argument('--confirm',action='store_true',help='Authorize only the supplied, state-bound review plan')
    p.add_argument('--review-plan',type=Path)
    p.add_argument('--known-hosts',type=Path,default=Path.home()/'.ssh/known_hosts')
    p.add_argument('--artifact-root',type=Path,default=BASE)
    p.add_argument('--out',type=Path,help='New JSON plan file inside artifact-root/reports; never overwrite')
    return p


def credentials():
    username = os.environ.get('TVI_SSH_USERNAME')
    password = os.environ.get('TVI_SSH_PASSWORD')
    if not username:
        if not sys.stdin.isatty(): raise ValidationError('ssh_username_required')
        username = input('SSH username: ').strip()
    if not password:
        if not sys.stdin.isatty(): raise ValidationError('ssh_password_required')
        password = getpass.getpass('SSH password: ')
    if not username or not password: raise ValidationError('empty_credentials')
    # Optional enable secret is never implicitly changed on a device.
    secret = os.environ.get('TVI_ENABLE_SECRET','')
    if not secret and sys.stdin.isatty():
        secret = getpass.getpass('Enable secret (Enter if unnecessary): ')
    return Credentials(username,password,secret)


def emit_plan(plan, out, artifact_root):
    encoded = json.dumps(plan,indent=2,sort_keys=True)+'\n'
    if out:
        target = out if out.is_absolute() else BASE/out
        allowed = (artifact_root.resolve()/'reports').resolve()
        if target.resolve().parent != allowed or target.name in {'.','..','.gitkeep'}:
            raise ValidationError('plan_output_must_be_inside_reports')
        atomic_write(target,encoded)
    else:
        print(encoded,end='')


def main(argv=None, *, factory=None, credential_provider=credentials):
    args = parser().parse_args(argv)
    try:
        contract = Contract.read()
        devices = load_inventory(args.inventory,contract)
        chosen = select_devices(devices,args.device,args.group,args.include_optional,explicit=args.mode=='apply')
        baseline = Baseline.read(args.baseline,contract)
        if args.mode != 'apply' and (args.confirm or args.review_plan):
            raise ValidationError('apply_flags_in_readonly_mode')
        if args.mode == 'plan':
            emit_plan(make_plan(chosen,baseline,contract),args.out,args.artifact_root)
            return 0
        review = None
        if args.mode == 'apply':
            if not args.confirm or not args.review_plan:
                raise ValidationError('confirmation_and_audit_review_required')
            try: review = json.loads(args.review_plan.read_text(encoding='utf-8-sig'))
            except (OSError,ValueError): raise ValidationError('invalid_review_file') from None
            validate_review(review,chosen,baseline,contract)
        if not args.known_hosts.is_file() or not args.known_hosts.read_text(encoding='utf8').strip():
            raise ValidationError('verified_known_hosts_required')
        store = ArtifactStore(args.artifact_root)
        creds = credential_provider()
        kwargs = {'factory':factory} if factory else {}
        results,code = batch(chosen,args.mode,baseline,contract,creds,store,args.known_hosts,review,**kwargs)
        payload={'operation':args.mode,'results':[r.summary() for r in results],'exit_code':code}
        if args.mode == 'audit' and code == 0:
            audit_plan=make_plan(chosen,baseline,contract,{r.hostname:r.state for r in results})
            if args.out: emit_plan(audit_plan,args.out,args.artifact_root)
            else: payload['review']=audit_plan
        print(json.dumps(payload,indent=2))
        return code
    except KeyboardInterrupt:
        print('ERROR: interrupted',file=sys.stderr)
        return 130
    except (AutomationError,OSError) as exc:
        category = exc.category if isinstance(exc,AutomationError) else 'local_filesystem_failed'
        print('ERROR: '+category,file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
