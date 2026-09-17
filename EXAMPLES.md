# Examples

*2026-09-16. Every example is given in both spellings of `SYNTAX.md`, then
its codegen as produced by the reference expander (`aviary-kernel`'s
bracket abstraction, the same one the paper's artifact uses), then the
behavioral check that was actually run: values were read by applying
results to fresh marker atoms, never by reading combinator syntax. Atom
counts are tree-atoms. Where a number is not given, it was not measured.*

## 1. Numerals: increment, decrement, addition, subtraction

Numerals are Scott numerals, a declared type like any other. Applying a
numeral to two continuations is a case analysis: `Zero` selects the
first, `Suc m` hands `m` to the second. That is why decrement is one
case and no recursion.

Unicode:
```
nat ≡ Zero ∣ Suc nat

arith ≔ {
  inc n   = Suc n
  dec n   = n ▹ { Zero  Zero ; Suc m  m }
  add m n = n ▹ { Zero  m    ; Suc k  Suc (add m k) }
  sub m n = n ▹ { Zero  m    ; Suc k  sub (dec m) k }
}
```

ASCII:
```
nat === Zero | Suc nat

arith := {
  inc n   = Suc n
  dec n   = n |> { Zero  Zero ; Suc m  m }
  add m n = n |> { Zero  m    ; Suc k  Suc (add m k) }
  sub m n = n |> { Zero  m    ; Suc k  sub (dec m) k }
}
```

`add` and `sub` recurse through the core's implicit self; `sub` reaches
`dec` by name because they share the core. Subtraction is truncated.

**Codegen.** The case form is application of the datum to its
continuations, so `dec n = n ▹ {…}` is `n Zero I` before abstraction.

| arm | atoms | term |
|---|---|---|
| `Zero` | 1 | `K` |
| `Suc` | 8 | `S (K K) (S (K (S I)) K)` |
| `inc` | 8 | `S (K K) (S (K (S I)) K)`, identical to `Suc`: the abstraction algorithm η-reduces `λn. Suc n` |
| `dec` | 7 | `S (S I (K K)) (K I)` |
| `add` | 42 | `Y`-tied; the first fourteen atoms are `Y` |
| `sub` | 43 | `Y`-tied |

A tail-recursive addition, `add m n = n ▹ { Zero m ; Suc k  add (Suc m) k }`,
is 44 atoms and takes 179 contractions to read out `add 2 3` against
173 for the version above; under call-by-name there is no reason to
prefer it.

**Checks run:** `inc 2 = 3`; `dec 3 = 2`; `dec 0 = 0`; `add 2 3 = 5`;
`add 0 4 = 4`; `sub 5 2 = 3`; `sub 2 5 = 0`. `dec 3` reaches weak head
normal form in 15 host contractions.

**Quoted:** `<inc>` is 268 atoms, `<dec>` 227, `<add>` 1,548. The level-1
tax is about 32 atoms per application node of the level-0 term, the
size of the `App` constructor's encoding.

## 2. A combinator three ways: `C`

`C f x y = f y x`, swap the arguments of a binary function.

Unicode / ASCII (identical, no glyph used):
```
C f x y = f y x               -- as an arm: a term, shared, applied at runtime
flip f x y ≔* f y x           -- as a macro: rewritten at the use site   (ASCII: :=*)

flipK₁ x y = C K x y          -- uses the arm
flipK₂ x y = flip K x y       -- uses the macro
```

| definition | atoms | term |
|---|---|---|
| `C` | 10 | `S (S (K S) (S (K K) S)) (K K)` |
| `flipK₁` (arm) | 11 | `S (S (K S) (S (K K) S)) (K K) K` |
| `flipK₂` (macro) | 5 | `S (K (S K)) K` |

Both `flipK` variants applied to `X1 X2` reduce to `X2`; `C K X1 X2`
reduces to `X2`. The macro version is smaller because `C` never exists
at runtime, the rewrite happened in the source; the arm version is one
shared node reused by every caller. This is the arm-versus-macro cost
model of `SURFACE-LANGUAGE-DESIGN.md` §3a: macros erase combinators,
arms share them.

## 3. A macro over pairs, and level 0 versus level 1

`swap p ≔* [3@p 2@p]` swaps a cell; `2@` and `3@` are the head and tail
projections on a Scott pair (`SYNTAX.md` §7).

Unicode:
```
swap p ≔* [3⊑p 2⊑p]
flipA q = swap q
```

ASCII:
```
swap p :=* [3@p 2@p]
flipA q = swap q
```

Macro expansion rewrites the arm to `pair (tl q) (hd q)`; the macro is
gone. Then:

- **Level 0 (unquoted):** `flipA` is 29 atoms,
  `S (S (K (S (S (K S) (S (K K) (S (K S) (S (K (S I)) K)))) (K K))) (S I (K (K I)))) (S I (K K))`.
  `flipA [X1 X2] K` reduces to `X2`. The program `flipA [K I] K` reduces to
  `I` in 40 host contractions.
- **Level 1 (quoted):** `<flipA>` is 1,057 atoms; the program
  `<flipA [K I] K>` is 1,809 atoms for a 49-atom program;
  `whnfF 41 <flipA [K I] K>` reaches weak head normal form in 29,191
  host contractions. Fuel 40 times out: fuel `k` permits `k`
  step-attempts of which the last must be the no-redex check.

## 4. A user interpreter with one added constructor

Unicode:
```
term5 ≡ S ∣ K ∣ I ∣ App term5 term5 ∣ Err
outcome ≡ Stepped term5 ∣ Done ∣ Errd
result ≡ RVal term5 ∣ RErr ∣ RTime

omega = S I I (S I I)

wf5Abs ≔ { stepErr acc = Errd }
wf5Omg ≔ { stepErr acc = omega }
answer ≔ wf5Abs ⊢ ⟨K I Err⟩₅
```

ASCII:
```
term5 === S | K | I | App term5 term5 | Err
outcome === Stepped term5 | Done | Errd
result === RVal term5 | RErr | RTime

omega = S I I (S I I)

wf5Abs := { stepErr acc = Errd }
wf5Omg := { stepErr acc = omega }
answer := wf5Abs |- <K I Err>@5
```

The object type is found by shape (`App` is the one constructor with two
fields of its own type); its declaration generates the five
constructors, the case form, and this arity's `sp` and `rb`. `stepS`,
`stepK`, `stepI` are the default arms for the leaves of those names;
`step` and the fuel loop are generated from the three declarations
(`SURFACE-LANGUAGE-DESIGN.md` §6c). `stepErr` is the one arm each core
writes, and the two cores differ in nothing else.

**Measured** (`python/tests/test_interpreter.py`): `wf5Abs` compiles to
768 atoms and `wf5Omg` to 771, each definition byte-identical to the
paper's hand-written terms (`st5Abs` 684, `st5Omg` 687, `sp5` 166,
`rb5` 81, `q5S` 275, `q5K` 121, `q5I` 107, the two arms 4 and 7, `omega`
6). With the paper's encoder and fuel 20 the T3 table reproduces
exactly: `Err` and `Err K` give ERR under `wf5Abs` and host divergence
under `wf5Omg`; `K I Err` and `I K` give VAL under both, with identical
contraction counts (574 and 438); `Ω` gives TIME under both (10,130).
The base interpreter, `term ≡ S ∣ K ∣ I ∣ App term term`, `maybe ≡
Nothing ∣ Just term`, `whnfF ≔ { step m = sp m nil stepS stepK stepI }`,
compiles to the paper's 618-atom `whnfF` byte for byte, with every
intermediate definition identical (`step` 569, `sp` 126, `rb` 74,
`stepS` 237, `stepK` 105, `stepI` 92), and `whnfF 3 ⟨I K⟩` reaches weak
head normal form in exactly 340 host contractions, decoding to
`Just ⟨K⟩`. The `answer` line is not yet run: `⊢` and `⟨ ⟩` are step 4.

