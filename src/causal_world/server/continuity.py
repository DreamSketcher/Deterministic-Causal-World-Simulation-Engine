"""v0.6 step 6: multi-life continuity — one world, N lives, one archive.

Ratified contract: experiments/proposals/v06_step6_continuity_contract.md §9.

Concepts (kept separate by construction):
  WORLD  = one SQLite archive; identity in its meta (seed/regions/agents/
           ruleset_version + life registry rows). One active writer.
  LIFE   = a segment [from_tick, to_tick) during which PlayerAgentSystem's
           ``controlled`` pointer names one agent. Ends by death,
           abdicate (explicit close while alive) or tick_limit.
  SESSION= one transport control period driving exactly one life.

No journal-format change, no kernel change: life boundaries live in the
identity meta as one JSON row per life (``life:<n>``), and the replayed
decision stream must reproduce them — the player.act sequence is the
cross-check (guard ``takeover_mismatch``), never the source. An empty
segment (registered, zero decisions) and a last death are therefore
distinguishable without consulting anything hidden (§9/Q3).

Takeover = the step-3 replay machinery, nothing more:
  view.meta → create_world(persist=None) → feed DecisionStreamReader
  stream, switching ``controlled`` per life schedule → the FULL canonical
  state is reproduced (verified by journal-hash and final-state-hash
  equality before the live archive is handed over). This module keeps a
  single rule honest: the archive alone suffices — no old session state is
  ever required (Check A, ratified).

Succession is birth-fact-only (no state is transferred, ever): living
descendants of the previous agent in deterministic BFS (generation, then
birth_tick, then id); otherwise the ELDEST living agent — a successor of
management, not a relative; the interface and meta both say ``elder``.
No descendants and no living agents → ``no_heir``: terminal. The pool is a
finite budget (O5 carrying capacity) — no regeneration, no restart, no
silent fresh archive.
"""

from __future__ import annotations

import hashlib
import json
import re

from causal_world.world.rules import RULESETS, get_ruleset

#: world names are strict identifiers, never paths (§9/Q4): lowercase
#: alphanumerics with interior ``_``/``-``, 1..32 chars. Dots, slashes and
#: capital letters are rejected before any filesystem call is made.
WORLD_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

LIFE_KEY = "life:{}"
#: written at finalize: the canonical state hash at the head, so every
#: later takeover can verify FULL reproduction, not just row counts
FINAL_STATE_KEY = "final_state_hash"

END_REASONS = ("death", "abdicate", "tick_limit")


class TakeoverError(Exception):
    """A takeover refusal that must not touch the world: mismatched
    history (replay ≠ archive), or a terminal world (no heir)."""

    def __init__(self, code: str, msg: str, extra: dict | None = None):
        super().__init__(msg)
        self.code = code
        self.msg = msg
        self.extra = extra or {}

    def to_dict(self) -> dict:
        out = {"type": "error", "code": self.code, "msg": self.msg}
        out.update(self.extra)
        return out


def world_name_ok(name: object) -> bool:
    return isinstance(name, str) and WORLD_NAME_RE.match(name) is not None


def ruleset_name_for_version(version: str) -> str:
    for name, cls in RULESETS.items():
        if cls.ruleset_version == version:
            return name
    raise TakeoverError(
        "takeover_mismatch", f"no known ruleset for version {version!r}"
    )


# ------------------------------------------------------- life meta rows ---
def life_record(
    n: int, agent: str, from_tick: int, succession: str,
    end: str | None = None, to_tick: int | None = None, decisions: int = 0,
    session: str | None = None,
) -> tuple[str, str]:
    """(meta_key, canonical JSON) for one life. Deterministic encoding.
    ``session`` is an operational hint (resume+close releases a busy
    world) — never part of world causality."""
    rec = {
        "n": n,
        "agent": agent,
        "from_tick": from_tick,
        "succession": succession,  # genesis | lineage | elder
        "end": end,               # None while open; END_REASONS when closed
        "to_tick": to_tick,
        "decisions": decisions,
    }
    if session is not None:
        rec["session"] = session
    return LIFE_KEY.format(n), json.dumps(rec, sort_keys=True)


def read_lives(view) -> list[dict]:
    """Life rows from archive meta, ordered by n; malformed rows refuse."""
    out: list[dict] = []
    for key, value in sorted(view.meta_all().items()):
        if not key.startswith("life:"):
            continue
        try:
            rec = json.loads(value)
        except json.JSONDecodeError as e:
            raise TakeoverError("takeover_mismatch", f"{key}: {e}") from e
        if (
            rec.get("n") != int(key.split(":")[1])
            or not isinstance(rec.get("agent"), str)
            or not isinstance(rec.get("from_tick"), int)
            or rec.get("succession") not in ("genesis", "lineage", "elder")
            or (rec.get("end") is not None and rec["end"] not in END_REASONS)
        ):
            raise TakeoverError("takeover_mismatch", f"{key}: malformed row")
        out.append(rec)
    out.sort(key=lambda r: r["n"])
    if not out:
        raise TakeoverError(
            "takeover_mismatch", "world archive has no registered life"
        )
    for i in range(1, len(out)):
        prev, cur = out[i - 1], out[i]
        if cur["from_tick"] != prev.get("to_tick"):
            raise TakeoverError(
                "takeover_mismatch",
                f"life {cur['n']} starts at {cur['from_tick']}, previous "
                f"ended at {prev.get('to_tick')!r}",
            )
    return out


