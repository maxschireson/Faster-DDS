# Learning cheap DDS cutoffs from self-play

This prototype scavenges existing self-play DDS requests, replays a bounded
subset offline to obtain proof-cost supervision, and trains a small CPU model.
It is an isolated experiment, not enabled in the production bridge arena.

The [early-refutation follow-up](refutation_study.md) adds recording of failed
children, reply moves, return reasons, and nonoverlapping dead-end origin costs.
It profiles 423 large self-play requests and compares hindsight guidance over
three card plays versus three tricks. No conditional early-trick model has yet
been trained from those new records.

## Exact task

For a DDS state and a trick threshold, predict for each legal representative
card (a) the probability that trying it produces a cutoff and (b) the logarithm
of the recursive search work needed to check that child. Rank by predicted
probability divided by predicted cost plus one. Promote the first-ranked card;
preserve the other cards and all of DDS's exact verification and pruning rules.

This is a first step toward learned proof guidance. It does not produce a full
symbolic certificate or claim to identify a globally minimum proof. Child costs
are measured in isolated, reset contexts using stock downstream search. They
are a teacher proxy: whole-search transpositions can change the best ordering.

## Source and collection

The source is the `trace.json.gz` format emitted by the bridge arena's
`ops/benchmark_live_dds.py`: recorded family IDs, current trick, strain, leader,
and the actual sampled worlds used by self-play. No new random deals are made.
The existing persistent cache also contains positions and exact all-move
scores, but lacks proof costs and board-family provenance. This pilot therefore
uses the trace capture for trustworthy family separation.

1. Deduplicate sampled root requests and select a bounded, seeded sample per
   source family. Preserve source SHA-256 and each request's provenance.
2. Replay each selected root with all-legal-move scoring. Verify that enabling
   collection leaves every score unchanged.
3. Capture branching states in the first five search levels, retain up to eight
   expensive distinct decisions per root (at least 64 recursive calls), and
   record the state, threshold and DDS's original legal representative order.
4. For every candidate at each selected decision, perform a separate exact
   threshold solve. Record success/failure and recursive calls. Forced and
   trivial cases receive exact labels too.
5. Keep whole source board families together. Remove exact state overlap before
   fitting. No production cache or worker is changed by these operations.

Costs are additional offline labeling work; the positions themselves are
scavenged. The pilot does not yet install a continuous logger in live workers.
Additional self-play trace captures can be processed by the same pipeline.

## Model and fitting

The current actor is rotated to seat zero. The 427 inputs comprise:

| Input | Features |
| --- | ---: |
| Remaining cards, four hands | 208 |
| Up to three cards in the current trick | 156 |
| Trump strain including notrump | 5 |
| Current-trick position | 4 |
| Target for the acting partnership and tricks remaining | 2 |
| Legal representative-card mask | 52 |

The network is `427 -> 64 ReLU -> 104`, with 34,152 parameters. Its two
52-output heads predict cutoff logits and `log(1 + child nodes)`. The loss is
legal-move-masked binary cross entropy plus 0.25 times Huber loss on log cost.
Optimization uses Adam, learning rate 0.001, batch size 128, 40 epochs. Select
the checkpoint using validation-family aggregate isolated-child search cost;
never select on the test family. Float32 inference is embedded in C++ and uses
sparse binary inputs. Quantization is not yet necessary for the latency target.

Inference runs only in the first five search levels, with a per-solve call cap.
Caps 1, 4, and 8 were compared on validation. Cap 1 was then evaluated on the
held-out family. An incorrect prediction changes ordering, never the answer.

## First pilot: 9 November 2026

| Quantity | Result |
| --- | ---: |
| Source self-play families | 10: 8 training, 1 validation, 1 test |
| Scavenged root requests | 1,000 |
| Selected internal decisions | 6,547 |
| Candidate cutoff/cost labels | 27,128 |
| Training / validation / test decisions | 5,263 / 721 / 563 |
| Parameters | 34,152 |
| Full native choice, features included | 1.23–1.29 microseconds |
| Held-out exact root requests | 100, each mode repeated three times |
| Test baseline / guided recursive calls | 4,221,579 / 4,218,003 |
| Test baseline / guided CPU seconds | 0.532414 / 0.542582 |
| Test runtime factor | 0.9813x: about 1.9% slower |
| Exact all-move output disagreement | Zero |

The latency result is promising. The first trained policy has **not** produced
a useful speed improvement. Its held-out proxy cost improves about 2%, but
complete-search work changes by only 0.085%, and overhead exceeds that saving.
Do not promote this checkpoint. DDS's stock ordering is already strong: in
held-out decisions where a cutoff exists, its first move succeeds 89.7% of the
time versus 83.3% for this model. Cheapness and cutoff accuracy must be balanced.

These are smoke/pilot results, not a statistically persuasive generalization
study: one held-out source family is only one independent test group. The
corpus covers spades, hearts, diamonds and notrump, with no club contracts.
Roots have at least seven tricks remaining; captured descendants include
six-trick states. Native latency is warm-cache on the available Linux CPU,
averaged over 10,000 choices; it is not an Apple Silicon or cold-cache result.
Timing is serial reset-context all-move DDS, not production warm related batches.
The model integration still includes research-hook overhead. Neither timing nor
the earlier oracle speedups should be applied directly to production throughput.

