#!/usr/bin/env python3
"""Workout plan generator for samy-workout-skills.

Reads a profile.json, a program file whose volume block volume.py has already
filled, an exercise dataset described by a descriptor in assets/datasets.json, and an
optional hand-written personal rules.md — and decides two things: which
exercises this person may legally be given, and how many weekly sets each
muscle is owed. It does not choose. `--brief` prints that budget and the legal
candidate pool per muscle and stops; `--selection` takes the coach's choices
back, checks them, and composes the plan. Every tunable number lives in
generate.config.json; every dataset-specific name lives in assets/datasets.json.
Unknown values are refused rather than guessed.

Usage:
    generate.py --brief --profile PROFILE.json --program PROGRAM.json \\
        --dataset-dir DIR [--rules RULES.md] [--dataset NAME]

    generate.py --selection SELECTION.json --profile PROFILE.json \\
        --program PROGRAM.json --dataset-dir DIR [--rules RULES.md] \\
        [--dataset NAME] [--today YYYY-MM-DD] [--write PLAN.json] \\
        [--write-md PLAN.md]

    generate.py --self-test

Without --write the plan JSON is printed to stdout. --write refuses to
overwrite an existing file — pick the next -2/-3 suffix instead.

Exit codes: 0 success, 2 usage error, 3 input error (a file or a value inside
it is missing or unrecognized). Volume targets are never computed here — they
are read from the program file's volume block, which volume.py owns.
"""

import argparse
import datetime
import io
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
    return script_dir().parent / "assets" / "datasets.json"


def load_config(path):
    cfg = load_json(path, "config")
    required = [
        "default_rules", "split_sessions", "focus_bonus", "name_length_penalty",
        "indirect_discount", "short_tolerance_sets", "compound_min_muscles",
        "trailer_groups", "reps_by_goal", "deload_sets_multiplier",
        "candidates_per_muscle", "set_seconds", "rest_seconds_by_goal",
        "session_minutes_floor", "rep_floors", "rep_floor_goals",
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
    "add it to muscle_map or muscle_ignore in assets/datasets.json — unmapped muscles are refused, never guessed"
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
                   f"— add each to equipment_tiers in assets/datasets.json")
    rows.sort(key=lambda r: (r["name"], r["id"]))
    return rows


# Keys are the headings as the docs spell them; lookup is case-insensitive.
RULES_SECTIONS = {
    "Exclude exercises": ("exclude", "exercises"),
    "Exclude equipment": ("exclude", "equipment"),
    "Exclude movement groups": ("exclude", "movement_groups"),
    "Exclude muscles": ("exclude", "muscles"),
    "Focus muscles": ("focus", "muscles"),
    "Must include": ("focus", "must_include"),
    "Order": ("order", None),
}
_RULES_SECTIONS_LOWER = {h.lower(): target for h, target in RULES_SECTIONS.items()}

RULES_HEADING_NOTE = (
    "valid headings: " + ", ".join(f"## {h}" for h in RULES_SECTIONS)
)


def parse_rules_md(text, path):
    """Parse a hand-written rules.md into the same dict shape rules.json had.

    The format is deliberately dumb so it is easy to type and easy to diff:
    `## <Section>` headings, one `- item` bullet per value. Only bullets carry
    meaning — any other prose is a note to self and is ignored, so the file can
    explain itself to the person editing it. A heading with no bullets under it
    means "no items", which is how a default is switched off. An unknown
    heading is refused, never ignored: a silently dropped rule is worse than a
    failed run. Raises ValueError with a `path:line: reason` message.
    """
    rules = {}
    current = None      # the list the next bullet appends to
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            heading = line.lstrip("#").strip()
            if level == 1:
                current = None          # the document title
                continue
            target = _RULES_SECTIONS_LOWER.get(heading.lower().rstrip(":"))
            if target is None:
                raise ValueError(f"{path}:{lineno}: unknown section {heading!r} — "
                                 f"{RULES_HEADING_NOTE}")
            section, field = target
            if field is None:
                current = rules.setdefault(section, [])
            else:
                current = rules.setdefault(section, {}).setdefault(field, [])
            continue
        if line.startswith(("-", "*")):
            value = line[1:].strip()
            if not value:
                continue
            if current is None:
                raise ValueError(f"{path}:{lineno}: bullet {value!r} before any section "
                                 f"heading — {RULES_HEADING_NOTE}")
            current.append(value)
            continue
        # Anything else is prose — a note to self, an explanation under a heading.
        # Only bullets carry meaning, so prose is ignored wherever it appears.
    return rules


