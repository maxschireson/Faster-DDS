"""Run serially on one allowed CPU; invoke from the patched DDS checkout."""
import argparse
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--binary', default='bazel-bin/benchmarks/related_batch_benchmark')
parser.add_argument('--prefix', default='results/related_batch')
parser.add_argument('--families', type=int, default=6)
parser.add_argument('--layouts', type=int, default=1000)
parser.add_argument('--repeats', type=int, default=2)
parser.add_argument('--cards', type=int, default=13)
parser.add_argument('--seed', type=int, default=20261118)
args = parser.parse_args()
prefix = Path(args.prefix)
prefix.parent.mkdir(parents=True, exist_ok=True)
if hasattr(os, 'sched_getaffinity'):
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
command = [args.binary, str(args.families), str(args.layouts), str(args.repeats),
           str(args.cards), str(args.seed), str(prefix)]
with Path(str(prefix) + '.csv').open('w') as output:
    subprocess.run(command, stdout=output, check=True)
