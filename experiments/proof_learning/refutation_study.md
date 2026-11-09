# Where expensive dead ends begin

9 November 2026. Follow-up to the self-play proof-learning pilot.

Max's proposed objective is to avoid slow refutations while finding quick
proofs, potentially by choosing the right path within a few early moves. This
study measures where the avoidable wrong choice occurred, rather than merely
the depth at which its failure was finally established.

## Instrumentation

The experimental DDS recorder now preserves each actually visited child:
card, parent-relative cutoff success/failure, recursive search cost, return
reason, whether the maximizing partnership's target was established, and the
immediate child proof move when one exists. Return reasons distinguish cache
proofs, target bounds, endgames, quick/later-trick bounds, move cutoffs, and
exhaustion of the legal alternatives.

A recorded proof move is a useful next response, not a complete certificate.
A branch may require many other replies to verify. Unvisited moves remain
unlabeled; they are never turned into false negative examples. All legal
representatives are recorded separately from visited children.

Detailed states are retained through the first three remaining tricks of a
request, including any already-started trick. Up to 64 expensive distinct
decisions per root are exported. An independent lightweight accounting profile
covers the entire search depth, so the location study does not truncate the
later origins it is intended to measure. This is diagnostic instrumentation in
an isolated build, not installed in live self-play workers.

## Accounting without double counting

At a node where an eventual child establishes the required cutoff, preceding
failed children are avoidable search under a different ordering. Assign their
complete measured subtrees to that node's depth and remove any nested failed
work already attributed inside those subtrees. Preserve the internal profile
of the successful child.

At a node where every child fails, the parent needs those results to establish
its bound. Do not label the entire set as avoidable; instead preserve avoidable
choices identified within the children. These rules apply to both partnerships
and both target-proof directions.

The result is a nonoverlapping decomposition of executed recursive calls.
It is not a guaranteed speedup: changing order also changes transposition-table
contents, later targets, and proof structure. It also excludes opportunities
to choose a cheaper successful proof when the original first choice succeeds.

## Results on scavenged self-play

The sample is all 423 requests with at least ten remaining tricks from the
previously selected 1,000 requests, representing ten source board families.
These are development data, not 423 independent boards or a fresh test set.

| Quantity | Result |
| --- | ---: |
| Recursive calls | 33,225,806 |
| Calls attributed to avoidable failed subtrees | 9,439,375 (28.4%) |
| Detailed early decisions exported | 22,298 |
| Actually observed child outcomes | 52,808 |
| Observed failed children | 41,207 |
| Child outcomes with an immediate proof/reply card | 38,988 |

Counting one played card as one search layer:

| Wrong choice begins within | Share of attributed failed-subtree work | Share of all recursive calls |
| --- | ---: | ---: |
| Root only | 15.0% | 4.3% |
| First 3 card plays | 21.0% | 6.0% |
| First 8 card plays | 48.0% | 13.6% |
| First 12 card plays | 65.1% | 18.5% |
| First 16 card plays | 80.1% | 22.8% |
| First 24 card plays | 93.9% | 26.7% |

Thus the late-leaf origin hypothesis is not supported on this sample: only
6.1% of this failed-subtree work originates after the first 24 played cards.
However, just the first two or three individual card choices do not capture
most of the opportunity. The first several tricks are a more useful window.
Partial starting tricks mean a three-trick recorder window contains 10–12 new
card plays; the profile table uses exact card-play distance from the request.

## Hindsight guide experiment

On a preselected subset of ten large requests per family (100 total), solve
each position three times while recording observed successful cutoff moves.
Retain the cheapest observed successful child for each exact state/target.
Then freeze the hints and replay a fresh exact all-move solve. Ordinary DDS
handles states absent from the hint map and every state below the gate.

| Hint horizon | Baseline calls | Frozen-hint calls | Node reduction |
| --- | ---: | ---: | ---: |
| First 3 card plays | 4,266,720 | 4,196,380 | 1.65% |
| First 3 remaining tricks | 4,266,720 | 3,583,022 | 16.02% |

This is 1.017x and 1.191x in recursive search work, respectively. It is not a
trained-network result, not wall-clock speedup, and not a ceiling. Hint
discovery consumed 12.66 million and 11.55 million additional recursive calls
respectively. There were 25 individual regressions in the three-play mode and
7 in the three-trick mode; the reported aggregate includes them. Verification
remained exact for every legal move throughout discovery and replay.

An earlier separate isolated-child teacher comparison also illustrates why
failure avoidance alone is insufficient. Among 3,064 decisions with at least
one successful child, stock ordering cost 36.77 million child nodes and the
cheapest-successful-child oracle cost 25.36 million. Of that proxy difference,
3.94 million were failed-prefix work and 7.47 million came from a more expensive
successful proof. These proxy costs do not account for full-search cache effects.

## Training approach

1. Keep scavenging large self-play requests with source family identity. Use
   the recorder's actual outcomes as inexpensive supervision, retaining
   explicit masks for unvisited alternatives.
2. Enrich a bounded sample of high-cost decisions with counterfactual exact
   solves. Form comparisons between an expensive failed continuation and a
   verified successful alternative, and between successful alternatives with
   different proof costs. Recheck promising choices in whole-root replay.
3. Fit a ranking objective weighted by verified work saved, with both proof
   success and log search cost as auxiliary targets. Include DDS's stock order
   as a prior/input. Keep both sides' refuting responses: at a defending node,
   finding the refutation quickly is the desired proof step.
4. Compare horizons of three card plays and three tricks. A root encoder can
   compute a reusable representation once; a cheap conditional head can select
   among legal moves using the short played-card prefix. Alternatively, emit a
   small conditional move-order table at the root. A fixed twelve-card sequence
   is insufficient because the guide must handle different replies.
5. Use the learned guide only for large requests and only to order search.
   Confirm improvement on new board families and complete warm related batches,
   charging feature construction, inference, table setup, and fallback costs.

The new recorder and hindsight measurements are complete. No new conditional
early-trick model has been trained or deployed by this follow-up.

## Reproduction and checks

The native patch now includes the additional recorder and return annotations.
Compile its changed `ab_search.cpp` as well as the driver; do not link a new
header against an old instrumented `ab_search` object because Research's
experimental layout changed. In the local build, the changed source was
recompiled and linked before the unchanged, pinned Bazel archives.

```bash
proof_learning refutations run/all.roots run/refutations.jsonl
proof_learning oracle run/refutation.roots run/oracle.jsonl
```

The first command also writes `run/refutations.jsonl.profiles.jsonl`. It skips
requests below ten remaining tricks. The second command compares three card
plays with three remaining tricks on supplied large requests.

Nine Python/unit/integration tests and five C++ GoogleTests passed. Tests cover
nonoverlapping failure accounting, necessary all-fail nodes, observed-child
masks, return metadata, exact move scores, unchanged recursive-call counts
under recording, horizon gates, and frozen-hint verification. The new
`refutation_summary.json` preserves the aggregated data. Raw records are saved
in a separate checkpoint rather than committed to the source repository.
