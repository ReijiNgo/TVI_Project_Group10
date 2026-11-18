"""Run unittest and record exact per-suite outcomes as ignored local QA evidence."""
import io
import json
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path

BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'tests'))


def main():
    suites=[];transcript=[]
    for filename in sorted((BASE/'tests').glob('test_*.py')):
        suite=unittest.defaultTestLoader.discover(str(BASE/'tests'),pattern=filename.name)
        buffer=io.StringIO()
        result=unittest.TextTestRunner(stream=buffer,verbosity=2).run(suite)
        row={'suite':filename.stem,'total':result.testsRun,
             'passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
             'failed':len(result.failures)+len(result.errors),'skipped':len(result.skipped)}
        suites.append(row);transcript.append(buffer.getvalue())
        print(json.dumps(row))
    report={'timestamp':datetime.now(timezone.utc).isoformat(),'suites':suites,
            'total':sum(s['total'] for s in suites),'passed':sum(s['passed'] for s in suites),
            'failed':sum(s['failed'] for s in suites),'skipped':sum(s['skipped'] for s in suites),
            'runtime':'NOT RUN; all SSH sessions in tests are fake'}
    folder=BASE/'reports';folder.mkdir(exist_ok=True)
    (folder/'offline-test-results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    (folder/'offline-tests.txt').write_text('\n'.join(transcript),encoding='utf8')
    if report['failed']:print('\n'.join(transcript),file=sys.stderr)
    return 1 if report['failed'] or not report['total'] else 0


if __name__=='__main__':raise SystemExit(main())
