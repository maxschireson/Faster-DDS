# Validated related-layout batch solving

This experiment adds a working C++ batch interface to DDS: fixed North/South,
multiple East/West allocations, complete up-front validation, persistent internal
proof tables, and optional root certificates and shape-based solve ordering.
For full deals, most of the speedup comes from retaining DDS's existing
generalized rank proofs. The new root layer has a larger effect in short endings. General symbolic shape-proof propagation
is not implemented.

## Measured full-deal results

These are 13 cards per hand. Each solve produces one exact trick-count result
for the specified strain and leader.

| E/W sample constraints | Independent solves, s | Retained TT, s | Root cache + shape order, s | Speedup vs independent |
|---|---:|---:|---:|---:|
| Unrestricted E/W shuffles | 159.39 | 129.35 | 107.28 | 1.49× |
| Shape and HCP constrained | 172.24 | 83.84 | 77.18 | 2.23× |
| Defensive tens and higher fixed | 185.76 | 25.27 | 23.94 | 7.76× |

Each row pools six independent N/S families, each with 1,000 defensive layouts.
Speedup is total independent-solve time divided by total batch-solve time, using
the arithmetic mean of two passes in opposite variant order. It is not the mean
of six speedup ratios. Individual families vary substantially.

| Layouts per batch | Retained TT speedup | Root cache + shape order speedup |
|---:|---:|---:|
| 1 | 1.011× | 1.014× |
| 4 | 1.030× | 1.035× |
| 16 | 1.085× | 1.051× |
| 64 | 1.296× | 1.292× |
| 256 | 1.728× | 1.719× |
| 1000 | 2.170× | 2.483× |

Additional six-pass small-batch check: 1 layouts: retained TT 1.006×; root + shape order 1.006×; 4 layouts: retained TT 1.015×; root + shape order 1.016×; 16 layouts: retained TT 1.069×; root + shape order 1.072×. These checks support a lightweight small-batch default; they do not establish a general single-solve gain.

The automatic policy uses ordinary retained-table solving through 256 layouts, except that positions with at most seven tricks remaining enable root certificates from 64 layouts. Above 256 layouts it enables root certificates plus shape ordering. This is a conservative policy chosen from this exploratory sample, not a proven optimal crossover. The table reports the explicitly measured paths. The abstract-cashing option remains off by default, and callers can override the mode and ordering explicitly.

## Seven- through ten-card positions

Six fixed N/S families per depth, 1,000 distinct unrestricted E/W allocations per family, four passes in alternating variant order. The hands are nested subsets of the same seeded deals used for the full-deal sweep. Times are pooled over families and divided by six; they include validation, context setup/teardown, and cache work.

| Cards per hand | Layouts | Cold, ms/batch | Retained TT, ms/batch | Root + shape order, ms/batch | Root + shape speedup |
|---:|---:|---:|---:|---:|---:|
| 7 | 1 | 0.143 | 0.140 | 0.128 | 1.114× |
| 7 | 4 | 0.452 | 0.447 | 0.412 | 1.098× |
| 7 | 16 | 1.845 | 1.804 | 1.678 | 1.099× |
| 7 | 64 | 7.485 | 6.661 | 4.924 | 1.520× |
| 7 | 256 | 30.195 | 24.574 | 13.428 | 2.249× |
| 7 | 1000 | 120.916 | 88.828 | 28.261 | 4.279× |
| 8 | 1 | 0.254 | 0.232 | 0.239 | 1.067× |
| 8 | 4 | 0.630 | 0.634 | 0.618 | 1.020× |
| 8 | 16 | 2.680 | 2.347 | 2.220 | 1.207× |
| 8 | 64 | 10.877 | 8.733 | 7.894 | 1.378× |
| 8 | 256 | 43.652 | 30.095 | 21.345 | 2.045× |
| 8 | 1000 | 166.881 | 98.346 | 47.219 | 3.534× |
| 9 | 1 | 0.505 | 0.499 | 0.475 | 1.062× |
| 9 | 4 | 1.501 | 1.532 | 1.517 | 0.989× |
| 9 | 16 | 5.498 | 5.563 | 5.521 | 0.996× |
| 9 | 64 | 21.730 | 18.479 | 18.257 | 1.190× |
| 9 | 256 | 83.717 | 54.667 | 49.945 | 1.676× |
| 9 | 1000 | 334.744 | 152.228 | 121.401 | 2.757× |
| 10 | 1 | 1.630 | 1.636 | 1.631 | 0.999× |
| 10 | 4 | 4.804 | 5.061 | 4.805 | 1.000× |
| 10 | 16 | 18.128 | 17.944 | 17.039 | 1.064× |
| 10 | 64 | 71.785 | 59.406 | 59.076 | 1.215× |
| 10 | 256 | 285.608 | 192.694 | 185.984 | 1.536× |
| 10 | 1000 | 1082.786 | 462.137 | 427.321 | 2.534× |

