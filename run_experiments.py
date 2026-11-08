"""Serial, cold-cache DDS comparison; run from the DDS repository root."""
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
for directory in ('results', 'logs'):
    (ROOT / directory).mkdir(parents=True, exist_ok=True)
if hasattr(os, 'sched_getaffinity'):
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})

def run(variant, tag, deals=200, seed=5197319, cards=13, solutions=1, reference=None):
    path = ROOT / 'results' / f'{tag}_{variant}.csv'
    start = time.perf_counter()
    with path.open('w') as out:
        subprocess.run([str(ROOT/'bin'/variant), str(deals), str(seed), str(cards), str(solutions)], stdout=out, check=True)
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == 5 * deals
    if reference is not None:
        assert len(rows) == len(reference)
        for a, b in zip(reference, rows):
            for field in ['deal', 'strain', 'cards', 'first', 'score', 'signature']:
                if a[field] != b[field]:
                    raise AssertionError(f'{variant}: {field} mismatch: {a} vs {b}')
            if variant in ['baseline', 'compact', 'winners', 'compact_winners']:
                assert a['trick_nodes'] == b['trick_nodes'], (variant, 'node count changed', a, b)
    summary = dict(variant=variant, tag=tag, cases=len(rows), elapsed_s=time.perf_counter()-start,
                   solve_s=sum(int(r['nanoseconds']) for r in rows)/1e9,
                   trick_nodes=sum(int(r['trick_nodes']) for r in rows))
    summary['nt_s'] = sum(int(r['nanoseconds']) for r in rows if r['strain']=='4')/1e9
    summary['nt_nodes'] = sum(int(r['trick_nodes']) for r in rows if r['strain']=='4')
    with (ROOT/'results'/'run_log.jsonl').open('a') as f: f.write(json.dumps(summary)+'\n')
    print(json.dumps(summary), flush=True)
    return rows

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv)>1 else 'screen'
    if mode == 'screen':
        reference = None
        for repeat, order in enumerate([
            ['baseline', 'compact', 'winners', 'runs'],
            ['runs', 'winners', 'compact', 'baseline'],
        ]):
            for variant in order:
                rows = run(variant, f'full_r{repeat}', reference=reference)
                if reference is None: reference = rows
    elif mode == 'small':
        reference = run('baseline', 'small', deals=2000, seed=821773, cards=0, solutions=3)
        for variant in sys.argv[2:]:
            run(variant, 'small', deals=2000, seed=821773, cards=0, solutions=3, reference=reference)
    elif mode == 'confirm':
        reference = None
        variants = sys.argv[2:]
        for repeat, order in enumerate([['baseline']+variants, list(reversed(variants))+['baseline']]):
            for variant in order:
                rows = run(variant, f'holdout_r{repeat}', deals=200, seed=2077111, reference=reference)
                if reference is None: reference = rows
    elif mode == 'known':
        for variant in sys.argv[2:]:
            with (ROOT/'logs'/f'known_{variant}.log').open('w') as f:
                subprocess.run([str(ROOT/'bin'/f'dtest_{variant}'),'-f','hands/list1000.txt','-s','solve','-n','1'],stdout=f,stderr=subprocess.STDOUT,check=True)
            print(f'{variant}: all root scores matched 1,000 reference deals',flush=True)