def load_rules(path):
    """Read a personal rules file. `.md` is the documented format; `.json` is
    still accepted so an older file keeps working."""
    p = Path(path)
    if p.suffix.lower() == ".json":
        personal = load_json(path, "rules file")
        personal.pop("$schema_version", None)
        return personal
    if not p.is_file():
        fail_input(f"rules file not found: {path}")
    try:
        return parse_rules_md(p.read_text(encoding="utf-8"), path)
    except ValueError as e:
        fail_input(str(e))


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


def must_include_ids(sessions, rows_by_name, rules, warnings):
    """Ids the person pinned. Placing them is the coach's job now — this only
    resolves the names and reports the ones that match nothing."""
    pinned = set()
    for name in rules["focus"]["must_include"]:
        row = rows_by_name.get(name.lower())
        if row is None or not any(row["primary"] in s["groups"] for s in sessions):
            warnings.append(f"unmatched_must_include:{name}")
            continue
        pinned.add(row["id"])
    return pinned


def marginal_score(row, remaining, groups, rules, config):
    """How much of the week's outstanding volume one set of this row would
    deliver — the reading order of a candidate pool, not a verdict."""
    score = 0.0
    for group, coeff in row["effective"].items():
        if group in groups and remaining.get(group, 0.0) > 0:
            score += min(remaining[group], coeff)
    if row["primary"] in rules["focus"]["muscles"] and remaining.get(row["primary"], 0.0) > 0:
        score += config["focus_bonus"]
    # Short names are the canonical movements ("barbell bench press" over
    # "barbell bench press wide reverse grip") — a mild steer, not a rule.
    score -= config["name_length_penalty"] * len(row["name"])
    return score


def distribute_sets(sessions, targets):
    """Spread each muscle's weekly sets as evenly as it goes across the sessions
    that train it — coaching.md § 4. The remainder lands on the earliest days,
    so 17 sets over 3 sessions comes out 6/6/5 rather than 9/4/4."""
    per_day = {s["day"]: {} for s in sessions}
    for group, total in targets.items():
        days = [s["day"] for s in sessions if group in s["groups"]]
        if not days:
            continue
        base, extra = divmod(int(total), len(days))
        for i, day in enumerate(days):
            per_day[day][group] = base + (1 if i < extra else 0)
    return per_day


def validate_order_rules(rules):
    for rule in rules["order"]:
        if rule not in ORDER_RULES:
            fail_input(f"unknown order rule {rule!r}; valid rules: {', '.join(ORDER_RULES)}")


def exercise_kind(row, config):
    return "compound" if len(row["muscles"]) >= config["compound_min_muscles"] else "isolation"


def reps_for(row, goal, config):
    if goal not in config["reps_by_goal"]:
        fail_input(f"unknown goal: {goal!r} — add it to reps_by_goal in generate.config.json")
    return config["reps_by_goal"][goal][exercise_kind(row, config)]


def rest_for(goal, config):
    if goal not in config["rest_seconds_by_goal"]:
        fail_input(f"unknown goal: {goal!r} — add it to rest_seconds_by_goal in "
                   f"generate.config.json")
    return config["rest_seconds_by_goal"][goal]


def session_capacity(program, volume_block, config):
    """How many exercises fit a session. The volume model already derived a
    ceiling from the session-length answer; rest intervals give a second one,
    and the tighter of the two wins. Both are ceilings, never quotas."""
    minutes = program["session_minutes"]
    if minutes not in config["session_minutes_floor"]:
        fail_input(f"unknown session length: {minutes!r} — add it to session_minutes_floor "
                   f"in generate.config.json")
    rest = rest_for(program["primary_goal"], config)
    sets = volume_block["sets_per_exercise"]
    # Costed at the compound rest interval: a ceiling that holds for the
    # heaviest session the coach might build, not only the lightest.
    per_exercise = sets * (config["set_seconds"] + rest["compound"])
    fits = (config["session_minutes_floor"][minutes] * 60) // per_exercise
    return max(1, min(volume_block["exercises_per_session"], int(fits))), rest