## 5. A value lookup

Unicode:
```
prog ≔ ⟨I ∵/k/three⟩₍₎
```

ASCII:
```
prog := <I ?^/k/three>@[]
```

Inside `< >` the alphabet is the default interpreter's object type
`{S, K, I, App, Scry}`; `/k/three` is a value of the path type, a list
of two segment tags; `?^` wraps it in `Scry`. Fuel is elided, so the
executable is `wfN E policy <prog>` with `E` the resolver the runtime
supplied at boot, whose lookup arm dispatches on the head segment `k`
through its mount table and hands `three` to the kernel's `peek`. The
`I` arm fires; the walker finds `Scry` in head position and applies `E`
to the path; `oJust <K>` splices and reduction continues to `<K>`;
`oNothing` is a reported miss; `oNotYet` blocks, and the runtime re-runs
from the top once the fact arrives, which is sound because the namespace
is append-only. Not yet run in the surface; the mechanism is the paper's
§6.2 and §6.3, which were.

## 6. What was measured and what was not

Measured, in this order, on the reference expander and reducer:
sections 1 to 4 in full (section 4's `answer` line excepted). Section 5 describes the paper's verified
mechanism in the surface's notation and has not been compiled from that
notation; quotation and the level-1 run are the next step, after which
section 5 and section 4's `answer` become measured statements.