At 1,000 layouts, the unsorted root cache settles 4,267/6,000 seven-card layouts (71.1%) before DDS initialization; at ten cards it settles 686/6,000 (11.4%). This helps explain why adding a root cache matters much more in the seven-card case. Ordinary TT retention supplies most of the ten-card speedup.

Small batches remain a qualified result: at seven cards the root paths save hundredths to tenths of a millisecond for 4–16 layouts; at ten cards there is little consistent benefit at those sizes. Four repetitions over only six families do not establish precise percent-level or general single-solve improvements.

A separate two-pass ablation keeps the root search driver and native retained TT but sets root-certificate capacity to zero. It separates root-proof reuse from the different initial score bound in short positions.

| Cards | Layouts | Root driver, no stored root proofs, ms/batch | With root storage, ms/batch | Speedup from root storage |
|---:|---:|---:|---:|---:|
| 7 | 16 | 1.802 | 1.779 | 1.013× |
| 7 | 64 | 6.718 | 5.183 | 1.296× |
| 7 | 256 | 25.598 | 14.031 | 1.824× |
| 7 | 1000 | 94.088 | 29.200 | 3.222× |
| 10 | 16 | 16.693 | 17.678 | 0.944× |
| 10 | 64 | 56.223 | 57.399 | 0.980× |
| 10 | 256 | 190.613 | 181.686 | 1.049× |
| 10 | 1000 | 450.451 | 447.596 | 1.006× |

At seven cards, root-proof reuse adds about 3.2× beyond the retained-TT/root-driver control at 1,000 layouts; at sixteen layouts it adds only about 1% in this check. At ten cards it adds only about 1% at 1,000 layouts, and can add overhead to small batches. This supports enabling the root layer earlier for short endings, while avoiding a general claim that it speeds up single solves. The two-pass control has different absolute timings from the four-pass primary sweep; compare its variants within the same run.

The automatic policy keeps native retention for small/deeper batches, enables the root cache at 64 layouts for positions with at most seven tricks remaining, and adds shape sorting above 256 layouts. It is a conservative initial policy rather than a fitted optimum. The table deliberately shows fixed explicit variants instead of selecting the fastest result separately in each row.


## Method

- Six fixed N/S pairs, seeded 20261118 through 20261123; strain is family index
  modulo five (S, H, D, C, NT, S). West leads an empty trick. The full-deal
  runs start before the opening lead.
- Three 1,000-layout cohorts per pair. `0`: independent unrestricted E/W shuffles.
  `1`: East's four suit lengths each within one of the original deal, and HCP
  within two; a synthetic auction-like constraint, not an actual bidding model.
  `2`: each defender's tens and higher fixed, with lower cards reshuffled.
- Full-layout duplicates are rejected during corpus construction. These are
  different defensive allocations, not repeated identical deals. The API itself
  accepts duplicate layouts, which can occur in a caller's sample distribution.
- Sizes 1, 4, 16, 64, 256 and 1,000 are prefixes of the same cohort. Every batch
  starts with a fresh context. The cold control empties its TT before every
  layout while retaining context allocation. Other modes retain their TT for
  the batch. All receive the same 256 MiB TT budget.
- Native reference and candidate scores agree for every layout in every run.
  Outputs are N/S remaining tricks; internally DDS searches the side to play.
- AMD EPYC 9V74, GCC 14.2, Linux, C++20, `-O3`, one pinned CPU, serial runs.
  Every variant contains the previously selected compact relative-rank table.
  Unlike the earlier kernel benchmark, this run does not add native-CPU or LTO
  flags. Earlier 4–5% compact-table savings are not counted again.
- Timings include validation, ordering, context creation, search, root-cache
  work and context teardown. Corpus generation, file output and verification
  comparisons are excluded. Two passes do not make percent-level differences
  precise; the additional small-batch runs use six passes.
- The 18,000 full layouts represent only six N/S pairs. The timed workloads are
  full deals. A separate performance sweep uses six unrestricted cohorts at
  each of seven, eight, nine and ten cards per hand, four passes, and the same seeds. These
  are synthetic legal remaining-card positions, not positions sampled from
  completed play trajectories. Partial tricks receive correctness tests.
  No multicore speedup is included.

## What changed

See [DESIGN.md](DESIGN.md) for the certificate representation and safety argument.

The root cache stores lower and upper bounds with DDS's winning-rank ownership
conditions and exact defensive shape. Matching bounds can settle a new layout
before rebuilding DDS's per-deal tables. A partial match narrows the search.
No proof tree is replayed, unlike the earlier template-transfer experiment.
The score-only API does not return a best card or a full all-moves score table.

The separate shape abstraction is deliberately limited: cashing k top cards
from the leading hand requires no opposing shape at notrump or in the trump
suit; in a side suit it requires `length(suit) >= k OR length(trump) == 0`
for every other hand. This is a genuine sufficient predicate, but it does not
relax arbitrary search proofs. The latter still need exact lengths.