def rank_candidates(rows, targets, rules, config, pinned):
    """One ranked pool per muscle group. The score is the old fit's marginal
    usefulness, frozen against the full week's targets — a starting order, not a
    verdict. Everything that would make it a verdict lives in coaching.md."""
    limit = config["candidates_per_muscle"]
    pools = {}
    groups = list(targets)
    for group in groups:
        rows_here = [r for r in rows if r["primary"] == group]
        rows_here.sort(key=lambda r: (
            -marginal_score(r, targets, groups, rules, config), r["name"], r["id"]))
        pools[group] = [{
            "id": r["id"],
            "name": r["name"],
            "equipment": r["equipment"],
            "movement_group": r["movement_group"],
            "volume_profile": r["volume_profile"],
            "primary": r["primary"],
            "kind": exercise_kind(r, config),
            "must_include": r["id"] in pinned,
            "volume": r["muscles"],
        } for r in rows_here[:limit]]
    return pools


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


# A program file is machine-written but hand-editable, so "present but
# incomplete" is an expected input. The program block is echoed into the plan,
# whose schema requires every one of these keys — so all of them are checked up
# front, not just the ones the fitting code reads. Anything missing is refused
# by name rather than met with a KeyError or a schema-invalid plan on disk.
PROGRAM_REQUIRED = ("name", "emoji", "primary_goal", "days_per_week",
                    "session_minutes", "split", "deload")
VOLUME_REQUIRED = ("equipment_tier", "exercises_per_session",
                   "sets_per_exercise", "per_muscle_weekly_sets")
VOLUME_HINT = ("  python skills/onboarding/scripts/volume.py "
               "--profile <profile.json> --write <program.json>")


def prepare(profile, program_data, records, ds_name, ds, rules, config):
    """Everything both commands need: the inputs validated, the dataset filtered
    down to what this person may legally be given, and the week's skeleton."""
    program = program_data.get("program")
    if not isinstance(program, dict):
        fail_input("program file has no \"program\" object")
    missing = [k for k in PROGRAM_REQUIRED if k not in program]
    if missing:
        fail_input(f"program block missing keys: {', '.join(missing)} — the onboarding "
                   f"skill writes this file; it is not hand-built")

    volume_block = program_data.get("volume")
    if not isinstance(volume_block, dict):
        fail_input(
            "program file has no volume block — run volume.py first:\n" + VOLUME_HINT
        )
    missing = [k for k in VOLUME_REQUIRED if k not in volume_block]
    if missing:
        fail_input(f"volume block missing keys: {', '.join(missing)} — rerun volume.py "
                   f"to rebuild it:\n" + VOLUME_HINT)
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

    validate_order_rules(rules)
    # Checked here rather than where it is first used, so an unfamiliar goal is
    # reported against the table a reader would go and edit.
    goal = program["primary_goal"]
    if goal not in config["reps_by_goal"]:
        fail_input(f"unknown goal: {goal!r} — add it to reps_by_goal in generate.config.json")
    sessions = session_plan(program, config)
    rows_by_name = {r["name"]: r for r in rows}
    pinned = must_include_ids(sessions, rows_by_name, rules, warnings)

    return {
        "profile": profile, "program": program, "volume": volume_block,
        "rows": rows, "rows_by_id": {r["id"]: r for r in rows},
        "targets": targets, "sessions": sessions, "pinned": pinned,
        "rules": rules, "ds_name": ds_name, "ds": ds, "warnings": warnings,
    }


def build_brief(ctx, config):
    """What the coach is given: the budget, and the legal candidates. No
    exercise is chosen here, and no session is ordered."""
    program, volume_block = ctx["program"], ctx["volume"]
    max_exercises, rest = session_capacity(program, volume_block, config)
    per_day = distribute_sets(ctx["sessions"], ctx["targets"])
    goal = program["primary_goal"]

    return {
        "$brief_version": MODEL_VERSION,
        "program": program,
        "dataset": {"name": ctx["ds_name"], "repo": ctx["ds"]["repo"], "ref": ctx["ds"]["ref"]},
        "sets_per_exercise": volume_block["sets_per_exercise"],
        "max_exercises_per_session": max_exercises,
        "rest_seconds": rest,
        "reps_band": config["reps_by_goal"][goal],
        "trailer_groups": config["trailer_groups"],
        "rep_floors": config["rep_floors"] if goal in config["rep_floor_goals"] else None,
        "targets": ctx["targets"],
        "sessions": [{
            "day": s["day"],
            "focus": s["focus"],
            "groups": s["groups"],
            "sets_per_muscle": per_day[s["day"]],
        } for s in ctx["sessions"]],
        "candidates": rank_candidates(ctx["rows"], ctx["targets"], ctx["rules"], config,
                                      ctx["pinned"]),
        "rules_applied": ctx["rules"],
        "warnings": list(ctx["warnings"]),
    }