def cross_check_streams(lives: list[dict], view) -> None:
    """Guard: every journaled player.act belongs to the life whose pointer
    the schedule claims for its tick. The stream never defines boundaries —
    it only falsifies a forged/damaged meta."""
    windows = []
    for i, life in enumerate(lives):
        end = life["to_tick"]
        if end is None:
            end = lives[i + 1]["from_tick"] if i + 1 < len(lives) else 10**18
        windows.append((life["from_tick"], end, life["agent"]))
    for t in view:
        if t.operation != "player.act":
            continue
        subject = next(
            (w.entity for w in t.writes if w.field == "last_action"), None
        )
        if subject is None:
            continue  # genesis-style pre-writes carry no decision
        for lo, hi, agent in windows:
            if lo <= t.tick < hi:
                if agent != subject:
                    raise TakeoverError(
                        "takeover_mismatch",
                        f"T{t.tick}: stream says {subject}, meta says {agent}",
                    )
                break
        else:
            raise TakeoverError(
                "takeover_mismatch", f"T{t.tick}: player.act outside any life"
            )


# --------------------------------------------------------- heir selection --
def choose_heir(deceased: str, agents: dict[str, dict]) -> tuple[str, str] | None:
    """Pure and deterministic. ``agents`` maps every AGENT to
    ``{alive, parent_id, birth_tick}``; only living candidates are eligible.

    Returns (heir, "lineage"|"elder") or None (terminal). BFS over
    descendants of the deceased: a generation is scanned before its
    children — dead links are TRAVERSED (a dead parent does not erase a
    living grandchild) but only living agents are eligible; within a
    generation: birth_tick, then id (§9/Q1 — never collection order).
    Elder fallback: the living agent with the smallest birth_tick, tie by
    id — a successor of MANAGEMENT, not a relative.
    """
    living = {a for a, v in agents.items() if v.get("alive")}
    kids: dict[str, list[str]] = {}
    for a, v in agents.items():
        p = v.get("parent_id")
        if isinstance(p, str):
            kids.setdefault(p, []).append(a)

    def by_age(a: str) -> tuple:
        b = agents[a].get("birth_tick")
        return (b if isinstance(b, int) else 10**18, a)

    frontier, seen = [deceased], {deceased}
    while frontier:
        nxt = {c for a in frontier for c in kids.get(a, ())} - seen
        seen |= nxt
        eligible = sorted((c for c in nxt if c in living), key=by_age)
        if eligible:
            return eligible[0], "lineage"
        frontier = sorted(nxt, key=by_age)
    if not living:
        return None
    return min(living, key=by_age), "elder"


def agents_map(state) -> dict[str, dict]:
    return {
        a: {
            "alive": bool(state.get(a, "alive")),
            "parent_id": state.get(a, "parent_id"),
            "birth_tick": state.get(a, "birth_tick"),
        }
        for a in state.entities_with_prefix("agent:")
    }


# ------------------------------------------------------------- the replay --
def _prepare_replay(db_path: str, *, require_closed: bool):
    """Read the archive and rebuild the world up to its head, but do not
    step it yet. Shared by the takeover replay and the read-only replay
    to an arbitrary tick, so both follow exactly the same pointer
    schedule and the same decision stream."""
    from causal_world.observer.journal import JournalView
    from causal_world.player import (
        DecisionChannel,
        DecisionStreamReader,
        attach_player_channel,
    )
    from causal_world.systems.player import PlayerAgentSystem
    from causal_world import create_world

    with JournalView(db_path) as view:
        meta = view.meta_all()
        lives = read_lives(view)
        cross_check_streams(lives, view)
        stream = DecisionStreamReader.actions_from(view)
        head_tick = view.tick_range()[1] + 1
    if require_closed and lives[-1]["end"] is None:
        raise TakeoverError(
            "world_busy",
            f"life {lives[-1]['n']} is still open on this archive",
            {"session": lives[-1].get("session")},
        )
    for key in ("seed", "regions", "agents", "ruleset_version"):
        if meta.get(key) is None:
            raise TakeoverError("takeover_mismatch", f"meta lacks {key}")

    sim = create_world(
        seed=int(meta["seed"]),
        ruleset=get_ruleset(ruleset_name_for_version(meta["ruleset_version"])),
        ticks=0,
        regions=int(meta["regions"]),
        agents=int(meta["agents"]),
        persist=None,
    )
    # pointer schedule from the meta rows; dead-pointer stretches consume
    # nothing on both sides (identical liveness discipline ⇒ alignment)
    by_tick = sorted(lives, key=lambda life: life["from_tick"])
    idx = 0

    def _point(tick: int) -> None:
        nonlocal idx
        while idx + 1 < len(by_tick) and by_tick[idx + 1]["from_tick"] <= tick:
            idx += 1
        for system in sim.systems:
            if isinstance(system, PlayerAgentSystem):
                system.controlled = by_tick[idx]["agent"]

    _point(0)
    attach_player_channel(sim, DecisionChannel(actions=list(stream)))
    return sim, meta, lives, head_tick, _point


