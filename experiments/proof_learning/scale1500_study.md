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

The native evaluation uses the fixed pilot threshold of -0.02, at most
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
undersized training data. All 23 Python tests passed after training, including native inference parity for the new checkpoint. No native
implementation changed in this follow-up; the previous clean-Bazel limitation
still applies.

The frozen inputs are saved as `DDS_1500_Deal_Corpus_2026-11-09.zip`. Full labels, the model, and evaluation rows are saved as `DDS_1500_Deal_Training_2026-11-09.zip`. Results follow below.

## Completed run

Labeling finished in 1,385 seconds. There were 36,000 raw decision records,
34,410 distinct encounters after removing 1,590 duplicated observations, and
74,668 distinct alternative trials. Four trials exceeded their work budget and
remain censored. Duplicated encounters reproduced identical node counts and
outcomes; no exact state plus stock ordering crossed a split boundary.

| Partition | Independent deals | Decision examples |
| --- | ---: | ---: |
| Training | **1,200** | **27,571** |
| Validation | 150 | 3,415 |
| Test | 150 | 3,424 |

The first training process was killed by SIGKILL, consistent with memory
pressure while expanding the JSON dataset and copying feature arrays. The
loader was changed to stream records, retain only training fields, preallocate
feature arrays, and release the decoded examples before optimization. No deals
were dropped to fit memory. The successful retry trained for 80 epochs in
16.7 seconds, with a peak resident set of about 181 MiB. Validation selected
epoch 1. The best validation loss was 0.000699488, compared with 0.000699099 for
always predicting zero cost change; epoch 80 had deteriorated to 0.000951723.

## How much could the tested single-change oracle save?

Across all 3,000 requests, stock DDS required 235,008,839 recursive calls.
Choosing the cheapest completed tested alternative at one early encounter per
request, or keeping stock ordering, required 222,823,437: **5.185% fewer nodes**.
This is total nodes saved divided by total baseline nodes, **not** an equal-board
average and **not** a direct CPU-time measurement. A deal-cluster bootstrap gives
a descriptive 95% interval of 4.82%–5.56% for this sampled workload. It excludes
teacher cost and is not a trained-policy result.

| Percentile across individual requests | Node savings |
| --- | ---: |
| Median | 3.39% |
| 75th | 7.38% |
| 90th | 14.59% |
| 95th | 19.52% |
| 99th | 41.81% |
| Maximum | 98.04% |

Eighteen of 3,000 requests had a tested change saving more than 50%. The largest
relative improvement was 69,289 to 1,360 nodes. Grouping each deal's two requests,
the median deal saving is 3.81% and the equal-deal mean is 5.89%; neither is the
pooled 5.185% figure used for total-work savings.

This restricted oracle is a lower bound on savings achievable by a stronger
offline search over ordering policies, ignoring discovery and inference cost.
It is not a bound on the shortest complete proof, and it tests only stock ranks
2–4 at sampled encounters. Multiple changes could overlap, add further savings,
or interact. Three independent 5% reductions of remaining work would save
14.26%, but this experiment has not demonstrated that stacking. Opposing replies
still have to be verified: one favorable line is not a complete proof.

## Trained model: exact results and measured CPU

Each held-out partition has 300 requests from 150 independent deals. Native
evaluation alternates order and repeats each baseline/guided pair three times.
Counts and CPU totals below include all three repetitions. Every legal-move
score matches. All 600 baseline requests also reproduce exactly three times
their independently collected teacher baseline node count.

| Partition | Baseline nodes | Model nodes | Node change | Baseline CPU seconds | Model CPU seconds | CPU change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Validation | 81,303,543 | 81,304,542 | +0.00123% | 10.146380 | 10.239489 | +0.92% |
| Test | 77,718,390 | 77,712,648 | -0.00739% | 10.131155 | 10.248501 | +1.16% |

The model promotes an alternative in only seven validation requests and three
test requests. It makes 48,975 and 47,946 model queries respectively across the
three repetitions; most requests retain stock ordering. Warm native feature
construction plus selection is about 1.02 microseconds per query. CPU totals
include the research hook as well as inference and search. The test node-saving
bootstrap interval spans zero (approximately -0.00013% to +0.0236%); the runtime
result includes timing noise and roughly 1% overhead. There is no useful
end-to-end speedup from this checkpoint, so it is not deployed.

An exploratory ranking diagnostic on completed alternative trials asks whether
the model ranks >5% improvements above other alternatives. Validation/test AUCs
are 0.468/0.488, compared with 0.518/0.521 for a simple training-derived prior
based only on stock rank. There are 225/236 positive alternatives respectively.
This diagnostic supplies no evidence that merely lowering the deployment
threshold would recover the oracle opportunity. It was not used to retune the
model on the test set.

## Interpretation and next experiment

The earlier eight-training-deal run was a pipeline smoke test and could not
meaningfully assess whether the model can learn exceptions to DDS's many
heuristics. This run meets the requested minimum and supplies a much broader
test, but 1,200 deals still need not cover rare bridge patterns. Its result is
specific to raw position features, stock ranks, the current small MLP and loss,
and ten-/twelve-trick actual self-play positions. It does not establish that
learned ordering is infeasible or that adding more independent data cannot help.

The next useful comparisons are a fixed-holdout learning curve with more deals,
inputs exposing DDS heuristic scores/components and bridge structure, and a
teacher that measures additional marginal savings after an earlier change.
Reporting held-out ranking, selective decisions, and actual whole-root CPU
separately will distinguish representation/learning limitations from inference
overhead and the opportunity available to the teacher. The current corpus,
labels, and exact evaluator make those comparisons possible without rerunning
self-play.
