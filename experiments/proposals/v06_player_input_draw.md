# Proposal v0.6-01 — Player-supplied decision draws

**Status:** accepted (discussion 2026-10-12), implemented in this commit.
**Scope:** v0.6 step 1 of 5. The single foundational touch the LIFE phase
depends on. v0.6 leaves `src/causal_world/kernel/` **untouched** — the
change is confined to `systems/base.py` (builder) and `world/rules.py`
(purpose + ruleset seed).

## The touch, in one sentence

Add one optional parameter to `TransitionBuilder.draw(... value=None)`;
when a value is supplied the recorded `RandomDraw.value` is *that* value
instead of the seed-derived `rng.draw()`.

## Why (the game contract)

The LIFE phase puts the player in control of one agent. The player's
choice must be a **first-class causal node** — recorded, addressable,
replayable, and distinguishable in AUTOPSY from a dice roll.

The contract, stated plainly: **dice can never veto an explicit
choice.** The naive design — map the chosen card through
`rng.draw(...) -> float` and gate it on a threshold — breaks this: if
the roll exceeds the threshold the kernel cancels the player's own
action. That is exactly the "died to randomness 0.17 < 0.43" unfairness
the bifurcation mechanic exists to redress; we must not reintroduce it
at the input layer.

The correct separation:

```
player owns the DECISION   ->  draw(purpose="player.decision", value=<supplied>)
world owns the OUTCOME     ->  ordinary rng draws (disease.infection en
                               route, agriculture.crop_variance, ...)
```

So the agent's *body* is still driven by the addressable dice (it can
die of infection regardless of what the player chose — "the world does
not adjust"), but the *choice* itself is the player's, recorded verbatim.
AUTOPSY then reads honestly: `t800 player.decision=migrate_north (your
choice) -> t805 disease.infection 0.002<0.016 (dice: infected en route)`.

## Current mechanism (unchanged parts)

`RandomSource.draw(tick, entity, purpose, index)` is a pure BLAKE2b
function of `(world_seed, rng_version, tick, entity, purpose, index)`
(invariants I7/I8: no global RNG state, no order/stream dependence). A
player's choice cannot be such a draw — its value would be
seed-determined, not player-determined. `PurposeRegistry.require()`
raises `UnknownPurposeError` for undeclared purposes. `validate_transition`
checks **writes only** (non-negative, unit-interval, temperature); it
never constrains draw values, so a supplied value outside `[0,1)` is
not a violation.

## The change

`src/causal_world/systems/base.py` — `TransitionBuilder.draw`:

```python
def draw(self, purpose, entity, index=0, threshold=None, value=None):
    if value is None:
        value = self._rng.draw(self._tick, entity, purpose, index)   # unchanged
    elif self._rng.purposes is not None:
        # Supplied (player) value: bypass the RNG, but keep the invariant
        # that every purpose appearing in the journal is declared.
        self._rng.purposes.require(purpose)
    outcome = value if threshold is None else (value < threshold)
    draw = RandomDraw(purpose=purpose, value=value, threshold=threshold,
                      outcome=outcome, entity=entity, index=index)
    self._draws.append(draw)
    return draw
```

`src/causal_world/world/rules.py` — a game-ruleset **seed** declaring the
purpose (base world unchanged):

```python
class PlayerLifeRules(CompostRules):          # surviving world + disease + immune_memory
    ruleset_version = "0.6.0"
    purposes = {**PURPOSES, "player.decision": "player-supplied action index (float), not a probability"}
    # default_systems inherited from compost for now; PlayerAgentSystem is added in step 3.
```

## Why every frozen guarantee survives

* **I7/I8 (addressable RNG):** the rng path is byte-identical; the
  supplied path never calls `rng.draw`, so it introduces no order or
  stream dependence and no hidden global state.
* **Determinism, redefined as "given the decision stream":** same
  `world_seed` **and** same supplied values → bit-identical journal. The
  stream is *self-describing* — it is recorded in the journal as the
  `player.decision` draws and their values — so replay re-supplies it
  from the journal (full sim-level replay is step 3, with
  `PlayerAgentSystem`).
* **Atomicity / conflict resolution:** draws do not participate in
  resolution (writes do); a transition carrying a supplied draw resolves
  and commits exactly as before.
* **Canonical hash:** `RandomDraw` serializes unchanged; `value` is
  canonicalized with its type tag (`canonical_token`).
* **Read-only observer (v0.4) / query engine (v0.5):** unchanged — they
  read draws as recorded; `player.decision` is just another purpose to
  them (and AUTOPSY's personal-chain filter keys on it).
* **`kernel/` is not touched.** The change lives in `systems/base.py`
  (builder) and `world/rules.py` (purpose + ruleset seed).

## Purpose declaration & separate fingerprint

`player.decision` is declared **only** in the game ruleset. The base and
research rulesets (`default`, `immune`, `compost`, ...) neither declare
it nor change: their draw streams and fingerprints are untouched (adding
a purpose to a *different* ruleset cannot affect another's addressable
draws — purpose is part of the hash payload). A world with a player is a
**different ruleset_version (0.6.0) → different fingerprint** from the
NPC research worlds. That is the intended, agreed separation: research
and game are different worlds over the same frozen kernel. The supplied
path calls `require()`, so an undeclared purpose cannot leak into any
journal.

## Value-type convention (pins determinism)

`canonical_token` type-tags values (`i:2` ≠ `f:2.0`), so the supplied
value's **type is part of the hash**. To match `RandomDraw.value: float`
and avoid int/float canonicalization drift, the game records a player
decision as `float(action_index)` with `threshold=None` (hence
`outcome == value`). The decision stream is a list of floats per
`(tick, agent)`, replayed type-identically. `player.decision` values are
**action indices**, not probabilities — semantically distinct from the
`[0,1)` rng draws; AUTOPSY separates them by `purpose`, and maps index →
action name in the ruleset/UI (not the kernel).

## Backward compatibility

`value=None` (the default) reproduces today's behavior byte-for-byte; no
existing call site passes `value`, so none change. All 142 prior tests
must stay green.

## Test plan (`tests/test_player_input.py`)

1. backward-compat: `draw(value=None)` equals the oracle `rng.draw`,
   outcome logic unchanged;
2. supplied value: `draw(value=X)` records `value=X` (≠ the seed roll),
   `outcome=X` when `threshold is None`;
3. purpose enforcement: a supplied draw with an undeclared purpose raises
   `UnknownPurposeError`;
4. determinism-given-decisions: same seed + same supplied value →
   identical journal hash;
5. supplied-vs-rng divergence: same address, supplied value ≠ rng value →
   different journal hash (proves the value, not the seed, is recorded);
6. value-type convention: `canonical_token(2.0) != canonical_token(2)`;
   supplying `2.0` twice is identical;
7. game ruleset: `player_life` declares `player.decision`, runs
   bit-identically twice, and is distinct (version + purposes) from
   `compost`.

## Scope boundary

* **In step 1:** the builder mechanism, the `player.decision` purpose,
  the `PlayerLifeRules` seed (compost base, systems unchanged), unit +
  ruleset determinism tests.
* **Deferred:** `PlayerAgentSystem` + the synchronous input channel and
  full sim-level replay-from-journal (step 3); heredity + `RuinSystem`
  (step 2); epochs (v0.6.1, epoch-gated not ruleset-swapped);
  `BiographyCard` (step 4); thin sim-server prototype (step 5).

## What this is not

Not a kernel change. Not a new RNG. Not a change to any existing
ruleset's draw stream or fingerprint. Not pay-to-win randomness — the
player's choice is a deterministic input; dice govern only outcomes.
