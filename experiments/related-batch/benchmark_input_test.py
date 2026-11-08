"""Check corpus selection and prevent duplicate-driven benchmark speedups."""
import csv
import io
import subprocess
import sys
import tempfile
from pathlib import Path

binary = str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory() as directory:
    prefix = str(Path(directory) / 'sample')
    result = subprocess.run([binary, '1', '128', '1', '7', '20261118', prefix, '0', '6'],
                            text=True, capture_output=True, check=True)
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert {r['constraint'] for r in rows} == {'0'}, 'constraint filter ignored'
    assert {r['variant'] for r in rows} == set('012345'), 'ablation variant missing'
    assert all(r['root_proofs'] == '0' for r in rows if r['variant'] == '5')
    hands = list(csv.DictReader(open(prefix + '_hands.csv')))
    assert len(hands) == 128
    assert len({tuple(r[f'h1s{s}'] for s in range(4)) for r in hands}) == 128
    impossible = subprocess.run([binary, '1', '3', '1', '1', '20261118', prefix, '0'],
                                capture_output=True, timeout=10)
    assert impossible.returncode != 0, 'impossible unique corpus accepted'
print('Benchmark corpus checks passed')
