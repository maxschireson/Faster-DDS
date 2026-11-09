"""Scavenge self-play DDS requests and train a target-conditioned proof ranker.

Only NumPy is needed. No writes to a production cache or self-play directory.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import random
import time
import numpy as np

INPUTS, HIDDEN, OUTPUTS = 427, 64, 104


def features(key, legal):
    x = np.zeros(INPUTS, np.float32)
    actor = (key[17] + key[18]) % 4
    for relative in range(4):
        for suit in range(4):
            bits = key[4 * ((actor + relative) % 4) + suit]
            for rank in range(13):
                x[relative * 52 + suit * 13 + rank] = (bits >> rank) & 1
    for i in range(key[18]):
        card = key[21 + i]
        x[208 + i * 52 + (card // 16) * 13 + card % 16 - 2] = 1
    x[364 + key[19]] = 1
    x[369 + key[18]] = 1
    remaining = (key[24] + 7) // 4
    residual = key[16] if key[16] < 32768 else key[16] - 65536
    is_max = (actor % 2 == 0) == bool(key[20])
    need = residual if is_max else remaining - residual + 1
    x[373:375] = [need / 13, remaining / 13]
    x[375 + np.asarray(legal, dtype=int)] = 1
    return x


def split_families(families):
    ordered = sorted(set(families), key=lambda f: hashlib.sha256(f.encode()).digest())
    if len(ordered) < 3:
        raise ValueError('At least three independent board families are required')
    n = max(1, len(ordered) // 10)
    return {f: ('test' if i < n else 'validation' if i < 2 * n else 'train')
            for i, f in enumerate(ordered)}


def prepare_roots(boards, per_family, seed, min_cards=1):
    rng = random.Random(seed)
    seen, roots = set(), []
    for board in sorted(boards, key=lambda b: b['family']):
        candidates = []
        for query in board['queries']:
            if query.get('future_tricks', 13) < min_cards:
                continue
            for world in query['worlds']:
                key = [0] * 26
                for seat, hand in enumerate(world):
                    for c in hand:
                        key[seat * 4 + c // 13] |= 1 << (c % 13)
                key[17:21] = [query['leader'], len(query['trick']), query['trump'], 1]
                for i, (_, c) in enumerate(query['trick']):
                    key[21 + i] = 16 * (c // 13) + c % 13 + 2
                key[24] = sum(map(len, world)) - 4
                identity = tuple(key)
                if identity in seen:
                    continue
                seen.add(identity)
                candidates.append(dict(family=board['family'], key=key,
                    board_index=board.get('index'), ply=query.get('ply'),
                    kind=query.get('kind'), player=query.get('player')))
        rng.shuffle(candidates)
        roots.extend(candidates[:per_family])
    return roots


def initialize(seed):
    rng = np.random.default_rng(seed)
    weights = [rng.normal(0, np.sqrt(2 / INPUTS), (INPUTS, HIDDEN)).astype(np.float32),
               np.zeros(HIDDEN, np.float32),
               rng.normal(0, 0.04, (HIDDEN, OUTPUTS)).astype(np.float32),
               np.concatenate([np.zeros(52), np.full(52, 3)]).astype(np.float32)]
    return dict(w=weights, m=[np.zeros_like(w) for w in weights],
                v=[np.zeros_like(w) for w in weights], step=0)


def forward(model, x):
    w, b, v, c = model['w']
    h = np.maximum(0, x @ w + b)
    return h @ v + c, h


def train_step(model, x, success, cost, mask, learning_rate=0.001):
    z, h = forward(model, x)
    probability = 1 / (1 + np.exp(-np.clip(z[:, :52], -30, 30)))
    denominator = max(float(mask.sum()), 1)
    delta = z[:, 52:] - cost
    bce = np.logaddexp(0, z[:, :52]) - success * z[:, :52]
    huber = np.where(abs(delta) < 1, delta ** 2 / 2, abs(delta) - 0.5)
    loss = float(((bce + 0.25 * huber) * mask).sum() / denominator)
    dz = np.concatenate([(probability - success) * mask,
                         0.25 * np.clip(delta, -1, 1) * mask], axis=1) / denominator
    dh = (dz @ model['w'][2].T) * (h > 0)
    gradients = [x.T @ dh, dh.sum(0), h.T @ dz, dz.sum(0)]
    model['step'] += 1
    t = model['step']
    for w, m, v, g in zip(model['w'], model['m'], model['v'], gradients):
        m *= 0.9; m += 0.1 * g
        v *= 0.999; v += 0.001 * g * g
        w -= learning_rate * (m / (1 - 0.9 ** t)) / (np.sqrt(v / (1 - 0.999 ** t)) + 1e-8)
    return loss


def arrays(rows):
    x = np.stack([features(r['key'], [m[0] for m in r['moves']]) for r in rows])
    success, cost, mask = (np.zeros((len(rows), 52), np.float32) for _ in range(3))
    for i, r in enumerate(rows):
        for card, wins, nodes in r['moves']:
            success[i, card] = wins
            cost[i, card] = np.log1p(nodes)
            mask[i, card] = 1
    return x, success, cost, mask


def metrics(model, rows, data):
    z, _ = forward(model, data[0])
    p = 1 / (1 + np.exp(-np.clip(z[:, :52], -30, 30)))
    rank = p * np.exp(-np.clip(z[:, 52:], 0, 30))
    costs = dict(stock=0, model=0, oracle=0)
    first = dict(stock=0, model=0)
    eligible = 0
    for i, r in enumerate(rows):
        if not any(m[1] for m in r['moves']):
            continue
        eligible += 1
        for name, ordered in [('stock', r['moves']),
                              ('model', sorted(r['moves'], key=lambda m: -rank[i, m[0]]))]:
            first[name] += ordered[0][1]
            for _, ok, n in ordered:
                costs[name] += n + 1
                if ok:
                    break
        costs['oracle'] += min(n + 1 for _, ok, n in r['moves'] if ok)
    return dict(rows=len(rows), eligible_cutoffs=eligible,
                first_success_rate={k: v / max(1, eligible) for k, v in first.items()},
                isolated_child_node_cost=costs,
                proxy_speedup=costs['stock'] / max(1, costs['model']))


def train(dataset, output, epochs, seed):
    rows = [json.loads(line) for line in Path(dataset).read_text().splitlines() if line]
    family_map = split_families(r['family'] for r in rows)
    # Remove exact transpositions crossing splits; evaluation owns those states.
    priority = {'train': 0, 'validation': 1, 'test': 2}
    owner = {}
    for r in rows:
        k = tuple(r['key'])
        s = family_map[r['family']]
        if k not in owner or priority[s] > priority[owner[k]]:
            owner[k] = s
    groups = {s: [] for s in priority}
    seen = set()
    for r in rows:
        k = tuple(r['key']); s = family_map[r['family']]
        if owner[k] != s or k in seen:
            continue
        seen.add(k); groups[s].append(r)
    if any(not r for r in groups.values()):
        raise ValueError('Empty split after leakage removal')
    data = {s: arrays(r) for s, r in groups.items()}
    model = initialize(seed)
    rng = np.random.default_rng(seed)
    history, best, best_weights = [], float('inf'), None
    start = time.process_time()
    for epoch in range(epochs):
        order = rng.permutation(len(groups['train']))
        losses = []
        for i in range(0, len(order), 128):
            idx = order[i:i + 128]
            losses.append(train_step(model, *(a[idx] for a in data['train'])))
        validation = metrics(model, groups['validation'], data['validation'])
        criterion = validation['isolated_child_node_cost']['model']
        if criterion < best:
            best = criterion; best_weights = [w.copy() for w in model['w']]
        row = dict(epoch=epoch + 1, loss=float(np.mean(losses)), validation=validation)
        history.append(row)
        if epoch % 5 == 0:
            print(json.dumps(row), flush=True)
    model['w'] = best_weights
    out = Path(output); out.mkdir(parents=True, exist_ok=True)
    with (out / 'model.txt').open('w') as f:
        f.write(f'DDS_PROOF_V1 {INPUTS} {HIDDEN} {OUTPUTS}\n')
        for w in model['w']:
            np.savetxt(f, w.reshape(1, -1), fmt='%.9g')
    np.savez(out / 'model.npz', **{f'w{i}': w for i, w in enumerate(model['w'])})
    report = dict(parameters=sum(w.size for w in model['w']), architecture=[INPUTS, HIDDEN, OUTPUTS],
                  cpu_seconds=time.process_time() - start, family_splits=family_map,
                  input_rows=len(rows), unique_rows=sum(map(len, groups.values())),
                  metrics={s: metrics(model, groups[s], data[s]) for s in groups}, history=history,
                  limitation='Isolated child-cost proxy; requires exact whole-solve timing before promotion.')
    (out / 'training.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k != 'history'}, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('scavenge'); a.add_argument('trace'); a.add_argument('output')
    a.add_argument('--per-family', type=int, default=100); a.add_argument('--seed', type=int, default=7411)
    a.add_argument('--min-cards', type=int, default=7)
    a = sub.add_parser('train'); a.add_argument('dataset'); a.add_argument('output')
    a.add_argument('--epochs', type=int, default=40); a.add_argument('--seed', type=int, default=7411)
    a = p.parse_args()
    if a.command == 'train':
        train(a.dataset, a.output, a.epochs, a.seed); return
    with gzip.open(a.trace, 'rt') as f:
        boards = json.load(f)
    roots = prepare_roots(boards, a.per_family, a.seed, a.min_cards)
    out = Path(a.output); out.mkdir(parents=True, exist_ok=True)
    (out / 'roots.json').write_text(json.dumps(roots))
    splits = split_families(r['family'] for r in roots)
    for split in ['all', 'train', 'validation', 'test']:
        with (out / f'{split}.roots').open('w') as f:
            for i, r in enumerate(roots):
                if split == 'all' or splits[r['family']] == split:
                    f.write(' '.join(map(str, [r['family'], i, *r['key']])) + '\n')
    (out / 'source.json').write_text(json.dumps(dict(
        source=str(Path(a.trace).resolve()), sha256=hashlib.sha256(Path(a.trace).read_bytes()).hexdigest(),
        roots=len(roots), family_splits=splits, seed=a.seed, min_cards=a.min_cards), indent=2))
    print(json.dumps(dict(roots=len(roots), families=len(splits))))


if __name__ == '__main__':
    main()
