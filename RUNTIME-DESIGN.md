# Design note: the runtime

*2026-09-16. Companion to `SURFACE-LANGUAGE-DESIGN.md`. The language
note fixes what programs compile to; this note fixes what runs them and
why a real runtime is needed for the language to be viable. Nothing here
is built. The research artifact in `~/ski-in-ski` runs on
`aviary-kernel`'s Python reducer, and that remains the reference
implementation for every count the paper reports.*

## 0. Thesis

The viable runtime is Turner's SKI graph-reduction machine with jets.
Jets are the runtime performing, from outside the calculus, the two
operations the calculus cannot perform for itself: recognizing the
structure of a live term, and (at the encoding boundary) quoting one.
Both are metalevel by theorem, not by engineering convenience, so the
runtime's job description is fixed before a line of it is written.

## 1. What the reference host is

`aviary-kernel` 0.1.0 reduces terms as a DAG with sharing, under normal
order, one contraction per step, with a fuel cap and a sampled size cap.
Sharing is why the artifact runs at all: the tower's intermediate states
are a few hundred DAG nodes while their tree unfoldings reach 10⁵ atoms.
Measured throughput is about 12,000 contractions per second (T2's
504,930 contractions in about 40 s). It has no jets and no notion of a
known combinator; every `S`, `K`, `I` is reduced by its rule.

For the paper that is the right tool. Its counts are the claims, and a
reducer that did anything cleverer would make the counts about the
reducer.

## 2. What viability requires

Three orders of magnitude in throughput, and the removal of the
per-level interpretive overhead.

- **Throughput.** A C or Rust graph reducer with hash-consed nodes and
  an explicit spine stack runs at 10⁷ to 10⁸ contractions per second.
  That makes a third tower level, the self-hosting compiler, and the
  partial-evaluation runs routine instead of overnight. This is the
  well-trodden part: Turner's machine \[1\], supercombinators \[2\], the
  G-machine \[3\], and the Reduceron \[4\] for the hardware end.

- **Jets.** Nock is viable because Vere matches batteries against a
  dashboard of known cores by hash and runs native code. The SKI
  analogue matches expanded subterms against a table of known
  combinators by structural hash: the standard subject's arms first
  (numerals, lists, `EQ`), then the interpreters. Jetting `whnfF` is the
  decisive one: it is exactly why `+mock` costs nothing per level in
  Nock, and it removes the roughly 10³-per-level overhead the paper
  reports, by the same means and with the same honesty about where the
  speed comes from. Turner's built-in combinator set was already this
  idea under another name.

- **Correctness of jets.** A jet is a claim that native code agrees with
  the term it replaces. The artifact's discipline transfers directly:
  a jet is admitted when the fresh-marker probes and the reduction
  certificates (`NEXT-STEPS.md` item 3 in the paper's repository) agree
  with the reduced term on the checked inputs. Differential testing
  against the unjetted reducer is the ongoing check, as it is for Vere.

## 3. Where the runtime sits relative to the theorems

Proposition 3.1 of the paper: no SKI term can quote a live term, because
factorisation of live combinators is not representable (Jay and
Given-Wilson 2011, Thm. 3.2). The proof is about terms; Jay and
Given-Wilson explicitly set aside "the Turing machine with the term on
its tape," which can factorise freely. The runtime is that machine.

So the two metalevel operations the language design (`SURFACE-LANGUAGE-DESIGN.md`
§5) must stage are exactly the two the runtime performs:

| operation | inside the calculus | in the runtime |
|---|---|---|
| quote a live term | impossible (Prop. 3.1) | the compiler, at compile time |
| recognize a live term's structure | impossible (same theorem) | jet matching, at run time |

This is the sentence the follow-up paper should state in its
introduction: the runtime does for the calculus the two things it cannot
do for itself, and both are fixed by a theorem rather than chosen.

## 3a. Two runtimes

- **`skijack`**: Python, on `aviary-kernel`'s reducer. The reference
  implementation and the conformance oracle; slow, exact, and the thing
  the paper's counts come from.
- **Avon** (a nod to Vere): a C runtime. Vere's own language, and the
  right one for a graph reducer, which is a flat arena of immutable
  shared nodes addressed by integer index with an explicit stack and no
  hidden allocation; an ownership model buys nothing for that. The
  architecture is the Ares / NockVM one recast in C:
  - **Arena.** One flat array of nodes, each a small tagged struct: leaf
    `S`/`K`/`I`, `App(left, right)` as two 32-bit indices, and an
    indirection node for the result of a contraction so sharing survives
    reduction. Bump allocation; a hash table from `(left, right)` to
    index so structurally equal applications are one node
    (hash-consing), which is also what makes jet lookup O(1).
  - **Reducer.** Normal-order head reduction with an explicit spine
    stack of indices, one contraction per step, fuel as a counter, a
    size cap on the arena. No recursion in the reducer, so a
    thousand-deep spine costs nothing on the C stack.
  - **Memory reclamation.** Vere's two-sided loom (allocate from both
    ends, copy the live graph on return from a computation) is the
    proven design for a persistent noun store and transfers directly;
    reference counting is the simpler first version and is correct for
    an acyclic arena, which this is.
  - **Jets.** A table from the structural hash of a node to a C function
    pointer, consulted when a hash-consed node is about to be reduced;
    the interpreter jet first. The hash is computed once at
    hash-cons insertion, so matching is a table probe, not a walk.
  - **Snapshots.** The arena is a flat array, so a snapshot is a write of
    the array plus the hash table's rebuild on load; interchange uses
    the bitstring encoding of §3d.
  - **Discipline.** Compiled with sanitizers in tests; differential
    against `skijack` on every corpus term, byte-identical outputs and
    identical contraction counts; no behaviour the Python reference does
    not also have.
  Byte-identical to `skijack` on every conformance target, by the
  nockasm discipline.

