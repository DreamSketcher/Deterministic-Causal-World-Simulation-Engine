# v0.6 step 2 — DESIGN (for review before code): Heredity + Ruins via a dormant pool (Option C)

**Status:** design, awaiting sign-off. No code yet.
**Decision:** Option C — pre-allocated dormant entities, activated by writes.
Zero changes to `kernel/`, resolver *logic*, or engine `step()`/`resolve()`.
**Freeze basis (already verified, commit `0960a67`):** the default world
(seeds 42 & 7, 2×10, 100 ticks) is bit-identical on the v0.1.0 kernel and
HEAD (`state_hash`/`journal_hash` equal; seed 42 == pinned
`DEFAULT_*_HASH`). "Default world stays bit-identical" is a *proven*
invariant we must not break — this design keeps it by construction.

Your four nuances are adopted verbatim: (1) pool size = ruleset parameter,
fixed at genesis; (2) dormant-agent choice = addressable draw; (3) parent =
random alive in region for v0.6, selection-by-trait deferred to v0.7+;
(4) one ruin slot per region, updated (not duplicated) on re-extinction.

---

## Why a dormant pool (the resolver forces this)

`Resolver._validate` checks creation **per (entity, field)**: a write whose
`(entity, field)` is absent from the snapshot is allowed only if `old is
None` **and** `allow_creation` — and `step()` calls `resolve(snapshot,
proposals)` with `allow_creation=False` (only `initialize()` passes True).
So a mid-run write to a *not-yet-existing field* is rejected as
`field_not_found`.

Consequence: a newborn or a ruin cannot get a field it didn't have at
genesis. Therefore every entity that will ever be "born"/"activated" must
exist at genesis **with all its future fields present** (dormant
placeholders). Activation is then a write `old=placeholder -> new=real` to
an *existing* field — no creation, resolver untouched, determinism trivial.

This is why C needs a small **generator** change (to pre-create the
dormant entities) but no resolver/engine-logic change.

---

## Part 0 — Foundational enabler: dormant pool + ruin slots at genesis

**`world/generator.py`** gains two duck-typed ruleset attributes (mirroring
the existing `extra_genesis_fields` hook; absent → 0 → default world
unchanged):

```
dormant_agents       : int   (extra agent slots, alive=False)
ruin_slots_per_region: int   (ruin slots per region, active=False)
```

* **Live agents** `agent:0 .. agent:{N-1}` — exactly as today (unchanged).
* **Dormant agents** `agent:{N} .. agent:{N+P-1}` — same field SET as a
  live agent (so every future write target exists) but `alive=False` and
  neutral placeholders (`health=0.0, hunger=0.0, immunity=0.0,
  infected=False, risk_tolerance=0.0, max_health=0.0, parent_id="none",
  region="none"`). They consume **no** genesis draws (blank slates); their
  real attributes come from inheritance at birth. Because draws are
  addressable per entity (I8), adding `agent:{N}..` never shifts the
  genesis of `agent:0..{N-1}`.
* **Ruin slots** `ruin:{r}` for each region (× `ruin_slots_per_region`) —
  `active=False, region="region:{r}", type="", age=0, resource_food=0.0,
  resource_knowledge=0.0`. New entity prefix `ruin:`; no existing system
  reads it, so zero interference.

**Existing systems already ignore the pool:** metabolism (`agents.py:45`),
census (`:77-79`, counts alive only), disease (`disease.py:82`) all skip
`alive=False`. So dormant agents are invisible until born — no system
edits needed to make the pool inert.

**New schema fields** (game ruleset only, via `_field_types` + the
`extra_genesis_fields` hook for live agents):

| entity | field | type | genesis (live) | genesis (dormant/ruin) |
|---|---|---|---|---|
| agent | `parent_id` | str | `"none"` (gen 0) | `"none"` |
| agent | `max_health` | float | = its genesis `health` | `0.0` |
| ruin | `active` | bool | — | `False` |
| ruin | `region` | str | — | `"region:{r}"` |
| ruin | `type` | str | — | `""` |
| ruin | `age` | int | — | `0` |
| ruin | `resource_food` | float | — | `0.0` |
| ruin | `resource_knowledge` | float | — | `0.0` |

`NON_NEGATIVE_FIELDS` += `max_health, age, resource_food,
resource_knowledge`; `UNIT_INTERVAL_FIELDS` unchanged (immunity already
there). Ruin resources are flattened to scalars because `canonical_token`
serializes only None/bool/int/float/str (no dicts).

---

## Part 1 (2a) — Heredity: `BirthSystem` (new `systems/heredity.py`)

Runs once per tick, per region. All randomness is addressable draws
(purposes declared in the game ruleset).

