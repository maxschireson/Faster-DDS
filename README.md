# DDS kernel optimization experiments — 8 November 2026

The clear winner in this first experiment was a smaller relative-rank table:
4–5% less solve time on full deals. Two other plausible optimizations did not
improve overall performance. These measurements do not establish the earlier
speculative 1.5–2x engineering target.

## Code and environment

Upstream: https://github.com/dds-bridge/dds

Revision: `0f969b86a4841f438fd0cdff2924c4f2404abf6a` (3.1.1 development tree).

AMD EPYC 9V74, Linux, GCC 14.2, optimized build, native CPU instructions and
link-time optimization in **every** variant, including the baseline. Thus the
compiler gain from the preceding review is not counted again. The timing driver
pins itself to one allowed CPU and executes variants serially. No Apple Silicon
performance measurements were made.

The original C++ editor integrations were unavailable; source inspection,
compiler diagnostics, and the repository's Bazel tests were used.

## Results

Times are the arithmetic mean of two passes in opposite variant order. Each
pass contains 1,000 full-length deal/strain cases: 200 independently shuffled
52-card layouts, all five strains, with opening leader rotating across layouts.
The confirmation set uses a different random seed. Best-move score is requested
with `target=-1, solutions=1`. Each case starts with an empty search cache.

| Variant | Screening set, seconds | Change from baseline | Confirmation set, seconds | Change from baseline |
|---|---:|---:|---:|---:|
| Unchanged upstream | 20.791 | — | 20.544 | — |
| Compact relative ranks | 19.988 | -3.86% | 19.446 | -5.34% |
| Conditional winner updates | 21.059 | +1.29% | Not separately retested | — |
| Longer own-hand cashing runs | 21.770 | +4.71% | Not retested | — |
| Compact ranks + conditional updates | Not tested | — | 20.064 | -2.34% |

Negative change means faster. The combination was 3.18% slower than compact
ranks alone on the confirmation set. Conditional updates are therefore omitted
from the recommended patch. Raw measurements are omitted from this source upload
and can be regenerated; small differences should not be treated as precise universal
speed estimates.

### Compact relative ranks — retain

`RelRanksType` originally stored fifteen ordinal slots per suit. Production
consumers use only the highest three. The prototype keeps slots 0–3, reducing
the per-context table from 960 KiB to 256 KiB (704 KiB saved, 73.3% reduction),
and limits construction to those slots. The corresponding heuristic-test helper
was updated as well. Search ordering and pruning rules are unchanged.

Every screened and confirmation case has exactly the same DDS trick-node count
as the baseline. The benefit is reduced processing cost, including table setup
when needed, rather than reduced search. The experiment does not separately
attribute the gain to cache locality versus faster initialization.

This changes an internal C++ structure's layout: rebuild linked consumers.

### Conditional winner updates — reject for now

At the end of a trick, skip saving/recomputing a suit's top two cards when both
remain in the aggregate mask. This preserves search nodes and results, but its
extra checking did not yield a dependable speedup. In the combination it lost
about three percentage points relative to the compact table alone.

### Longer cashing runs — reject this implementation

A fallback in `QuickTricks` counts uninterrupted top cards held by the player
already on lead, across suits, at notrump. It is deliberately conservative:
no entry to partner, no ruffing assumptions, and no addition to partner's trick
count. It supplies the winning-rank mask of the own-hand winners used.

The targeted AKQJx-style examples now terminate successfully, including a
relative-rank gap, the minimizing side, and winners in multiple suits. However,
the screening set's DDS trick nodes fell only from 64,813,031 to 64,805,954:
**7,077 nodes, or 0.0109%**. Within notrump the reduction was about 0.0685%.
Additional checking cost more than it saved. This narrow experiment does not
assess richer communication, trump-drawing, dominance, or endplay bounds.

## Validation

- Test-first checks initially failed on upstream for the memory budget,
  unnecessary winner snapshots, and missing cashing-run recognition.
- Ten targeted tests passed with the prototypes, including an independent scan
  of the top three ranks for all 8,192 masks in all four suits.
