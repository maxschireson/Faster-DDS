# Scaling proof-order training to independent self-play deals

The ten-deal pilot was inadequate for judging learnability. This experiment
selects 1,500 distinct completed self-play deals, with a frozen 1,200/150/150
training/validation/test split. Training is required to contain at least 1,000
independent deals **after** label collection and deduplication.

## Source and independence

`prepare_episodes.py` reads completed `mixed-fork-pair-v1` episodes from the
mixed arena's `g0001-bid40k` run. It validates the board and replays legal actions
from the first focal table. It groups deals by the SHA-256 digest of their four
original hands, independent of contract and hand permutation, before selecting
or splitting positions. The ten source families from the pilot are excluded.
There were 3,235 source episodes and 3,225 eligible independent deals; 1,500 were
selected with a deterministic hash order, independent of solver costs/outcomes.

Two large positions per deal are reconstructed, after four and twelve played
cards: 3,000 root requests with twelve and ten tricks remaining. These use the
**actual dealt hands from self-play**, not the PIMC sampled layouts collected in
the pilot. This expands independent training diversity but changes the source
distribution, so differences from the pilot cannot be attributed solely to
sample count. The corpus does not test thirteen-trick opening positions.

All five strains are represented: 814 spade, 770 heart, 326 diamond, 334 club,
and 756 no-trump requests. Exact source paths, file hashes, original episode
family IDs, canonical deal IDs, root states, and fixed splits are preserved.
The source run and its caches are read-only throughout this experiment.

## Labeling and training

The existing single-intervention teacher tests DDS stock choices 2–4 within
the first three card plays of each requested root. Both the eight costliest
baseline decision encounters and the first four chronological encounters are
labeled, then duplicate encounters are removed. Each trial replays the same
prefix and changes only one decision. Rank-one controls must exactly reproduce
baseline search work; completed trials must preserve all legal-move scores.
The existing max(20,000, four times baseline nodes) cap remains in place.

Labeling runs in 50-root batches. Each completed file is atomically renamed;
incomplete `.part` files are not training data. A single low-priority worker
is used. Measured cost prioritizes offline labels only and is not an inference
feature. Separate validation and test families are never training examples.

The residual MLP remains 480→64→3 (30,979 parameters), trained for up to 80 epochs
with its checkpoint selected by validation loss. The new `--splits` option
preserves the prepared family assignments even if some roots emit no decisions.
`--min-train-families 1000` enforces the requested independent training size.
The exact-state/stock-order cross-split deduplication runs before this check.

The planned native evaluation uses the fixed pilot threshold of -0.02, at most
64 model queries and one promotion per solve, within three card plays. The
entire root remains an exact DDS solve. Whole-root CPU and node measurements,
with alternating baseline/guided order and three repetitions, determine whether
the larger model is useful. No production model promotion is authorized by a
training loss improvement alone.

## Reproduction

Apply/build the existing native patch as described in `counterfactual_study.md`.
Place the bridge harness checkout on `PYTHONPATH` for episode preparation.

```
python prepare_episodes.py EPISODES scale1500 --deals 1500 --exclude-source PILOT_ROOTS_JSON
proof_learning intervene scale1500/all.roots cost.jsonl 3 8 cost
proof_learning intervene scale1500/all.roots first.jsonl 3 4 first
# Concatenate the two files (or the completed 50-root shards) to training.jsonl.
OPENBLAS_NUM_THREADS=1 python train_delta.py training.jsonl model \
    --splits scale1500/manifest.json --min-train-families 1000
proof_learning delta scale1500/validation.roots validation.jsonl model/delta.txt -0.02
proof_learning delta scale1500/test.roots test.jsonl model/delta.txt -0.02
```

The preparation and minimum-family checks have automated tests for legal replay,
related-position grouping, contract/hand-permutation deduplication, rejection of
invalid or incomplete records, fixed splits under subsampling, and refusal of
undersized training data. All 22 Python tests passed before training. No native
implementation changed in this follow-up; the previous clean-Bazel limitation
still applies.

The frozen inputs are saved as `DDS_1500_Deal_Corpus_2026-11-09.zip`. Labeling and
training results will be appended after completion; this protocol does not claim
a speedup.