## Validation and reproducibility

Six Python/unit/integration tests and two C++ GoogleTests passed. The checks
include family separation, root deduplication, target/seat feature conversion,
both heads learning, Python/native output agreement across 100 fixtures, and
425 cutoff labels independently checked with the bridge arena's separate exact
DDS library. Every collection replay and guided benchmark verifies all legal
move scores. The source patch applies cleanly to pinned upstream DDS.

The native patch targets DDS revision
`0f969b86a4841f438fd0cdff2924c4f2404abf6a`. Start from an isolated checkout:

```bash
git checkout 0f969b86a4841f438fd0cdff2924c4f2404abf6a
git apply /path/to/Faster-DDS/experiments/proof_learning/native.patch
bazel test -c opt //library/tests/ab_search:proof_model_test
bazel build -c opt //benchmarks:proof_learning
```

The local Bazel analysis process terminated with exit 255 in this environment;
the executed pilot compiled the new driver with GCC and linked the previously
Bazel-built instrumented DDS archives from the same pinned revision and
instrumentation. GoogleTests were compiled at `-O0` after `-O2` compilation was
killed. The native model and experiment driver were compiled at `-O3` with
`-Wall -Wextra -Werror`. This limitation is recorded rather than claiming a new
Bazel build passed.

Given an existing self-play trace and the built native executable:

```bash
python pipeline.py scavenge /path/to/trace.json.gz run --per-family 100
/path/to/proof_learning collect run/all.roots run/training.jsonl
OPENBLAS_NUM_THREADS=1 python pipeline.py train run/training.jsonl run/model
/path/to/proof_learning evaluate run/validation.roots run/validation.jsonl run/model/model.txt 1
/path/to/proof_learning evaluate run/test.roots run/test.jsonl run/model/model.txt 1
python -m unittest discover -s . -v
```

Set `DDS_PROOF_BINARY`, `DDS_PROOF_MODEL`, `DDS_PROOF_DATA` and optionally
`DDS_PROOF_REFERENCE` to enable native integration tests. The latter is the
path to an independently built library exporting the DDS C context API. NumPy
is the only Python dependency. Generated data, logs, binaries and checkpoints
are excluded from this repository; the pilot checkpoint is saved separately.

## Next learning iteration

### Root-only, large-request follow-up

The captured 10-board production workload concentrates time in large DDS
requests, after existing cache hits and duplicate worlds are accounted for:

| Remaining tricks | Share of DDS-call CPU time | Share of native solves |
| --- | ---: | ---: |
| 13 | 53.0% | 4.7% |
| 12–13 | 70.8% | 9.6% |
| 11–13 | 81.7% | 16.0% |
| 10–13 | 87.8% | 23.7% |

These times include the DDS caller's packing/cache work. A remaining-tricks
bucket includes positions within the current trick, not just complete hands.
On this sample, a 30-microsecond prediction once per native request with at
least ten tricks remaining would add 0.217 seconds against 51.48 seconds in
that group, about 0.42%. Cache hits should bypass prediction entirely.

The evaluator now supports `[CAP] [LEVELS] [MIN_TRICKS]`. For example:

```bash
/path/to/proof_learning evaluate run/all.roots run/root-only.jsonl run/model/model.txt 1 1 10
```

This allows at most one prediction at the exact root depth and skips smaller
requests. A regression test checks zero small-request calls and records the
minimum/maximum actual inference depths to verify no child was queried.
All seven Python/unit/integration tests passed after this change.

Reusing the first model across all 1,000 development requests produced 423
eligible large requests and 577 skipped smaller requests. All-move results
matched exactly. Large-request recursive work increased 0.21% and measured
time increased 1.34%; there is still no demonstrated improvement. On the 68
eligible requests from the previously held-out family, time was essentially
unchanged (1.0006x), with 0.086% fewer nodes. This follow-up is development
analysis reusing the same families, not a fresh confirmation test. The gate
improves inference economics; a better policy or richer root-level proposal is
still required. `root_only_summary.json` preserves aggregate measurements.

Collect more independent self-play families before expanding the number of
nearby positions per family. Add DDS's existing move order as an input/prior so
the network learns when to improve it. Then compare direct cheapest-successful
move supervision with probability/cost ranking, selecting on complete verified
search cost. Train only on training families and select gates on validation;
use newly reserved test families after design changes. Measure warm related
batches and all-move outputs before considering deployment. Proof fragments
or symbolic certificates are a separate later stage requiring a new verifier.

## Attribution

DDS was created by Bo Haglund and developed by Soren Hein and the DDS
contributors. This experiment relies on their exact solver and retains its
Apache-2.0 notices. Max Schireson proposed scavenging self-play for proof
learning and directed the work. OpenAI ChatGPT/Codex assisted with the prototype,
measurements, tests, and report. See the repository's CREDITS.md and LICENSE.

## Counterfactual ordering follow-up

[Counterfactual study](counterfactual_study.md): promote stock choices 2–4 at a single early encounter and measure the full solve. A 100-root teacher finds 5.38% hindsight node savings within three card plays; the first residual model does not generalize (reserved family +2.21% nodes, +7.42% CPU). Stock DDS remains the default.
