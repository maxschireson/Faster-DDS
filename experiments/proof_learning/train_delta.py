"""Learn log whole-root work changes for DDS's second/third/fourth choices."""
import argparse
import json
from pathlib import Path
import numpy as np
from pipeline import features, split_families


def load_rows(path):
    """Stream JSON and retain only training fields, avoiding full text copies."""
    rows=[]
    with Path(path).open() as source:
        for line in source:
            r=json.loads(line)
            rows.append(dict(family=r['family'],root=r['root'],decision_index=r['decision_index'],
                key=r['key'],stock_order=r['stock_order'],ply_from_root=r['ply_from_root'],
                baseline_nodes=r['baseline_nodes'],trials=[dict(rank=t['rank'],nodes=t['nodes'],
                complete=t['complete']) for t in r['trials']]))
    return rows


def encode(row):
    x = np.zeros(480, np.float32)
    x[:427] = features(row['key'], row['stock_order'])
    for i, c in enumerate(row['stock_order']):x[427 + c] = 1 / (i + 1)
    x[479] = row['ply_from_root'] / 12
    return x


def partition(rows, splits):
    unique = {}; owners = {}
    for r in rows:
        unique.setdefault((r['family'], r['root'], r['decision_index']), r)
        key = (tuple(r['key']), tuple(r['stock_order']))
        owners.setdefault(key, set()).add(splits[r['family']])
    groups = {s: [] for s in ['train', 'validation', 'test']}
    removed = 0
    for r in unique.values():
        if len(owners[(tuple(r['key']), tuple(r['stock_order']))]) > 1:
            removed += 1
        else: groups[splits[r['family']]].append(r)
    return groups, dict(duplicate_observations=len(rows)-len(unique), cross_split_rows=removed)


def baseline_loss(*data):
    model = initialize(0)
    for w in model['w']: w.fill(0)
    return loss_parts(model, *data)[0]


def checked_partition(rows, splits, min_train_families):
    if any(s not in {'train','validation','test'} for s in splits.values()):
        raise ValueError('Invalid family partition')
    groups, report = partition(rows, splits)
    if any(not rs for rs in groups.values()):raise ValueError('Empty partition after deduplication')
    count=len({r['family'] for r in groups['train']})
    if count < min_train_families:
        raise ValueError(f'Only {count} independent training families; require {min_train_families}')
    return groups, report


def initialize(seed):
    rng = np.random.default_rng(seed)
    w = [rng.normal(0, np.sqrt(2 / 480), (480, 64)).astype(np.float32), np.zeros(64, np.float32),
         rng.normal(0, 0.01, (64, 3)).astype(np.float32), np.full(3, 0.05, np.float32)]
    return dict(w=w, m=[np.zeros_like(v) for v in w], v=[np.zeros_like(v) for v in w], t=0)


def predict(model, x):
    w, b, v, c = model['w']
    return np.maximum(0, x @ w + b) @ v + c


def loss_parts(model, x, y, mask, complete, weight):
    h = np.maximum(0, x @ model['w'][0] + model['w'][1])
    prediction = h @ model['w'][2] + model['w'][3]
    delta = prediction - y
    delta = np.where(complete, delta, np.minimum(delta, 0))
    weights = mask * weight
    denominator = max(float(weights.sum()), 1)
    huber = np.where(abs(delta) <= 0.2, delta ** 2 / 2, 0.2 * (abs(delta) - 0.1))
    return float((huber * weights).sum() / denominator), h, np.clip(delta, -0.2, 0.2) * weights / denominator


def step(model, x, y, mask, complete, weight):
    loss, h, dy = loss_parts(model, x, y, mask, complete, weight)
    dh = (dy @ model['w'][2].T) * (h > 0)
    gradients = [x.T @ dh, dh.sum(0), h.T @ dy, dy.sum(0)]
    model['t'] += 1; t = model['t']
    for w, m, v, g in zip(model['w'], model['m'], model['v'], gradients):
        m *= 0.9; m += 0.1 * g; v *= 0.999; v += 0.001 * g * g
        w -= 0.001 * (m / (1 - 0.9 ** t)) / (np.sqrt(v / (1 - 0.999 ** t)) + 1e-8)
    return loss


def tensors(rows, scale):
    x = np.empty((len(rows),480),np.float32)
    for i,r in enumerate(rows):x[i]=encode(r)
    y, mask, complete = (np.zeros((len(rows), 3), np.float32) for _ in range(3))
    for i, row in enumerate(rows):
        for t in row['trials']:
            if t['rank'] == 1:continue
            c = t['rank'] - 2
            y[i, c] = np.log(t['nodes'] / row['baseline_nodes'])
            mask[i, c] = 1; complete[i, c] = t['complete']
    weight = np.sqrt(np.asarray([r['baseline_nodes'] for r in rows], np.float32) / scale).clip(0.2, 5)[:, None]
    return x, y, mask, complete, weight


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset'); p.add_argument('output'); p.add_argument('--epochs', type=int, default=80)
    p.add_argument('--splits', help='Frozen manifest containing family_splits')
    p.add_argument('--min-train-families',type=int,default=1)
    args = p.parse_args()
    rows = load_rows(args.dataset)
    splits = (json.loads(Path(args.splits).read_text())['family_splits'] if args.splits
              else split_families(r['family'] for r in rows))
    groups, deduplication = checked_partition(rows, splits, args.min_train_families)
    scale = np.median([r['baseline_nodes'] for r in groups['train']])
    data = {s: tensors(rs, scale) for s, rs in groups.items()}
    row_counts={s:len(rs) for s,rs in groups.items()}
    family_counts={s:len({r['family'] for r in rs}) for s,rs in groups.items()}
    del rows,groups
    model = initialize(7411); rng = np.random.default_rng(7411)
    history, best, best_w, best_epoch = [], float('inf'), None, 0
    for epoch in range(args.epochs):
        order = rng.permutation(row_counts['train'])
        for i in range(0, len(order), 64):step(model, *(a[order[i:i + 64]] for a in data['train']))
        val = loss_parts(model, *data['validation'])[0]
        history.append(val)
        if val < best:best, best_epoch, best_w = val, epoch + 1, [w.copy() for w in model['w']]
        if (epoch+1)%10==0:print(json.dumps(dict(epoch=epoch+1,validation_loss=val)),flush=True)
    model['w'] = best_w
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    with (out / 'delta.txt').open('w') as f:
        f.write('DDS_DELTA_V1 480 64 3\n')
        for w in model['w']:np.savetxt(f, w.reshape(1, -1), fmt='%.9g')
    np.savez(out / 'delta.npz', **{f'w{i}': w for i, w in enumerate(model['w'])})
    report = dict(parameters=sum(w.size for w in model['w']), best_epoch=best_epoch,
                  deduplication=deduplication,
                  family_splits=splits, rows=row_counts,
                  independent_families=family_counts,
                  selected_label_loss={s:loss_parts(model,*d)[0] for s,d in data.items()},
                  baseline_label_loss={s:baseline_loss(*d) for s,d in data.items()},
                  validation_history=history,
                  warning='Labels may prioritize expensive states offline. These losses are not a causal runtime speedup; native whole-root evaluation is required.')
    (out / 'training.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k != 'validation_history'},indent=2))


if __name__ == '__main__':main()