def reps_low(reps):
    digits = ""
    for ch in str(reps):
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    return int(digits) if digits else None


SELECTION_KEYS = {"id", "sets", "reps", "rir", "rest_seconds", "superset_group"}


def check_selection(ctx, selection, brief, config):
    """The two training refusals — an exercise never offered, a rep target under
    the floor — plus the integrity checks that make a selection readable at all
    (every day present, whole sets, known keys). Everything else the coach
    decided is theirs to defend."""
    if not isinstance(selection, dict) or not isinstance(selection.get("sessions"), list):
        fail_input("selection file has no \"sessions\" array")

    legal = {}
    for session in brief["sessions"]:
        ids = set()
        for group in session["groups"]:
            ids.update(c["id"] for c in brief["candidates"].get(group, []))
        legal[session["day"]] = ids

    want_days = sorted(legal)
    got_days = sorted(s.get("day") for s in selection["sessions"])
    if got_days != want_days:
        fail_input(f"selection covers days {got_days} but the brief asked for {want_days}")

    floors = brief["rep_floors"]
    for session in selection["sessions"]:
        day = session["day"]
        for ex in session.get("exercises", []):
            ex_id = ex.get("id")
            if ex_id not in legal[day]:
                fail_input(f"day {day}: {ex_id!r} was not among the candidates offered for that "
                           f"session — pick from the brief, or re-run it with changed rules")
            if not isinstance(ex.get("sets"), int) or ex["sets"] < 1:
                fail_input(f"day {day}: {ex_id!r} needs a whole number of sets, at least 1")
            unknown = sorted(set(ex) - SELECTION_KEYS)
            if unknown:
                fail_input(f"day {day}: {ex_id!r} has unknown keys {unknown} — "
                           f"see assets/schema/selection.schema.json")
            row = ctx["rows_by_id"][ex_id]
            if not ex.get("reps"):
                ex["reps"] = reps_for(row, ctx["program"]["primary_goal"], config)
            if floors:
                kind = exercise_kind(row, config)
                low = reps_low(ex["reps"])
                if low is None:
                    fail_input(f"day {day}: {ex_id!r} has no readable rep target {ex['reps']!r}")
                if low < floors[kind]:
                    fail_input(f"day {day}: {ex_id!r} is a {kind} exercise at {low} reps — "
                               f"coaching.md 1.4 floors it at {floors[kind]} for this goal")