Both implement the same boot protocol (§3b), so a compiled kernel moves
between them.

## 3b. Boot protocol and kernel shape

**An executable is a function of the runtime's initial subject, and the
runtime always starts by applying the loaded term to it.** Nothing else
needs to be known to start a program. The initial subject carries the
quoted standard library (`SURFACE-LANGUAGE-DESIGN.md` §6b), so this also
settles who supplies `⟨subject⟩`: the runtime, at boot.

A **kernel** is a core with a declared interface the runtime pulls by
name, Arvo's shape at small scale:
- `poke`: event → new kernel and a list of effects;
- `peek`: path → answer, which is the scry namespace of `SYNTAX.md` §6,
  served to level-1 programs that `∵`.

The runtime's loop: apply `poke` to the event, install the result, serve
`peek` to anything that scries, emit the effects. A program that is not
a kernel is just a term applied once to the initial subject.

## 3c. Fuel policy

The compiler cannot fill in elided fuel: a term's fuel is its running
time, and convergence is only semi-decidable (the paper's §5). Elided
fuel, `<t>@[]`, therefore means *runtime policy*: iterative deepening,
doubling the budget until a value or a configured cap, with the cap
reported as the timeout outcome, never hidden. One static case exists:
a term the compiler can prove affine (no `Y`, no contraction, by the
paper's census) is strongly normalizing with a step count bounded by
its size, and the compiler may fill exact fuel for it. Everything else
is the runtime's.

## 3d. Serialization

A term at rest is Tromp's bitstring encoding, `S̃ = 00`, `K̃ = 01`,
application `1 M̃ Ñ`, extended with a third leaf code for `I` (or with
`I` expanded to `S K K`, at the cost of two atoms per occurrence; the
choice is a version decision). This is the SKI `jam`: bijective,
self-delimiting, and already in the paper's bibliography. Sharing is not
preserved by the bitstring; a runtime that needs it (snapshots of
reduced states, whose tree unfoldings are exponential) uses its own
hash-consed image format and the bitstring for interchange only.

## 4. Architecture, in the order it should be built

1. **Graph reducer.** Nodes are `S`, `K`, `I`, `App`, plus an
   indirection node for sharing after contraction. Normal-order head
   reduction with an explicit spine stack (no recursion), fuel, and a
   size cap. Hash-consing of application nodes so structurally equal
   subterms are one node; this is what makes jet lookup cheap and is
   also what the reference host approximates by identity-sharing. Output
   must reproduce every count in the paper exactly: T0 340, T1 91,556,
   T2 504,930, the T3 table, the scry tables. That is the acceptance
   test, and the reference host is the oracle for it.
2. **Encoded-term I/O.** Read and write the printed form the paper's
   appendix uses and the `figures/*.txt` files, so terms move between
   the reference host and the runtime without a third format.
3. **Jet table.** Keyed by the hash of the expanded term. First entries:
   the Scott constructors and case forms, numerals and arithmetic, lists,
   `EQ`. Each entry ships with its probe-based test against the reducer.
4. **The interpreter jet.** `whnfF`, `wfQ`, `wfN` as native code that
   reads encoded terms and produces encoded outcomes, with the same fuel
   semantics (fuel `k` permits `k` step-attempts, the last of which must
   be the no-redex check). This is the `+mock` jet and the point at which
   virtualization becomes free.
5. **Scry.** The runtime owns the resolver's external side: the fact
   store, and the resume loop when the language's core-based driver is
   not used. Blocking semantics as in the paper: re-run from scratch
   under an append-only namespace, with the fuel non-neutrality
   documented rather than hidden.
6. **A subject loader and the boot protocol** (§3b). The standard subject
   compiled once, hash-consed, quoted once for level 1, and shared across
   programs; `poke`/`peek` served by the loop.

## 5. What the runtime must not do

- Change any count the paper reports. The reference host stays the
  oracle; the runtime agrees with it or is wrong.
- Reduce under jets in ways the unjetted term would not. A jet is an
  optimization of a reduction that exists, never a semantics of its own.
- Perform quotation on behalf of a running term. The compiler quotes;
  the runtime never turns a live value into data for a program to
  inspect, because the language (§5 of the language note) promises that
  cannot happen.

## 6. Literature to read first

1. D. A. Turner, "A New Implementation Technique for Applicative
   Languages", *Software: Practice and Experience* 9(1), 1979. The SKI
   graph-reduction machine.
2. R. J. M. Hughes, "Super-combinators: A New Implementation Method for
   Applicative Languages", *ACM Symposium on LISP and Functional
   Programming*, 1982.
3. T. Johnsson, "Efficient Compilation of Lazy Evaluation", *ACM
   SIGPLAN Symposium on Compiler Construction*, 1984. The G-machine.
4. M. Naylor and C. Runciman, "The Reduceron Reconfigured", *ICFP 2010*.
   Graph reduction in hardware.
5. The Urbit whitepaper (Yarvin, Monk, Dyudin, Pasco, 2016) and the Vere
   source for the jet dashboard's matching and registration discipline.
6. B. Jay and T. Given-Wilson, "A Combinatory Account of Internal
   Structure", *JSL* 76(3), 2011, §3, for what the runtime is allowed to
   do that the calculus is not.

(Entries 1 to 4 are from memory and should be checked against the
sources before they are cited anywhere.)

## 7. Relationship to the other repository

`~/ski-in-ski` holds the paper, the reference artifact, and the numbers.
This repository holds the language (`SURFACE-LANGUAGE-DESIGN.md`) and
the runtime (this note). The dependency runs one way: the runtime must
reproduce the artifact's counts, and the language compiles to the
artifact's ABI; nothing in the paper depends on either.