def _replay_ticks(sim, point, count: int) -> None:
    for tick in range(count):
        point(tick)
        sim.step()


def journal_prefix_hash(db_path: str, upto_tick: int) -> str:
    """Canonical journal hash of the recorded history BEFORE ``upto_tick``.

    The same definition as ``journal.hash()``: sha256 over newline-joined
    canonical records in id order, restricted to transitions of ticks
    ``0 .. upto_tick-1`` — exactly the transitions a replay of that many
    ticks produces.
    """
    from causal_world.kernel.canonical import canonical_json
    from causal_world.kernel.transition import transition_record
    from causal_world.observer.journal import JournalView

    hasher = hashlib.sha256()
    with JournalView(db_path) as view:
        # Genesis and the FIRST step both live at tick 0, so "tick < 0"
        # is empty while a zero-step replay already contains genesis. The
        # archive records how many genesis transitions it wrote (additive
        # meta, outside journal.hash); old archives without it are read
        # through the genesis.* operations, which no step produces.
        genesis_count = view.meta("genesis_transitions")
        genesis_ids = set()
        if upto_tick == 0 and genesis_count is None:
            genesis_ids = {
                t.id for t in view
                if t.tick == 0 and t.operation.startswith("genesis.")
            }
        for transition in view:
            if upto_tick == 0:
                if genesis_count is not None:
                    keep = transition.id is not None and (
                        transition.id <= int(genesis_count)
                    )
                else:
                    keep = transition.id in genesis_ids
            else:
                keep = transition.tick < upto_tick
            if keep:
                hasher.update(
                    (canonical_json(transition_record(transition)) + "\n")
                    .encode("utf-8")
                )
    return hasher.hexdigest()


def replay_head(db_path: str):
    """Reproduce the world at the archive head from the archive alone.

    Returns (sim, archive, lives). ``sim`` has the FULL state (verified
    against the journal hash and, when recorded, the final-state hash);
    ``archive`` is the reopened SqliteArchive ready to be handed to the
    sim; ``lives`` are the meta rows. Raises TakeoverError — before any
    write — if history does not reproduce.
    """
    from causal_world.simulation.archive import SqliteArchive

    sim, meta, lives, head_tick, point = _prepare_replay(
        db_path, require_closed=True
    )
    _replay_ticks(sim, point, head_tick)

    archive = SqliteArchive(db_path)  # reopen: _last_id/_total from disk
    # CHECK A as a permanent guard: the replay reproduces the FULL history
    # (canonical journal) and, when recorded, the canonical head STATE —
    # sufficiency of the decision stream is verified, not assumed.
    if sim.journal.hash() != archive.hash():
        archive.close()
        raise TakeoverError(
            "takeover_mismatch",
            "replayed history does not reproduce the archive "
            "(config drift or a forged/damaged journal)",
        )
    if meta.get(FINAL_STATE_KEY) and sim.state.hash() != meta[FINAL_STATE_KEY]:
        archive.close()
        raise TakeoverError(
            "takeover_mismatch", "replayed STATE differs from the recorded head"
        )
    # hand over: one counter continues, so ids keep ascending by construction
    sim.journal = archive
    sim.index = archive
    return sim, archive, lives


def replay_until(db_path: str, tick: int):
    """Replay the world to ``tick`` and verify its journal prefix.

    READ-ONLY: unlike :func:`replay_head` it does not require a closed
    life, does not open the archive for writing and does not hand it
    over. Returns ``(sim, prefix_hash)`` where ``sim.state.tick == tick``
    and ``prefix_hash`` is the canonical hash of the archive's transitions
    below that tick; the replayed in-memory journal must hash to exactly
    that value, or the prefix is not the recorded history.

    The caller still owns the state comparison: the archive does not
    store per-tick state hashes, so an experiment compares
    ``sim.state.hash()`` with the uninterrupted run it recorded.
    """
    tick = int(tick)
    if tick < 0:
        raise ValueError("replay_until needs a non-negative tick")
    sim, _meta, _lives, head_tick, point = _prepare_replay(
        db_path, require_closed=False
    )
    if tick > head_tick:
        raise TakeoverError(
            "takeover_mismatch",
            f"archive ends at tick {head_tick}, cannot replay to {tick}",
        )
    _replay_ticks(sim, point, tick)
    expected = journal_prefix_hash(db_path, tick)
    if sim.journal.hash() != expected:
        raise TakeoverError(
            "takeover_mismatch",
            f"replayed history up to tick {tick} does not reproduce the archive",
        )
    return sim, expected