**Trigger (birth occasion).** For region R at tick t, a birth is *eligible*
iff: `food_stock[R] > BIRTH_FOOD_MIN` **and** `population[R] <
CARRYING_CAP[R]` **and** at least one dormant agent is unclaimed. Then draw
`birth.occurrence` (index = region ordinal) against a rate that rises with
food surplus — logistic growth toward carrying capacity, not replacement.
(Carrying capacity = the pool: `N_live + P` globally, or a per-region share
— open question O1.)

**Choose the dormant slot (nuance 2 — addressable, not `[0]`, not
`random.choice`).** Collect free dormant ids in a canonical (sorted) list;
pick `free[k]` where `k = int(draw("birth.select", R, t, idx) * len(free))`.
Sorted list + addressable draw ⇒ deterministic, no order artifact.

**Choose the parent (nuance 3 — random alive in region for v0.6).**
`alive_agents[R]` sorted; `parent = alive_agents[int(draw("birth.parent",
R, t, idx) * len(alive_agents[R]))]`. Selection-by-health/wealth is a
v0.7+ ruleset variant (swap the parent-choice draw for a trait-weighted
one) — the mechanism is identical, only the pick rule changes.

**Inheritance + mutation** (TZ formulas; `m = (draw("birth.mutation",
child, t, k) - 0.5) * MUT_SCALE`, one draw per inherited trait):

```
immunity       = clamp(0.30 + 0.40 * parent.immune_memory + m0, 0, 1)
max_health     = clamp(parent.max_health * 0.90 + m1, 1, 100)
risk_tolerance = clamp(parent.risk_tolerance * 0.70 + 0.30 * draw + m2, 0, 1)
health         = max_health          # born at full health
hunger         = 0.1                 # newborn
infected       = False
region         = R
parent_id      = parent.entity
alive          = True                # the activation write
```

**Transition `agent.birth`** (one per birth):
*reads:* `parent.immune_memory`, `parent.max_health`,
`parent.risk_tolerance`, `region[R].food_stock`, `region[R].population`,
`child.alive` (=False). *writes:* the child's nine fields above
(`alive False->True` is the activation). *draws:* `birth.occurrence`,
`birth.select`, `birth.parent`, `birth.mutation×3`. All recorded ⇒ the
lineage (`parent_id`) and every inherited value are in the causal graph.

**Why immunity drifts (the emergent result).** In the compost world,
survivors accumulate `immune_memory` (each infection teaches +0.35). A
child's `immunity = 0.30 + 0.40*parent.immune_memory`, so children of
seasoned survivors start more resistant. Over generations, as the living
pool's `immune_memory` rises, `avg(immunity)` of newborns rises —
**natural selection, not a programmed trend.** Measured by CausalQuery:
generation = depth of the `parent_id` chain (gen 0 = `parent_id="none"`);
group newborns by generation, average `immunity`, show the upward drift.

---

## Part 2 (2b) — World memory: `RuinSystem` + `ExplorationSystem` (new `systems/ruins.py`)

**RuinSystem (per region, per tick):**
* **Activation (nuance 4 — one slot, updated):** if `population[R] == 0`
  and slot `ruin:{R}.active == False` → write `active=True`,
  `type=<derived>`, `age=0`, `resource_food = f(region food_stock at
  extinction)`, `resource_knowledge = 0.0` (knowledge is an epoch-era
  resource; v0.6 keeps it 0 — see O3). Because every region starts
  populated (compost survives), `population==0` means *extinction*, not
  "never populated."
* **Degradation:** if `active` → `age += 1`,
  `resource_food *= RUIN_DECAY` (e.g. 0.995/tick).
* **Collapse:** if `age > RUIN_MAX_AGE` or `resource_food <= 0.01` →
  `active=False`, resources 0 (slot dormant again).
* **Re-extinction:** if the region repopulates (births) then dies again,
  the same slot re-activates with fresh `age=0`/`type`/resources — updated,
  never duplicated (one slot per region ⇒ no "which of three ruins"
  ambiguity).

`type` derived from region state at extinction (O4): e.g. `food_stock`
high → `"granary"`, else `"settlement"`. Deterministic from the snapshot.

**ExplorationSystem (per alive agent, per tick):**
* Eligible iff agent's region has `ruin:{R}.active == True` and
  `resource_food > 0`. NPC agents explore on an addressable draw
  `agent.explore` (gated by `risk_tolerance`); the player agent's explore
  is a `player.decision` (step 1 mechanism) — same transition shape.
* Transition `agent.explore`: *reads* `ruin:{R}.resource_food`,
`agent.hunger`; *writes* `agent.hunger -= min(EXPLORE_FOOD,
ruin.resource_food)` (bonus), `ruin.resource_food -= <taken>`; *draws*
`agent.explore`. The bonus and the ruin draw-down are both in the agent's
causal trace ⇒ "you found a granary your ancestors built; it fed you."

---

## Part 3 — Determinism (why two runs are bit-identical)

