"""Cross-ruleset comparison for the v0.3.1 structural diagnosis.

Reads the committed SQLite archives of several runs (same seed/scale) and
emits one markdown comparison document: the survival table, death-mechanism
mixes and the verdict. Purely post-hoc — reads the journal only.

Usage:
    python3 experiments/compare_rulesets.py \
        --out experiments/reports/v031_diagnosis.md \
        baseline=runs/survival_seed7.db \
        immune=runs/survival_seed7_immune.db \
        iron_health=runs/survival_seed7_iron_health.db ...
"""

from __future__ import annotations

import argparse
import time

from survival import DeathClassifier, SqliteArchive, collect_records


def summarize(name: str, db: str, ticks: int) -> dict:
    t0 = time.time()
    archive = SqliteArchive(db)

    def meta(key: str):
        try:
            return archive.get_meta(key)
        except Exception:
            return None

    records = collect_records(archive, ticks)
    dead = [r for r in records if not r.alive_at_end]
    lifespans = sorted(r.lifespan for r in records)
    n = len(lifespans)

    classifier = DeathClassifier(archive)
    mechanisms: dict[str, int] = {}
    for r in dead:
        m = classifier.classify(r, depth=10)
        mechanisms[m] = mechanisms.get(m, 0) + 1

    last_death = max((r.death_tick for r in dead), default=None)
    summary = {
        "name": name,
        "ruleset_version": meta("ruleset_version") or "?",
        "survivors": sum(1 for r in records if r.alive_at_end),
        "agents": len(records),
        "mean": sum(lifespans) / n if n else 0.0,
        "median": lifespans[n // 2] if n else None,
        "p90": lifespans[int(n * 0.9)] if n else None,
        "last_death": last_death,
        "mechanisms": mechanisms,
        "elapsed": time.time() - t0,
    }
    archive.close()
    return summary


def fmt_mechanisms(mechs: dict[str, int], total: int) -> str:
    if total == 0:
        return "—"
    parts = []
    for m in sorted(mechs, key=lambda k: -mechs[k]):
        parts.append(f"{m} {100.0 * mechs[m] / total:.1f}%")
    return "; ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--ticks", type=int, default=10000)
    parser.add_argument("runs", nargs="+", help="label=db_path pairs")
    args = parser.parse_args(argv)

    summaries = []
    for spec in args.runs:
        label, db = spec.split("=", 1)
        print(f"analyzing {label} ({db})…", flush=True)
        summaries.append(summarize(label, db, args.ticks))

    lines: list[str] = []
    add = lines.append
    add("# v0.3.1 — structural diagnosis of the collapse")
    add("")
    add("Frozen **CAUSAL KERNEL v0.1**. Same seed (7), same scale")
    add("(10 regions × 1000 agents × 10 000 ticks), one severed link per")
    add("ruleset. The question: which link of the v0.3.0 spiral is the")
    add("bottleneck of the collapse?")
    add("")
    add("## Comparison")
    add("")
    header = "| measure |"
    sep = "|---|"
    for s in summaries:
        header += f" {s['name']} ({s['ruleset_version']}) |"
        sep += "---|"
    add(header)
    add(sep)
    add("| survivors |" + "".join(
        f" **{s['survivors']}** / {s['agents']} |" for s in summaries))
    add("| extinction / last death |" + "".join(
        f" tick {s['last_death'] if s['last_death'] is not None else '— (survived)'} |"
        for s in summaries))
    add("| mean lifespan |" + "".join(
        f" {s['mean']:.0f} |" for s in summaries))
    add("| median lifespan |" + "".join(
        f" {s['median']} |" for s in summaries))
    add("| p90 lifespan |" + "".join(
        f" {s['p90']} |" for s in summaries))
    add("| death mechanisms |" + "".join(
        f" {fmt_mechanisms(s['mechanisms'], s['agents'] - s['survivors'])} |"
        for s in summaries))
    add("")
    add("Analysis time: " +
        ", ".join(f"{s['name']} {s['elapsed']:.0f}s" for s in summaries) + ".")
    add("")
    add("Per-run reports: `experiments/reports/survival_seed7_<ruleset>.md`.")

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
