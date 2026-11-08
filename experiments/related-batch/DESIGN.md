# Related-layout batch solver

The API accepts fixed North and South holdings, one fixed strain and current
trick, and a vector of East/West allocations of the same remaining cards. It
returns exact remaining North–South tricks in input order. There is no learned
component, no approximate score, and no information-limited common strategy.

## Validation and lifetime

All layouts are validated before a context is created. Checks cover legal mask
bits, duplicate cards across hands and the current trick, 1–13 cards per hand
when current-trick cards are restored, contiguous current-trick entries, a legal
strain/leader, observable revokes, and the same remaining deck in every layout.
An invalid late layout rejects the entire batch. Duplicate *layouts* are allowed;
duplicate *cards within a layout* are rejected. Bitmask input cannot represent a
duplicate occurrence within one holding; a list/PBN adapter must detect that
before conversion if it accepts noncanonical input.

Each batch owns a fresh context, retains its transposition table with DDS mode 2,
and destroys that context at completion. Keeping a single strain for that
lifetime matters: DDS mode 2 suppresses its ordinary new-trump reset as well as
its new-deal reset. A caller never has to manage this safety condition manually.
The context is single-threaded. Independent batches can use independent contexts.
The 256 MiB default limits the native TT; an additional bounded root cache holds
at most 65,536 certificates and 128 certificates per shape. Native TT eviction
remains safe. Hitting a root-cache cap simply stops adding new patterns.

## Root certificates

DDS already proves more than one exact card arrangement: its winning-rank masks
identify the lowest relevant rank in each suit, and relative-rank patterns permit
changes below those ranks, subject to exact suit lengths. Ordinary internal TT
lookups exploit this. The normal root search also computes those masks, but does
not expose reusable root bounds through the scalar result API.

The prototype initializes a deal with ordinary `target=0` DDS, then runs the
ordinary root search at successive thresholds. After each completed threshold it
records the proven lower or upper bound and the E/W ownership of every live card
at or above each suit's lowest winning rank. N/S holdings, the remaining deck,
strain, leader and current trick are fixed for the cache's lifetime. Exact East
suit lengths determine West's lengths, so a compact East-shape key suffices.
There are no forbidden root moves in this scalar search.

A later layout checks these masks and lengths before DDS initialization. Matching
lower and upper certificates can establish an exact score together; a one-sided
match narrows the search interval. No result is accepted merely because a
coarse key matches. The result does not include a move: a cached score need not
supply a valid representative card or DDS's full equivalent-card output.

For positions with fewer than 13 tricks remaining, the scalar driver also starts
with the actual remaining trick count as its upper bound. This is a separate
advantage from cross-layout reuse in short endings. Full-deal timing comparisons
avoid that confound.

## Limited shape abstraction

An optional family of cashing certificates is compiled once from the batch's
fixed remaining deck. A certificate says that the player on lead owns the top k
remaining cards of one suit. In notrump, or when that suit is trump, those k
tricks are guaranteed irrespective of exact opposing lengths. In a side suit,
each other hand must satisfy:

    length(led suit) >= k OR length(trump) == 0

This sufficient condition also prevents partner from being forced to ruff and
interrupting the cashing hand's lead. It requires an empty current trick.
Ownership and these predicates are checked on each layout. The lower bound is
used together with the ordinary rank certificates.

This is a narrow, proved shape abstraction. Arbitrary DDS search proofs still
retain exact shape. Removing exact length constraints from arbitrary stored
winning-rank patterns would be unsound: following suit, ruffs, discards, entries
and squeeze timing can depend on lengths even when low card ranks do not matter.
General shape abstraction would require propagating sufficient length predicates
through the proof tree, including every reply at universal nodes. It is not
implemented here.

## Use

Apply `related_batch.patch` after the repository's recommended compact-ranks
patch at upstream DDS revision `0f969b86a4841f438fd0cdff2924c4f2404abf6a`.
The patch adds source, tests and a benchmark without changing DDS's existing
single-board entry points or search engine.

```cpp
#include <related_batch.hpp>

related_batch::Batch batch;
batch.trump = 4; // notrump
batch.first = 0; // North leads
batch.north = {0x7000, 0, 0, 0}; // spade AKQ
batch.south = {0, 0, 0, 0x001c}; // club 432
batch.layouts.push_back({{0, 0x001c, 0, 0}, {0, 0, 0x001c, 0}});
batch.layouts.push_back({{0, 0, 0x001c, 0}, {0, 0x001c, 0, 0}});
related_batch::Options options;
options.mode = related_batch::Mode::RootProofs;
options.abstract_cash_bounds = true;
auto result = related_batch::solve(batch, options);
// result.ns_tricks == {3, 3}
```

The header is available through the existing `//library/src:dds` Bazel target.
This first implementation exposes a C++ API; there is no new C/Python binding.

## Attribution

The underlying solver, search, pruning and winning-rank certificates are DDS
work, principally by Bo Haglund, Søren Hein, Martin Nygren and the upstream
contributors. Max Schireson directed the related-layout experiment; OpenAI
ChatGPT/Codex assisted with implementation, tests and analysis. All additions
retain Apache-2.0 licensing. This is an experimental derivative, not an upstream
DDS release.