Across the full 18-cohort matrix, root caching alone changes retained-TT time by -1.83%; adding shape ordering changes it by -12.60%. The optional cashing variant changes it by -0.25%. These are pooled times, not confidence intervals.

| E/W constraints | Layouts settled from earlier root bounds | Partially tightened |
|---|---:|---:|
| Unrestricted E/W shuffles | 47 / 6,000 | 466 / 6,000 |
| Shape and HCP constrained | 192 / 6,000 | 1,098 / 6,000 |
| Defensive tens and higher fixed | 1,685 / 6,000 | 1,742 / 6,000 |

A high complete-root-hit count does not imply the same fraction of runtime is saved: retained DDS was already resolving many of those layouts cheaply from internal proofs. General shape abstraction has not been solved by this experiment.

A broader next experiment should derive length predicates at DDS's quick-trick
and later-trick proof leaves and propagate them through AND/OR search proofs.
Certificate complexity needs a cap with an exact-shape fallback. Dropping the
shape key from an existing rank pattern is not safe. These measurements do not
establish a general single-solve gain from such broader abstraction.

## Verification

- All 18,000 full-deal layout scores agree with fresh-cache native DDS in every measured variant and repetition. Repeated node counts are deterministic.
- All 24,000 seven- through ten-card layouts also match fresh-cache native DDS
  in every measured variant and repetition.
- 1,200 three-card endings match a separate unpruned minimax implementation, exhaustively enumerating the E/W allocations for each fixed N/S pair.
- 7,000 four-card layouts, exhaustively enumerated within their families, match independent native DDS and exercise generalized root hits.
- Additional tests cover all strains/leaders, varied layouts after one/two/three known trick cards, duplicates, tiny caches, invalid masks/counts/decks, current-trick revokes, and automatic mode selection.
- The new batch tests, native solve-board tests and TT-lookup tests pass. The new tests also pass AddressSanitizer and UndefinedBehaviorSanitizer together with leak detection disabled: LeakSanitizer cannot run under process tracing in this environment, so memory leaks are not covered by that check. The wider existing TT suite passes 88/89 tests; its memory-cap test has an unchanged baseline boundary assertion failure (the loop stops at exactly the threshold, while the assertion requires strictly greater). The same failure was reproduced on a clean upstream-plus-recommended-patch checkout without the related-batch changes.
- The patch applies cleanly after the existing recommended patch at the pinned upstream revision.

Tests for the batch API and the abstract-bound feature were first run in a
failing state before implementation. The final readability refactor is checked
again against the original small-batch score and node results. The editor MCP
integrations were unavailable; compiler diagnostics, manual source review and
Bazel tests were used.

## Reproduction

Start at upstream DDS revision `0f969b86a4841f438fd0cdff2924c4f2404abf6a`.
Apply this repository's `patches/recommended.patch` for the compact-ranks baseline,
then `experiments/related-batch/related_batch.patch`. The two-patch application
was checked against a clean copy of that exact upstream revision.

From the patched DDS checkout:

```sh
bazelisk test -c opt //benchmarks:related_batch_test
bazelisk build -c opt //benchmarks:related_batch_benchmark
python /path/to/Faster-DDS/experiments/related-batch/run_benchmark.py
python /path/to/Faster-DDS/experiments/related-batch/analyze_results.py results/related_batch
```

The experimental Linux build selected the system GCC toolchain with this
additional flag on each Bazel command:

```sh
--extra_toolchains=@@rules_cc++cc_configure_extension+local_config_cc_toolchains//:all
```

The longer small-batch check uses `--layouts 16 --repeats 6`. Set a different
`--prefix` so it does not overwrite the main measurements, then analyze with
`--repeats 6`. All scripts create their output directories.

The ending sweeps use `--cards 7 --constraint 0 --repeats 4` and likewise
`--cards 8`, `--cards 9` and `--cards 10`. The seven- and ten-card root-cache ablations add `--variants 6 --repeats 2`.
Use distinct output prefixes and pass the matching repetition count to the analyzer.
The corpus smoke test is `python benchmark_input_test.py /path/to/binary`.

Raw CSVs, sampled hands, machine-generated summaries and test/build logs are
kept in the accompanying results archive, not in this source repository. CSV
variants are `0=cold`, `1=retained`, `2=root`, `3=root+shape order`,
`4=root+abstract cashing bound`, `5=root driver with root-cache capacity zero`
(the latter is enabled only in the follow-up ablation). In variant 4, `root_full` and `root_partial`
include the contribution of cashing bounds. `nodes` counts completed-trick
transitions, not every card-play ply. `tt_mib` is sampled peak native TT usage,
not total resident process memory; the small root cache is additional.

DDS's authors and contributors supplied the solver and its proof machinery.
Max Schireson directed this investigation; OpenAI ChatGPT/Codex assisted with
implementation and analysis. Upstream notices and Apache-2.0 licensing remain.
