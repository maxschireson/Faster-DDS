# Related-layout DDS batch experiment

Fixed North/South hands, multiple East/West allocations, validation before search,
and reusable DDS proofs. This directory contains source and reproducible scripts;
raw measurements and logs are distributed separately.

- [Performance report](PERFORMANCE.md): full deals, seven- through ten-card positions,
  small batches, controls, limitations and reproduction commands.
- [Design and API](DESIGN.md): validation, cache lifetime and proof conditions.
- [Source patch](related_batch.patch): apply after `patches/recommended.patch`
  at DDS revision `0f969b86a4841f438fd0cdff2924c4f2404abf6a`.
- `run_benchmark.py`, `analyze_results.py`, `benchmark_input_test.py`: runner,
  result validation and corpus checks.

DDS and its proof machinery are the work of the upstream authors and contributors.
Max Schireson directed this investigation; OpenAI ChatGPT/Codex assisted with
implementation and analysis. All additions retain Apache-2.0 licensing.