Every choice is an addressable draw keyed by `(tick, entity, purpose,
index)` (invariants I7/I8): birth occurrence/select/parent/mutation, ruin
activation (deterministic from the snapshot — no draw needed), exploration.
Same `world_seed` ⇒ same draw values ⇒ same births, same parents, same
lineage, same ruin lifecycles ⇒ **bit-identical `state_hash` and
`journal_hash`**. The player decision stream (step 1) uses purpose
`player.decision`, disjoint from `birth.*`/`agent.explore`, so NPC
demography is independent of player input; with the *same* decision stream
replayed, a player-controlled world is bit-identical too.

---

## Part 4 — Default world stays bit-identical (double guarantee)

1. `DefaultWorldRules` (and every research ruleset) defines **no**
   `dormant_agents` / `ruin_slots_per_region` ⇒ generator creates **zero**
   dormant agents and **zero** ruin slots ⇒ genesis is byte-for-byte the
   v0.1 genesis ⇒ `DEFAULT_STATE_HASH`/`DEFAULT_JOURNAL_HASH` preserved
   (the invariant we just proved holds on HEAD).
2. Research `default_systems` contain **no** `BirthSystem`/`RuinSystem`/
   `ExplorationSystem` ⇒ even if a stray pool existed, nothing would
   activate it.

Only `PlayerLifeRules` (0.6.0) opts into the pool + the three systems, so
only the game world changes. Research and game remain different worlds
over one frozen kernel.

---

## Part 5 — Files touched (all freeze-consistent)

| file | change | core? |
|---|---|---|
| `world/generator.py` | dormant pool + ruin slots from duck-typed ruleset attrs | no (genesis, additive, default-inert) |
| `world/rules.py` | `PlayerLifeRules`: schema fields, pool sizes, `birth.*`/`agent.explore` purposes, `default_systems +=` the three | no (ruleset) |
| `systems/heredity.py` (new) | `BirthSystem` | no (system) |
| `systems/ruins.py` (new) | `RuinSystem`, `ExplorationSystem` | no (systems) |
| `simulation/engine.py` | registry `+= BirthSystem, RuinSystem, ExplorationSystem` (additive, like every system since v0.2) | no (registration only; step/resolve untouched) |
| `tests/test_heredity.py`, `tests/test_ruins.py` (new) | see Part 6 | — |
| `kernel/`, resolver logic, engine `step()`/`resolve()` | **untouched** | — |

---

## Part 6 — Tests (149 → ~167)

*Generator:* pool + ruin slots created with correct placeholders; **default
world bit-identical** (re-assert pinned hashes with the new generator).
*BirthSystem:* birth fires only when eligible; dormant choice is
addressable & deterministic; parent is alive & in-region; inheritance
formulas exact (immunity/max_health/risk_tolerance); mutation addressable;
newborn `alive=True` with inherited attrs; `parent_id` lineage correct;
population never exceeds carrying capacity.
*Heredity drift:* over enough ticks, `avg(immunity)` of newborns rises with
generation depth (selection); same seed ⇒ identical drift curve.
*RuinSystem:* ruin activates on extinction; degrades (age↑, resources↓);
collapses at `age>max`; one slot per region (no duplicates); re-extinction
updates the same slot.
*ExplorationSystem:* agent finds active ruin ⇒ hunger↓ bonus, ruin
resources↓, both in the agent's causal trace.
*Determinism:* game ruleset replays bit-identically (same seed); and with a
fixed decision stream (same seed + stream).

---

## Open design questions (confirm before I write code)

* **O1 — carrying capacity & birth rate.** Global cap `N+P`, or per-region
  share? Birth rate as a function of food surplus — target ~10 generations
  within a runnable tick budget (e.g. 2 regions × 300 agents × ~1500 ticks
  for the drift test). Need a maturity gate (only agents older than X ticks
  may be parents), or is any alive agent eligible for v0.6?
* **O2 — mutation scale.** `MUT_SCALE` for immunity/max_health/risk (e.g.
  ±0.05)? Too small ⇒ no variance; too large ⇒ swamps inheritance.
* **O3 — exploration bonus scope.** v0.6 = **food only** (survival-
  relevant, existing fields); `resource_knowledge` stays 0 until epochs
  (v0.6.1) give knowledge a use. OK to defer knowledge?
* **O4 — ruin `type` derivation.** From region state at extinction
  (`granary` if food_stock high, else `settlement`)? Or a fixed type for
  v0.6?
* **O5 — pool size default.** `dormant_agents = N` (2× total) enough for
  the drift test + a game session? Ruin slots = 1/region (your call).
* **O6 — heredity base ruleset.** `PlayerLifeRules` currently extends
  `CompostRules` (surviving world). Keep compost as the game base, so the
  dynasty has a world that doesn't collapse at t573?

If these look right (or you give the values), I build 2a then 2b, each with
tests + a report section, kernel/resolver/engine-logic untouched, and
re-assert the pinned default-world hashes as the freeze guard.
