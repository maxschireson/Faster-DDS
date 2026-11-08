"""Validate a complete benchmark run and summarize paired batch timings."""
import argparse
import collections
import csv
import json
import statistics
from pathlib import Path


def analyze(prefix, families, repeats):
    rows = list(csv.DictReader(Path(str(prefix) + '.csv').open()))
    grouped = collections.defaultdict(list)
    for row in rows:
        key = tuple(int(row[k]) for k in ('family', 'constraint', 'size', 'variant'))
        grouped[key].append(row)
    sizes = sorted({int(row['size']) for row in rows})
    assert len(rows) == families * 3 * len(sizes) * 5 * repeats
    for key, group in grouped.items():
        assert len(group) == repeats, (key, len(group))
        assert len({row['nodes'] for row in group}) == 1, (key, 'nondeterministic nodes')
    hands = list(csv.DictReader(Path(str(prefix) + '_hands.csv').open()))
    scored = list(csv.DictReader(Path(str(prefix) + '_scores.csv').open()))
    maximum = max(sizes)
    assert len(hands) == len(scored) == families * 3 * maximum
    pools = {}
    allocations = collections.defaultdict(set)
    for row in hands:
        group = (int(row['family']), int(row['constraint']))
        hands4 = [[int(row[f'h{h}s{s}']) for s in range(4)] for h in range(4)]
        counts = [sum(mask.bit_count() for mask in hand) for hand in hands4]
        assert len(set(counts)) == 1
        for s in range(4):
            assert sum(hand[s].bit_count() for hand in hands4) == \
                (hands4[0][s] | hands4[1][s] | hands4[2][s] | hands4[3][s]).bit_count()
        invariant = (tuple(hands4[0]), tuple(hands4[2]),
                     tuple(hands4[1][s] | hands4[3][s] for s in range(4)))
        assert pools.setdefault(group, invariant) == invariant
        allocations[group].add(tuple(hands4[1]))
    if int(rows[0]['cards']) >= 10:
        assert all(len(values) == maximum for values in allocations.values())
    summary = {'families': families, 'layouts': len(hands), 'repeats': repeats,
               'cohorts': [], 'by_constraint': [], 'by_size': []}
    for fi in range(families):
        for constraint in range(3):
            values = [statistics.mean(float(r['total_ms']) for r in
                      grouped[fi, constraint, maximum, variant]) / 1000 for variant in range(5)]
            summary['cohorts'].append(dict(family=fi, constraint=constraint, seconds=values,
                speedup_vs_cold=[values[0] / value for value in values]))
    for constraint in range(3):
        cohorts = [c for c in summary['cohorts'] if c['constraint'] == constraint]
        values = [sum(c['seconds'][v] for c in cohorts) for v in range(5)]
        summary['by_constraint'].append(dict(constraint=constraint, seconds=values,
            speedup_vs_cold=[values[0] / value for value in values]))
    for size in sizes:
        values = [sum(statistics.mean(float(r['total_ms']) for r in grouped[fi, c, size, v])
                      for fi in range(families) for c in range(3)) / 1000 for v in range(5)]
        summary['by_size'].append(dict(size=size, seconds=values,
            speedup_vs_cold=[values[0] / value for value in values]))
    Path(str(prefix) + '_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('prefix', type=Path)
    parser.add_argument('--families', type=int, default=6)
    parser.add_argument('--repeats', type=int, default=2)
    args = parser.parse_args()
    analyze(args.prefix, args.families, args.repeats)
