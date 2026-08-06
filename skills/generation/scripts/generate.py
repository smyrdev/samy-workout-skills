#!/usr/bin/env python3
"""Workout plan generator for samy-workout-skills.

Reads a profile.json, a program file whose volume block volume.py has already
filled, an exercise dataset described by a descriptor in datasets.json, and an
optional personal rules.json — and fits concrete exercises to the per-muscle
weekly set allocation. Every tunable number lives in generate.config.json;
every dataset-specific name lives in datasets.json. This script holds the
algorithm only and refuses unknown values rather than guessing.

Usage:
    generate.py --profile PROFILE.json --program PROGRAM.json \\
        --dataset-dir DIR [--rules RULES.json] [--dataset NAME] \\
        [--today YYYY-MM-DD] [--write PLAN.json] [--write-md PLAN.md]

    generate.py --self-test

Without --write the plan JSON is printed to stdout. --write refuses to
overwrite an existing file — pick the next -2/-3 suffix instead.

Exit codes: 0 success, 2 usage error, 3 input error (a file or a value inside
it is missing or unrecognized). Volume targets are never computed here — they
are read from the program file's volume block, which volume.py owns.
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

MODEL_VERSION = "1.0"


def fail_usage(message):
    print(f"usage error: {message}", file=sys.stderr)
    sys.exit(2)


def fail_input(message):
    print(f"input error: {message}", file=sys.stderr)
    sys.exit(3)


def load_json(path, what):
    p = Path(path)
    if not p.is_file():
        fail_input(f"{what} not found: {path}")
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        fail_input(f"{what} is not valid JSON: {path} ({e})")


def script_dir():
    return Path(__file__).resolve().parent


def default_config_path():
    return script_dir() / "generate.config.json"


def default_descriptor_path():
    return script_dir().parent / "datasets.json"


def load_config(path):
    cfg = load_json(path, "config")
    required = [
        "default_rules", "split_sessions", "max_per_movement_group_per_session",
        "max_per_volume_profile_per_session", "repeat_penalty", "focus_bonus",
        "name_length_penalty", "indirect_discount", "sets_max",
        "short_tolerance_sets", "compound_min_muscles", "trailer_groups",
        "reps_by_goal", "deload_sets_multiplier",
    ]
    missing = [k for k in required if k not in cfg]
    if missing:
        fail_input(f"config missing keys: {', '.join(missing)}")
    return cfg


def pick_dataset(descriptor, name):
    datasets = descriptor.get("datasets")
    if not isinstance(datasets, dict) or not datasets:
        fail_input("descriptor has no datasets")
    key = name or descriptor.get("default")
    if key not in datasets:
        fail_input(f"unknown dataset {key!r}; descriptor has: {', '.join(sorted(datasets))}")
    ds = datasets[key]
    required = ["repo", "ref", "data_file", "fields", "category_filter",
                "equipment_tiers", "muscle_map", "muscle_ignore", "benchmark_gates"]
    missing = [k for k in required if k not in ds]
    if missing:
        fail_input(f"descriptor for {key!r} missing keys: {', '.join(missing)}")
    return key, ds


def equipment_to_tier(ds):
    table = {}
    for tier_str, names in ds["equipment_tiers"].items():
        try:
            tier = int(tier_str)
        except ValueError:
            fail_input(f"equipment_tiers key {tier_str!r} is not an integer")
        for eq in names:
            if eq in table:
                fail_input(f"equipment {eq!r} appears in more than one tier")
            table[eq] = tier
    return table


KNOWN_MUSCLES_NOTE = (
    "add it to muscle_map or muscle_ignore in datasets.json — unmapped muscles are refused, never guessed"
)


def build_rows(records, ds):
    """Compact dataset records into fit-ready rows. Refuses unknown equipment
    and unmapped muscles rather than guessing."""
    fields = ds["fields"]
    muscle_map = ds["muscle_map"]
    ignore = set(ds["muscle_ignore"])
    categories = set(ds["category_filter"])
    tier_of = equipment_to_tier(ds)

    unknown_equipment, unmapped_muscles = set(), set()
    rows = []
    for rec in records:
        if rec.get(fields["category"]) not in categories:
            continue
        volume = rec.get(fields["volume"])
        if not isinstance(volume, dict) or not volume:
            continue
        primary = rec.get(fields["primary_muscle"])
        if primary is None or primary in ignore:
            continue
        if primary not in muscle_map:
            unmapped_muscles.add(primary)
            continue
        equipment = rec.get(fields["equipment"])
        if equipment not in tier_of:
            unknown_equipment.add(str(equipment))
            continue
        muscles = {}
        for muscle, coeff in volume.items():
            if muscle in ignore:
                continue
            if muscle not in muscle_map:
                unmapped_muscles.add(muscle)
                continue
            group = muscle_map[muscle]
            muscles[group] = max(muscles.get(group, 0.0), float(coeff))
        if not muscles:
            continue
        vp_field = fields.get("volume_profile")
        rows.append({
            "id": rec.get(fields["id"]),
            "name": rec.get(fields["name"]),
            "equipment": equipment,
            "tier": tier_of[equipment],
            "movement_group": rec.get(fields["movement_group"]),
            "volume_profile": rec.get(vp_field) if vp_field else None,
            "primary": muscle_map[primary],
            "muscles": dict(sorted(muscles.items())),
        })

    if unmapped_muscles:
        fail_input(f"dataset muscles not in muscle_map/muscle_ignore: "
                   f"{sorted(unmapped_muscles)} — {KNOWN_MUSCLES_NOTE}")
    if unknown_equipment:
        fail_input(f"dataset equipment not in any tier: {sorted(unknown_equipment)} "
                   f"— add each to equipment_tiers in datasets.json")
    rows.sort(key=lambda r: (r["name"], r["id"]))
    return rows


def merge_rules(default_rules, personal):
    merged = {
        "exclude": dict(default_rules["exclude"]),
        "focus": dict(default_rules["focus"]),
        "order": list(default_rules["order"]),
    }
    if personal is None:
        return merged
    for section in ("exclude", "focus"):
        for key, value in personal.get(section, {}).items():
            if key not in merged[section]:
                fail_input(f"rules.{section} has unknown key {key!r}")
            merged[section][key] = value
    if "order" in personal:
        merged["order"] = list(personal["order"])
    return merged


ORDER_RULES = (
    "must_include_first", "trailer_groups_last", "compound_before_isolation",
    "focus_muscles_first", "large_groups_before_small",
)


def benchmark_exclusions(rows, ds, benchmarks):
    """Row ids excluded because a gating benchmark is false."""
    excluded = set()
    for bench_key, gate in ds["benchmark_gates"].items():
        if bench_key not in benchmarks:
            fail_input(f"profile strength_benchmarks missing key {bench_key!r} "
                       f"named by descriptor benchmark_gates")
        if benchmarks[bench_key] is True:
            continue
        patterns = [re.compile(p) for p in gate["false_excludes_names_matching"]]
        spared = set(gate.get("unless_equipment", []))
        for row in rows:
            if row["equipment"] in spared:
                continue
            if any(p.search(row["name"]) for p in patterns):
                excluded.add(row["id"])
    return excluded


def apply_filters(rows, rules, tier, gate_excluded, warnings):
    all_names = {r["name"] for r in rows}
    all_equipment = {r["equipment"] for r in rows}
    all_movement_groups = {r["movement_group"] for r in rows if r["movement_group"]}

    excl = rules["exclude"]
    for name in excl["exercises"]:
        if name.lower() not in all_names:
            warnings.append(f"unknown_exclude_exercise:{name}")
    for eq in excl["equipment"]:
        if eq not in all_equipment:
            warnings.append(f"unknown_exclude_equipment:{eq}")
    for mg in excl["movement_groups"]:
        if mg not in all_movement_groups:
            warnings.append(f"unknown_exclude_movement_group:{mg}")

    excluded_names = {n.lower() for n in excl["exercises"]}
    excluded_equipment = set(excl["equipment"])
    excluded_mgs = set(excl["movement_groups"])

    kept = []
    for row in rows:
        if row["tier"] > tier:
            continue
        if row["id"] in gate_excluded:
            continue
        if row["name"] in excluded_names:
            continue
        if row["equipment"] in excluded_equipment:
            continue
        if row["movement_group"] in excluded_mgs:
            continue
        kept.append(row)
    return kept


def session_plan(program, config):
    split = program["split"]
    if split not in config["split_sessions"]:
        fail_input(f"unknown split: {split!r} — add it to split_sessions in generate.config.json")
    template = config["split_sessions"][split]
    pattern = template["pattern"]
    days = program["days_per_week"]
    return [
        {"day": day + 1,
         "focus": pattern[day % len(pattern)],
         "groups": list(template["groups"][pattern[day % len(pattern)]])}
        for day in range(days)
    ]


def place_must_include(sessions, rows_by_name, rules, chosen, uses, warnings):
    pinned = {}
    for name in rules["focus"]["must_include"]:
        row = rows_by_name.get(name.lower())
        if row is None:
            warnings.append(f"unmatched_must_include:{name}")
            continue
        candidates = [s for s in sessions if row["primary"] in s["groups"]]
        if not candidates:
            warnings.append(f"unmatched_must_include:{name}")
            continue
        target = min(candidates, key=lambda s: (len(chosen[s["day"]]), s["day"]))
        chosen[target["day"]].append(row)
        uses[row["id"]] = uses.get(row["id"], 0) + 1
        pinned.setdefault(target["day"], set()).add(row["id"])
    return pinned


def marginal_score(row, remaining, groups, sets, rules, uses, config):
    score = 0.0
    for group, coeff in row["effective"].items():
        if group in groups and remaining.get(group, 0.0) > 0:
            score += min(remaining[group], sets * coeff) / sets
    if row["primary"] in rules["focus"]["muscles"] and remaining.get(row["primary"], 0.0) > 0:
        score += config["focus_bonus"]
    score -= config["repeat_penalty"] * uses.get(row["id"], 0)
    # Short names are the canonical movements ("barbell bench press" over
    # "barbell bench press wide reverse grip") — a mild steer, not a rule.
    score -= config["name_length_penalty"] * len(row["name"])
    return score


def fill_sessions(sessions, rows, targets, volume_block, rules, config, warnings):
    remaining = {g: float(v) for g, v in targets.items()}
    uses = {}
    chosen = {s["day"]: [] for s in sessions}
    rows_by_name = {r["name"]: r for r in rows}

    pinned = place_must_include(sessions, rows_by_name, rules, chosen, uses, warnings)

    cap = volume_block["exercises_per_session"]
    sets_default = volume_block["sets_per_exercise"]
    mg_cap = config["max_per_movement_group_per_session"]
    vp_cap = config["max_per_volume_profile_per_session"]

    sets_of = {}  # (day, id) -> sets
    for session in sessions:
        for row in chosen[session["day"]]:
            sets_of[(session["day"], row["id"])] = sets_default
            for group, coeff in row["effective"].items():
                if group in remaining:
                    remaining[group] -= sets_default * coeff

    # Fill round-robin — slot 1 on every day, then slot 2, and so on — so the
    # week comes out balanced instead of front-loaded with empty final days.
    for _slot in range(cap):
        for session in sessions:
            day = session["day"]
            if len(chosen[day]) >= cap:
                continue
            groups = [g for g in session["groups"] if g in remaining]
            mg_count, vp_count = {}, {}
            picked_ids = set()
            for row in chosen[day]:
                picked_ids.add(row["id"])
                if row["movement_group"]:
                    mg_count[row["movement_group"]] = mg_count.get(row["movement_group"], 0) + 1
                if row["volume_profile"]:
                    vp_count[row["volume_profile"]] = vp_count.get(row["volume_profile"], 0) + 1

            def eligible(row):
                if row["id"] in picked_ids:
                    return False
                if row["primary"] not in groups:
                    return False
                mg = row["movement_group"]
                if mg and mg_count.get(mg, 0) >= mg_cap:
                    return False
                vp = row["volume_profile"]
                if vp and vp_count.get(vp, 0) >= vp_cap:
                    return False
                return True

            candidates = [r for r in rows if eligible(r) and remaining.get(r["primary"], 0.0) > 0]
            if not candidates:  # secondary-need fallback: any exercise still moving a needle
                candidates = [
                    r for r in rows
                    if eligible(r)
                    and marginal_score(r, remaining, groups, sets_default, rules, uses, config) > 0
                ]
            if not candidates:
                continue
            best = min(
                candidates,
                key=lambda r: (
                    -marginal_score(r, remaining, groups, sets_default, rules, uses, config),
                    uses.get(r["id"], 0), r["name"], r["id"],
                ),
            )
            chosen[day].append(best)
            uses[best["id"]] = uses.get(best["id"], 0) + 1
            sets_of[(day, best["id"])] = sets_default
            for group, coeff in best["effective"].items():
                if group in remaining:
                    remaining[group] -= sets_default * coeff

    repair_shortfalls(sessions, chosen, sets_of, remaining, config)

    tolerance = config["short_tolerance_sets"]
    for group in targets:
        if remaining[group] > tolerance:
            warnings.append(f"short:{group}")

    return chosen, sets_of, pinned, remaining


def repair_shortfalls(sessions, chosen, sets_of, remaining, config):
    """Add sets to already-picked exercises, primary movers first, until every
    short group is within tolerance or nothing can take another set."""
    tolerance = config["short_tolerance_sets"]
    sets_max = config["sets_max"]
    progress = True
    while progress:
        progress = False
        for group in list(remaining):
            if remaining[group] <= tolerance:
                continue
            carriers = []
            for session in sessions:
                for row in chosen[session["day"]]:
                    coeff = row["muscles"].get(group, 0.0)
                    if coeff >= 1.0 and sets_of[(session["day"], row["id"])] < sets_max:
                        carriers.append((0 if row["primary"] == group else 1,
                                         session["day"], row["name"], session["day"], row))
            if not carriers:
                continue
            carriers.sort(key=lambda c: c[:3])
            _, _, _, day, row = carriers[0]
            sets_of[(day, row["id"])] += 1
            for g, coeff in row["effective"].items():
                if g in remaining:
                    remaining[g] -= coeff
            progress = True


def order_session(rows, sets_of, day, pinned, rules, targets, config):
    for rule in rules["order"]:
        if rule not in ORDER_RULES:
            fail_input(f"unknown order rule {rule!r}; valid rules: {', '.join(ORDER_RULES)}")

    def key(row):
        parts = []
        for rule in rules["order"]:
            if rule == "must_include_first":
                parts.append(0 if row["id"] in pinned.get(day, set()) else 1)
            elif rule == "trailer_groups_last":
                parts.append(1 if row["primary"] in config["trailer_groups"] else 0)
            elif rule == "compound_before_isolation":
                parts.append(-len(row["muscles"]))
            elif rule == "focus_muscles_first":
                parts.append(0 if row["primary"] in rules["focus"]["muscles"] else 1)
            elif rule == "large_groups_before_small":
                parts.append(-targets.get(row["primary"], 0))
        parts.extend([row["name"], row["id"]])
        return tuple(parts)

    return sorted(rows, key=key)


def reps_for(row, goal, config):
    kind = "compound" if len(row["muscles"]) >= config["compound_min_muscles"] else "isolation"
    if goal not in config["reps_by_goal"]:
        fail_input(f"unknown goal: {goal!r} — add it to reps_by_goal in generate.config.json")
    return config["reps_by_goal"][goal][kind]


def dataset_commit(dataset_dir):
    try:
        result = subprocess.run(
            ["git", "-C", str(dataset_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def generate_plan(profile, program_data, records, ds_name, ds, rules, config,
                  today, commit=None):
    program = program_data.get("program")
    if not isinstance(program, dict):
        fail_input("program file has no \"program\" object")
    volume_block = program_data.get("volume")
    if not isinstance(volume_block, dict):
        fail_input(
            "program file has no volume block — run volume.py first:\n"
            "  python skills/onboarding/scripts/volume.py --profile <profile.json> "
            "--write <program.json>"
        )
    slug = program_data.get("profile_slug")
    benchmarks = profile.get("strength_benchmarks", {})

    warnings = []
    rows = build_rows(records, ds)
    gate_excluded = benchmark_exclusions(rows, ds, benchmarks)
    tier = volume_block["equipment_tier"]
    rows = apply_filters(rows, rules, tier, gate_excluded, warnings)
    if not rows:
        fail_input("no exercises left after filtering — check tier, gates and rules")

    # Indirect (synergist) volume counts toward targets at a discount, so every
    # group ends up with real direct work instead of being "covered" by 0.5s.
    discount = config["indirect_discount"]
    for row in rows:
        row["effective"] = {
            g: (c if c >= 1.0 else c * discount) for g, c in row["muscles"].items()
        }

    targets = dict(volume_block["per_muscle_weekly_sets"])
    for group in rules["exclude"]["muscles"]:
        if group not in targets:
            fail_input(f"rules.exclude.muscles has unknown muscle group {group!r}; "
                       f"valid groups: {', '.join(targets)}")
        targets.pop(group)

    sessions = session_plan(program, config)
    chosen, sets_of, pinned, remaining = fill_sessions(
        sessions, rows, targets, volume_block, rules, config, warnings)

    planned = {g: 0.0 for g in targets}
    session_objects = []
    for session in sessions:
        day = session["day"]
        ordered = order_session(chosen[day], sets_of, day, pinned, rules, targets, config)
        exercises = []
        for row in ordered:
            sets = sets_of[(day, row["id"])]
            for group, coeff in row["effective"].items():
                if group in planned:
                    planned[group] += sets * coeff
            exercises.append({
                "id": row["id"],
                "name": row["name"],
                "equipment": row["equipment"],
                "movement_group": row["movement_group"],
                "primary": row["primary"],
                "sets": sets,
                "reps": reps_for(row, program["primary_goal"], config),
                "volume": row["muscles"],
            })
        session_objects.append({"day": day, "focus": session["focus"], "exercises": exercises})

    deload_week = None
    if program.get("deload"):
        deload_week = {
            "sets_multiplier": config["deload_sets_multiplier"],
            "note": "Final week: same sessions with sets scaled down to promote recovery.",
        }

    return {
        "$schema_version": MODEL_VERSION,
        "created_at": f"{today.isoformat()}T00:00:00Z",
        "profile_slug": slug,
        "program": program,
        "dataset": {"name": ds_name, "repo": ds["repo"], "ref": ds["ref"], "commit": commit},
        "rules_applied": rules,
        "targets": {
            g: {"allocated": targets[g], "planned": round(planned[g], 1)} for g in targets
        },
        "sessions": session_objects,
        "deload_week": deload_week,
        "warnings": warnings,
    }


def render_markdown(plan):
    program = plan["program"]
    lines = []
    lines.append(f"# {program['emoji']} {program['name']}")
    lines.append("")
    lines.append(f"{program['days_per_week']} days/week · {program['session_minutes']} min "
                 f"· {program['split']} · goal: {program['primary_goal']}"
                 + (" · ends with a deload week" if plan["deload_week"] else ""))
    lines.append("")
    lines.append(f"Generated {plan['created_at'][:10]} for `{plan['profile_slug']}` "
                 f"from dataset `{plan['dataset']['name']}`"
                 + (f" @ `{plan['dataset']['commit'][:9]}`" if plan["dataset"]["commit"] else "")
                 + ".")
    lines.append("")
    lines.append("## Weekly volume")
    lines.append("")
    lines.append("| Muscle group | Allocated sets | Planned sets | |")
    lines.append("|---|---|---|---|")
    for group, t in plan["targets"].items():
        flag = "⚠️ short" if f"short:{group}" in plan["warnings"] else ""
        lines.append(f"| {group} | {t['allocated']} | {t['planned']} | {flag} |")
    lines.append("")
    for session in plan["sessions"]:
        lines.append(f"## Day {session['day']} — {session['focus'].replace('_', ' ')}")
        lines.append("")
        lines.append("| Exercise | Equipment | Sets × Reps |")
        lines.append("|---|---|---|")
        for ex in session["exercises"]:
            lines.append(f"| {ex['name']} | {ex['equipment']} | {ex['sets']} × {ex['reps']} |")
        lines.append("")
    if plan["deload_week"]:
        mult = plan["deload_week"]["sets_multiplier"]
        lines.append(f"**Deload:** {plan['deload_week']['note']} "
                     f"(sets × {mult}, rounded down, minimum 1)")
        lines.append("")
    other_warnings = [w for w in plan["warnings"] if not w.startswith("short:")]
    if other_warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in other_warnings:
            lines.append(f"- `{w}`")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("Edit freely — this file is yours. The JSON next to it is the structured "
                 "record; regenerate rather than hand-syncing the two.")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------------------
# Self-test — offline, against the bundled fixture. Pinned invariants, no network.
# --------------------------------------------------------------------------------------

def fixture_profile(pullups=True):
    return {
        "strength_benchmarks": {
            "pullups_5": pullups, "pullups_10": False, "dips_10": True,
            "pushups_15": True, "bench_press_10": True,
            "incline_press_10": True, "overhead_press_10": False,
        },
    }


def fixture_volume_block(tier=3, cap=6, sets=3):
    return {
        "equipment_tier": tier,
        "exercises_per_session": cap,
        "sets_per_exercise": sets,
        "per_muscle_weekly_sets": {
            "chest": 10, "back": 12, "shoulders": 8, "biceps": 6, "triceps": 6,
            "quads": 10, "hamstrings": 8, "glutes": 8, "calves": 6, "core": 6,
        },
    }


def fixture_program_data(split="full_body", days=4, deload=True, volume=None):
    return {
        "$schema_version": "1.0",
        "created_at": "2026-08-06T00:00:00Z",
        "profile_slug": "fixture",
        "program": {
            "name": "Fixture Block", "emoji": "🧪", "primary_goal": "hypertrophy",
            "days_per_week": days, "session_minutes": "60-90", "split": split,
            "deload": deload,
        },
        "volume": volume or fixture_volume_block(),
    }


def run_self_test(config, descriptor):
    ds_name, ds = pick_dataset(descriptor, None)
    records = load_json(script_dir() / "generate.fixture.json", "fixture")
    today = datetime.date(2026, 8, 6)
    default_rules = config["default_rules"]

    def plan_for(profile, program_data, rules=None):
        return generate_plan(profile, program_data, records, ds_name, ds,
                             merge_rules(default_rules, rules), config, today)

    failures = []

    def check(cond, label):
        if not cond:
            failures.append(label)

    # 1. Category filter and muscle_ignore: cardio, stretch and neck-only rows never appear.
    plan = plan_for(fixture_profile(), fixture_program_data())
    names = [ex["name"] for s in plan["sessions"] for ex in s["exercises"]]
    check("jump rope" not in names, "cardio row leaked into plan")
    check("standing hamstring stretch" not in names, "stretch row leaked into plan")
    check("lying neck bridge" not in names, "ignored-muscle row leaked into plan")

    # 2. Session caps and coverage.
    for s in plan["sessions"]:
        check(len(s["exercises"]) <= 6, f"day {s['day']} exceeds exercises_per_session")
    check(all(t["planned"] > 0 for t in plan["targets"].values()),
          "a muscle group got zero planned volume")

    # 3. Equipment tier: at tier 1 no machine equipment appears.
    plan1 = plan_for(fixture_profile(), fixture_program_data(
        volume=fixture_volume_block(tier=1)))
    eqs = {ex["equipment"] for s in plan1["sessions"] for ex in s["exercises"]}
    check(not eqs & {"cable", "leverage machine", "sled machine", "smith machine", "assisted"},
          f"tier-1 plan uses machine equipment: {sorted(eqs)}")

    # 4. Benchmark gate: pullups_5 false removes unassisted pull-ups, keeps assisted/band.
    gated = plan_for(fixture_profile(pullups=False), fixture_program_data())
    gated_names = [ex["name"] for s in gated["sessions"] for ex in s["exercises"]]
    check("pull-up" not in gated_names, "gated pull-up still selected")
    check(any(n in gated_names for n in ("assisted pull-up", "band pull-up")),
          "gate removed the assisted alternatives too")

    # 5. Determinism: same inputs, byte-identical plan.
    again = plan_for(fixture_profile(), fixture_program_data())
    check(json.dumps(plan, sort_keys=True) == json.dumps(again, sort_keys=True),
          "two identical runs produced different plans")

    # 6. Personal rules: exclusion, focus, must_include, unknown-name warning.
    ruled = plan_for(fixture_profile(), fixture_program_data(), rules={
        "exclude": {"exercises": ["barbell squat", "flying pig"]},
        "focus": {"muscles": ["shoulders"], "must_include": ["dumbbell fly"]},
    })
    ruled_names = [ex["name"] for s in ruled["sessions"] for ex in s["exercises"]]
    check("barbell squat" not in ruled_names, "excluded exercise still selected")
    check("dumbbell fly" in ruled_names, "must_include exercise missing")
    check("unknown_exclude_exercise:flying pig" in ruled["warnings"],
          "unknown exclusion name not warned about")

    # 7. Session ordering: trailer groups (core, calves) come after everything else.
    for s in plan["sessions"]:
        primaries = [ex["primary"] for ex in s["exercises"]]
        trailer_started = False
        for p in primaries:
            if p in config["trailer_groups"]:
                trailer_started = True
            elif trailer_started:
                failures.append(f"day {s['day']}: non-trailer after trailer group")
                break

    # 8. Shortfall honesty: an unreachable target is reported, never silent.
    starved = fixture_volume_block(cap=3)
    starved["per_muscle_weekly_sets"] = dict(
        starved["per_muscle_weekly_sets"], hamstrings=40)
    short = plan_for(fixture_profile(), fixture_program_data(
        days=3, volume=starved))
    check("short:hamstrings" in short["warnings"], "unreachable target not reported short")

    # 9. Upper/lower split: no lower-body primary on an upper day and vice versa.
    ul = plan_for(fixture_profile(), fixture_program_data(split="upper_lower", days=4))
    for s in ul["sessions"]:
        allowed = set(config["split_sessions"]["upper_lower"]["groups"][s["focus"]])
        for ex in s["exercises"]:
            check(ex["primary"] in allowed,
                  f"day {s['day']} ({s['focus']}): {ex['name']} targets {ex['primary']}")

    # 10. Deload flag round-trips.
    check(plan["deload_week"] is not None, "deload requested but deload_week missing")
    no_deload = plan_for(fixture_profile(), fixture_program_data(deload=False))
    check(no_deload["deload_week"] is None, "deload_week present without deload")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return False
    print(f"OK: {ds_name} fixture — 10 invariant groups hold")
    return True


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        description="Fit exercises from a dataset to a program file's per-muscle weekly sets.",
    )
    p.add_argument("--profile", help="path to profile.json")
    p.add_argument("--program", help="path to programs/program-*.json with a volume block")
    p.add_argument("--rules", help="path to a personal rules.json (optional)")
    p.add_argument("--dataset-dir", help="path to the cloned dataset repository")
    p.add_argument("--dataset", help="dataset key in the descriptor (default: its \"default\")")
    p.add_argument("--descriptor", help="path to datasets.json (default: alongside the skill)")
    p.add_argument("--config", help="path to generate.config.json (default: alongside this script)")
    p.add_argument("--today", help="YYYY-MM-DD, for a deterministic created_at. Defaults to the real date.")
    p.add_argument("--write", help="write the plan JSON here (refuses to overwrite)")
    p.add_argument("--write-md", help="also write a human-readable markdown render here")
    p.add_argument("--self-test", action="store_true", help="run the built-in self-test and exit")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config or default_config_path())
    descriptor = load_json(args.descriptor or default_descriptor_path(), "descriptor")

    if args.self_test:
        ok = run_self_test(config, descriptor)
        sys.exit(0 if ok else 1)

    for flag, value in (("--profile", args.profile), ("--program", args.program),
                        ("--dataset-dir", args.dataset_dir)):
        if not value:
            fail_usage(f"{flag} is required")

    profile = load_json(args.profile, "profile")
    program_data = load_json(args.program, "program file")
    personal = load_json(args.rules, "rules file") if args.rules else None

    ds_name, ds = pick_dataset(descriptor, args.dataset)
    dataset_dir = Path(args.dataset_dir)
    data_path = dataset_dir / ds["data_file"]
    records = load_json(data_path, "dataset data file")
    if not isinstance(records, list):
        fail_input(f"dataset data file is not an array of records: {data_path}")

    rules = merge_rules(config["default_rules"], personal)

    if args.today:
        try:
            y, m, d = (int(x) for x in args.today.split("-"))
            today = datetime.date(y, m, d)
        except (ValueError, TypeError):
            fail_usage(f"--today is not a valid YYYY-MM-DD date: {args.today}")
    else:
        today = datetime.date.today()

    plan = generate_plan(profile, program_data, records, ds_name, ds, rules,
                         config, today, commit=dataset_commit(dataset_dir))

    if args.write:
        out = Path(args.write)
        if out.exists():
            fail_usage(f"{args.write} already exists — plans are never overwritten; "
                       f"pick the next -2/-3 suffix")
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"wrote {args.write}")
    else:
        print(json.dumps(plan, indent=2, ensure_ascii=False))

    if args.write_md:
        out_md = Path(args.write_md)
        if out_md.exists():
            fail_usage(f"{args.write_md} already exists — pick the next -2/-3 suffix")
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(plan), encoding="utf-8")
        print(f"wrote {args.write_md}")

    sys.exit(0)


if __name__ == "__main__":
    main()