- All four candidate configurations matched baseline on every move score in
  **10,000 positions with 3–9 cards per hand**, with all five strains represented.
  Equivalent-card output was expanded to canonical card/score pairs.
- The compact table, cashing-run prototype, and combined variant each matched
  every reference result on the repository's **1,000 full-deal all-root-moves**
  suite, including its strict card/equivalence/output-order checks.
- The selected compact-table change passed **18 repository test targets**:
  search, move generation, heuristic sorting, solve/play analysis, context, and
  transposition-table configuration. Historical test logs are omitted from this upload.

The timing sets, short-position differential checks, and reference suite are
different workloads. The short-position and reference runs are correctness
checks; their elapsed times are not used for the reported speedups. DDS's
reported node counter counts completed-trick transitions, not every card ply.

## Files and reproduction

- `patches/recommended.patch`: compact table, its two tests, and benchmark driver.
- `patches/compact.patch`, `winners.patch`, `runs.patch`: separate experimental
  changes against upstream; they do not contain the common benchmark driver.
- `patches/compact_winners.patch`: the combined cost-per-position experiment.
- `patches/experimental_harness.patch`: common driver and all prototype tests.
  The tests describe the proposed improvements, so some intentionally fail on
  unmodified upstream. Use the appropriate test filter for a single variant.
- `run_experiments.py`: the exact serial comparison/verification driver.
- `results/`: generated locally when experiments run; excluded from Git.
- `logs/`: generated locally when reference checks run; excluded from Git.
- `environment.json`: compiler, flags, seeds, and revision.

Use a fresh checkout at the pinned revision. For the selected change, apply
`recommended.patch`. For reproducing the experiment, apply
`experimental_harness.patch` instead, build a baseline, then apply one variant
patch at a time. Do not apply the recommended and experimental harness patches
together. Reverse each variant patch before building the next one.

The Linux/GCC build command used was:

```sh
bazelisk build -c opt \
  --extra_toolchains=@@rules_cc++cc_configure_extension+local_config_cc_toolchains//:all \
  --copt=-march=native --copt=-flto --linkopt=-flto \
  //benchmarks:kernel_benchmark //library/tests:dtest
```

Create a `bin` directory beside this README. Copy the benchmark executable to
`bin/baseline`, `bin/compact`, `bin/winners`, `bin/runs`, or
`bin/compact_winners` as appropriate; copy `dtest` to the corresponding
`bin/dtest_VARIANT`. Binaries are not included because they are host-specific.
Then, while the working directory is the DDS checkout, run:

```sh
python /path/to/this/study/run_experiments.py screen
python /path/to/this/study/run_experiments.py confirm compact compact_winners
python /path/to/this/study/run_experiments.py small compact winners runs compact_winners
python /path/to/this/study/run_experiments.py known compact runs compact_winners
```

Each benchmark timing includes `solve_board` and excludes context creation,
cache reset, and CSV output. Per-deal rank tables may remain allocated between
strains, equally for every variant; the search cache is cleared before every
case. No cross-deal proof reuse, learned prediction, or ordering change was added.

For prototype tests use `//library/tests/ab_search:kernel_optimizations_test` and
`--test_filter=CompactRanks.*`, `WinnerUpdates.*`, or `CashingRuns.*` as
appropriate. All ten can be run with all three source patches applied.
The broader GCC test run used the same optimization flags plus
`--per_file_copt=.*test.*\.cpp@-Wno-error=dangling-else` to accommodate an
existing GoogleTest-macro warning in upstream `make3_test.cpp`.

The source and patch derivatives retain upstream's Apache 2.0 licensing; the
license is included. These are local research changes, not an upstream release.

## Source upload

This repository keeps the patches, tests embedded in the patches, benchmark driver,
reproduction instructions, and environment metadata. Raw CSVs, JSONL traces,
machine-generated result summaries, and build/test logs are excluded. The original
experiment archive remains unchanged. See `CREDITS.md` for attribution.