def compose_plan(ctx, selection, brief, config, today, commit=None):
    check_selection(ctx, selection, brief, config)
    program, targets = ctx["program"], ctx["targets"]
    warnings = list(ctx["warnings"])

    planned = {g: 0.0 for g in targets}
    session_objects = []
    by_day = {s["day"]: s for s in selection["sessions"]}
    for session in ctx["sessions"]:
        day = session["day"]
        exercises = []
        for ex in by_day[day].get("exercises", []):
            row = ctx["rows_by_id"][ex["id"]]
            sets = ex["sets"]
            for group, coeff in row["effective"].items():
                if group in planned:
                    planned[group] += sets * coeff
            entry = {
                "id": row["id"],
                "name": row["name"],
                "equipment": row["equipment"],
                "movement_group": row["movement_group"],
                "primary": row["primary"],
                "sets": sets,
                "reps": str(ex["reps"]),
                "volume": row["muscles"],
            }
            for key in ("rir", "rest_seconds", "superset_group"):
                if ex.get(key) is not None:
                    entry[key] = ex[key]
            exercises.append(entry)
        session_objects.append({"day": day, "focus": session["focus"], "exercises": exercises})

    tolerance = config["short_tolerance_sets"]
    for group in targets:
        if targets[group] - planned[group] > tolerance:
            warnings.append(f"short:{group}")

    deload_week = None
    if program.get("deload"):
        deload_week = {
            "sets_multiplier": config["deload_sets_multiplier"],
            "note": "Final week: same sessions with sets scaled down to promote recovery.",
        }

    return {
        "$schema_version": MODEL_VERSION,
        "created_at": f"{today.isoformat()}T00:00:00Z",
        "user": {"name": ctx["profile"]["user"]["name"]},
        "program": program,
        "dataset": {"name": ctx["ds_name"], "repo": ctx["ds"]["repo"],
                    "ref": ctx["ds"]["ref"], "commit": commit},
        "rules_applied": ctx["rules"],
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
    lines.append(f"Generated {plan['created_at'][:10]} for {plan['user']['name']} "
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
            # RIR and superset pairing ride inside the existing columns: the
            # render is the person's printable copy, and a table that grows a
            # column every time the plan learns a field stops being one.
            name = ex["name"]
            if ex.get("superset_group"):
                name = f"[{ex['superset_group']}] {name}"
            prescription = f"{ex['sets']} × {ex['reps']}"
            if ex.get("rir") is not None:
                prescription += f" @ {ex['rir']} RIR"
            lines.append(f"| {name} | {ex['equipment']} | {prescription} |")
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
        "user": {"name": "Fixture"},
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
        "program": {
            "name": "Fixture Block", "emoji": "🧪", "primary_goal": "hypertrophy",
            "days_per_week": days, "session_minutes": "60-90", "split": split,
            "deload": deload,
        },
        "volume": volume or fixture_volume_block(),
    }


def stand_in_selection(brief):
    """A coach-shaped stub for the self-test: one exercise per muscle the day
    trains, top of the pool, at the default sets and the low end of the band.
    It exists so compose and its refusals can be exercised offline. It is not a
    fitting algorithm and nothing outside this self-test may call it."""
    sessions = []
    for session in brief["sessions"]:
        exercises = []
        for group in session["groups"]:
            pool = brief["candidates"].get(group) or []
            if not pool or len(exercises) >= brief["max_exercises_per_session"]:
                continue
            pick = pool[0]
            exercises.append({
                "id": pick["id"],
                "sets": brief["sets_per_exercise"],
                "reps": brief["reps_band"][pick["kind"]],
                "rir": 2,
            })
        sessions.append({"day": session["day"], "exercises": exercises})
    return {"sessions": sessions}


def run_self_test(config, descriptor):
    ds_name, ds = pick_dataset(descriptor, None)
    records = load_json(script_dir() / "generate.fixture.json", "fixture")
    today = datetime.date(2026, 8, 6)
    default_rules = config["default_rules"]

    def ctx_for(profile, program_data, rules=None):
        return prepare(profile, program_data, records, ds_name, ds,
                       merge_rules(default_rules, rules), config)

    def brief_for(profile, program_data, rules=None):
        return build_brief(ctx_for(profile, program_data, rules), config)

    def plan_for(profile, program_data, rules=None, selection=None):
        ctx = ctx_for(profile, program_data, rules)
        brief = build_brief(ctx, config)
        return compose_plan(ctx, selection or stand_in_selection(brief), brief, config, today)

    def pool_names(brief):
        return [c["name"] for pool in brief["candidates"].values() for c in pool]

    def refuses(fn):
        # The refusal message is the point of the check, not noise to print: a
        # passing self-test should say nothing but OK.
        saved, sys.stderr = sys.stderr, io.StringIO()
        try:
            fn()
        except SystemExit as exc:
            return exc.code != 0
        finally:
            sys.stderr = saved
        return False

    failures = []

    def check(cond, label):
        if not cond:
            failures.append(label)

    # 1. Category filter and muscle_ignore: cardio, stretch and neck-only rows are never offered.
    brief = brief_for(fixture_profile(), fixture_program_data())
    names = pool_names(brief)
    check("jump rope" not in names, "cardio row leaked into the candidates")
    check("standing hamstring stretch" not in names, "stretch row leaked into the candidates")
    check("lying neck bridge" not in names, "ignored-muscle row leaked into the candidates")

    # 2. The budget is a ceiling, and every target group has something to offer.
    check(brief["max_exercises_per_session"] <= 6, "budget exceeds exercises_per_session")
    check(all(brief["candidates"][g] for g in brief["targets"]),
          "a muscle group was offered no candidates at all")

    # 3. Equipment tier: at tier 1 no machine equipment is offered.
    tier1 = brief_for(fixture_profile(), fixture_program_data(
        volume=fixture_volume_block(tier=1)))
    eqs = {c["equipment"] for pool in tier1["candidates"].values() for c in pool}
    check(not eqs & {"cable", "leverage machine", "sled machine", "smith machine", "assisted"},
          f"tier-1 candidates include machine equipment: {sorted(eqs)}")

    # 4. Benchmark gate: pullups_5 false removes unassisted pull-ups, keeps assisted/band.
    gated = pool_names(brief_for(fixture_profile(pullups=False), fixture_program_data()))
    check("pull-up" not in gated, "gated pull-up still offered")
    check(any(n in gated for n in ("assisted pull-up", "band pull-up")),
          "gate removed the assisted alternatives too")

    # 5. Determinism: the brief is the reproducible half, and stays byte-identical.
    again = brief_for(fixture_profile(), fixture_program_data())
    check(json.dumps(brief, sort_keys=True) == json.dumps(again, sort_keys=True),
          "two identical runs produced different briefs")

    # 6. Personal rules: exclusion, must_include flagging, unknown-name warning.
    ruled = brief_for(fixture_profile(), fixture_program_data(), rules={
        "exclude": {"exercises": ["barbell squat", "flying pig"]},
        "focus": {"muscles": ["shoulders"], "must_include": ["dumbbell fly"]},
    })
    check("barbell squat" not in pool_names(ruled), "excluded exercise still offered")
    check(any(c["must_include"] for pool in ruled["candidates"].values() for c in pool),
          "must_include exercise not flagged in the candidates")
    check("unknown_exclude_exercise:flying pig" in ruled["warnings"],
          "unknown exclusion name not warned about")

    # 6b. The markdown rules format parses to exactly what the JSON shape used to be.
    parsed = parse_rules_md("""
# My rules

A note to self that is not a rule.

## Exclude exercises
- barbell squat
- flying pig

## Exclude equipment

## Focus muscles
* shoulders

## Must include
- dumbbell fly

## Order
- must_include_first
- compound_before_isolation
""", "<self-test>")
    check(parsed == {
        "exclude": {"exercises": ["barbell squat", "flying pig"], "equipment": []},
        "focus": {"muscles": ["shoulders"], "must_include": ["dumbbell fly"]},
        "order": ["must_include_first", "compound_before_isolation"],
    }, f"rules.md parsed to {parsed!r}")
    md_ruled = brief_for(fixture_profile(), fixture_program_data(), rules={
        k: v for k, v in parsed.items() if k != "order"})
    md_pool = {c["name"]: c for pool in md_ruled["candidates"].values() for c in pool}
    check("barbell squat" not in md_pool
          and md_pool.get("dumbbell fly", {}).get("must_include"),
          "rules.md exclusion/must_include did not reach the candidates")

    # 7. Even distribution (coaching.md § 4): a muscle's weekly sets land evenly
    #    across the days that train it, and still sum to the allocation.
    for group, total in brief["targets"].items():
        per_day = [s["sets_per_muscle"][group]
                   for s in brief["sessions"] if group in s["sets_per_muscle"]]
        check(sum(per_day) == int(total), f"{group}: per-session sets sum to {sum(per_day)}, "
                                          f"not the {int(total)} allocated")
        check(max(per_day) - min(per_day) <= 1, f"{group}: sets spread unevenly {per_day}")

    # 8. Shortfall honesty: an unreachable target is reported, never silent.
    starved = fixture_volume_block(cap=3)
    starved["per_muscle_weekly_sets"] = dict(
        starved["per_muscle_weekly_sets"], hamstrings=40)
    short = plan_for(fixture_profile(), fixture_program_data(days=3, volume=starved))
    check("short:hamstrings" in short["warnings"], "unreachable target not reported short")

    # 9. Upper/lower split: an upper day is only ever budgeted upper-body sets.
    ul = brief_for(fixture_profile(), fixture_program_data(split="upper_lower", days=4))
    for s in ul["sessions"]:
        allowed = set(config["split_sessions"]["upper_lower"]["groups"][s["focus"]])
        for group in s["sets_per_muscle"]:
            check(group in allowed, f"day {s['day']} ({s['focus']}) budgets {group}")

    # 10. Deload flag round-trips through compose.
    check(plan_for(fixture_profile(), fixture_program_data())["deload_week"] is not None,
          "deload requested but deload_week missing")
    check(plan_for(fixture_profile(), fixture_program_data(deload=False))["deload_week"] is None,
          "deload_week present without deload")

    # 11. The two refusals: an exercise never offered, and a rep target under the floor.
    profile, program_data = fixture_profile(), fixture_program_data()
    intruder = stand_in_selection(brief)
    intruder["sessions"][0]["exercises"][0]["id"] = "not-a-real-exercise"
    check(refuses(lambda: plan_for(profile, program_data, selection=intruder)),
          "an exercise outside the candidate pool was accepted")
    under = stand_in_selection(brief)
    under["sessions"][0]["exercises"][0]["reps"] = "2"
    check(refuses(lambda: plan_for(profile, program_data, selection=under)),
          "a rep target under the floor was accepted")
    typo = stand_in_selection(brief)
    typo["sessions"][0]["exercises"][0]["rirr"] = 2
    check(refuses(lambda: plan_for(profile, program_data, selection=typo)),
          "an unknown selection key was silently dropped")

    # 12. Omitting reps is allowed: the goal's default band fills in, and the floor
    #     check reads that default rather than refusing the omission.
    bare = stand_in_selection(brief)
    for s in bare["sessions"]:
        for ex in s["exercises"]:
            del ex["reps"]
    composed = plan_for(profile, program_data, selection=bare)
    kind_of = {c["id"]: c["kind"] for pool in brief["candidates"].values() for c in pool}
    check(all(ex["reps"] == brief["reps_band"][kind_of[ex["id"]]]
              for s in composed["sessions"] for ex in s["exercises"]),
          "omitted reps did not fall back to the goal's default band")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return False
    print(f"OK: {ds_name} fixture — all invariant groups hold")
    return True


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        description="Decide what is legal and what each muscle is owed (--brief); "
                    "compose a plan from the coach's selection (--selection).",
    )
    p.add_argument("--profile", help="path to profile.json")
    p.add_argument("--program", help="path to programs/program-*.json with a volume block")
    p.add_argument("--rules", help="path to a personal rules.md (optional; .json also accepted)")
    p.add_argument("--dataset-dir", help="path to the cloned dataset repository")
    p.add_argument("--dataset", help="dataset key in the descriptor (default: its \"default\")")
    p.add_argument("--descriptor", help="path to assets/datasets.json (default: alongside the skill)")
    p.add_argument("--config", help="path to generate.config.json (default: alongside this script)")
    p.add_argument("--today", help="YYYY-MM-DD, for a deterministic created_at. Defaults to the real date.")
    p.add_argument("--brief", action="store_true",
                   help="print the budget and the candidate pools, and stop. Choose from these.")
    p.add_argument("--selection", help="path to a selection.json of chosen exercises")
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
    personal = load_rules(args.rules) if args.rules else None

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

    ctx = prepare(profile, program_data, records, ds_name, ds, rules, config)
    brief = build_brief(ctx, config)

    if args.brief:
        print(json.dumps(brief, indent=2, ensure_ascii=False))
        sys.exit(0)

    if not args.selection:
        fail_usage("--selection is required to write a plan; run --brief first to see the "
                   "candidates, then pass back what you chose")
    selection = load_json(args.selection, "selection file")
    plan = compose_plan(ctx, selection, brief, config, today,
                        commit=dataset_commit(dataset_dir))

    # Both targets are checked before either is written: a refused run must
    # not leave an orphan half of the dated .json/.md pair behind.
    out = Path(args.write) if args.write else None
    out_md = Path(args.write_md) if args.write_md else None
    if out and out.exists():
        fail_usage(f"{args.write} already exists — plans are never overwritten; "
                   f"pick the next -2/-3 suffix")
    if out_md and out_md.exists():
        fail_usage(f"{args.write_md} already exists — pick the next -2/-3 suffix")

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"wrote {args.write}")
    else:
        print(json.dumps(plan, indent=2, ensure_ascii=False))

    if out_md:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(plan), encoding="utf-8")
        print(f"wrote {args.write_md}")

    sys.exit(0)


if __name__ == "__main__":
    # Program emoji and en dashes reach stdout; a cp1252 console (Windows) would
    # otherwise die on them. Bytes on disk are always UTF-8 regardless.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    main()
