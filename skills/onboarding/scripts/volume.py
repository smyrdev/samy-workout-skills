#!/usr/bin/env python3
"""Weekly training-volume allocator for samy-workout-skills.

Reads a profile.json and a set of program answers (goal, days/week, session
length, split), and computes a weekly per-muscle set allocation. Every tunable
number lives in volume.config.json, next to this file — this script holds the
algorithm only.

Usage:
    volume.py --profile PROFILE.json --goal GOAL --days N --session SESSION \\
        --split SPLIT [--today YYYY-MM-DD] [--write PROGRAM.json]

    volume.py --profile PROFILE.json --write PROGRAM.json
        (goal/days/session/split are read from the "program" object already
        in PROGRAM.json when the flags are omitted)

    volume.py --self-test

Exit codes: 0 success, 2 usage error (bad invocation), 3 input error (a file
or a value inside it is missing or unrecognized). Unknown enum values are
refused, never guessed.
"""

import argparse
import datetime
import json
import math
import sys
from pathlib import Path

MODEL_VERSION = "1.0"
DEFAULT_STYLE = "balanced"
DATE_RE_FULL = None  # not used; validated by simple parsing below


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


def default_config_path():
    return Path(__file__).resolve().parent / "volume.config.json"


def load_config(path):
    cfg = load_json(path, "config")
    required = [
        "canonical_muscle_order", "exercises_per_session", "sets_per_exercise",
        "goal_exercise_density", "style_multipliers", "rest_seconds_by_goal",
        "target_weekly_sets_per_muscle", "base_weights", "goal_multipliers",
        "split_multipliers", "equipment_tier", "bodyfat_midpoint",
        "muscle_benchmarks", "max_scale_factor", "mev_sets_per_muscle",
        "full_body_high_frequency_days",
    ]
    missing = [k for k in required if k not in cfg]
    if missing:
        fail_input(f"config missing keys: {', '.join(missing)}")
    return cfg


def parse_date(s, field):
    try:
        parts = s.split("-")
        if len(parts) == 1:
            return datetime.date(int(parts[0]), 1, 1), True  # year-only, approximate
        if len(parts) == 3:
            return datetime.date(int(parts[0]), int(parts[1]), int(parts[2])), False
    except (ValueError, TypeError):
        pass
    fail_input(f"{field} is not a valid date: {s!r}")


def compute_age(dob_str, today):
    dob, year_only = parse_date(dob_str, "basics.date_of_birth")
    age = today.year - dob.year
    if not year_only and (today.month, today.day) < (dob.month, dob.day):
        age -= 1
    return age


def hamilton(weights, total, order):
    """Largest-remainder apportionment of `total` whole sets across `order`,
    proportional to `weights`. Ties broken by position in `order`, so the
    result is byte-identical across platforms."""
    if total <= 0:
        return {m: 0 for m in order}
    weight_sum = sum(weights[m] for m in order)
    if weight_sum <= 0:
        base, rem = divmod(total, len(order))
        result = {m: base for m in order}
        for m in order[:rem]:
            result[m] += 1
        return result
    exact = {m: weights[m] / weight_sum * total for m in order}
    floors = {m: math.floor(exact[m]) for m in order}
    remainder = total - sum(floors.values())
    ranked = sorted(order, key=lambda m: (-(exact[m] - floors[m]), order.index(m)))
    result = dict(floors)
    for m in ranked[:remainder]:
        result[m] += 1
    return result


def compute_volume(profile, goal, days, session, split, style, today, config):
    order = config["canonical_muscle_order"]

    lifting = profile.get("experience", {}).get("lifting")
    bracket = profile.get("basics", {}).get("bodyfat_bracket")
    gym_type = profile.get("gym", {}).get("type")
    dob = profile.get("basics", {}).get("date_of_birth")
    benchmarks = profile.get("strength_benchmarks", {})

    if goal not in config["sets_per_exercise"]:
        fail_input(f"unknown goal: {goal!r}")
    if goal not in config["goal_exercise_density"]:
        fail_input(f"goal missing from goal_exercise_density: {goal!r}")
    if session not in config["exercises_per_session"]:
        fail_input(f"unknown session: {session!r}")
    if split not in config["split_multipliers"]:
        fail_input(f"unknown split: {split!r}")
    if style not in config["style_multipliers"]:
        fail_input(f"unknown style: {style!r}")
    if goal not in config["rest_seconds_by_goal"]:
        fail_input(f"goal missing from rest_seconds_by_goal: {goal!r}")
    if not isinstance(days, int) or not (3 <= days <= 7):
        fail_input(f"days must be an integer 3-7, got {days!r}")
    if lifting not in config["target_weekly_sets_per_muscle"]:
        fail_input(f"profile experience.lifting is missing or unknown: {lifting!r}")
    if bracket not in config["bodyfat_midpoint"]:
        fail_input(f"profile basics.bodyfat_bracket is missing or unknown: {bracket!r}")
    if gym_type not in config["equipment_tier"]:
        fail_input(f"profile gym.type is missing or unknown: {gym_type!r}")
    if not dob:
        fail_input("profile basics.date_of_birth is missing")
    missing_benchmarks = [
        k for k in (
            "pullups_5", "pullups_10", "dips_10", "pushups_15",
            "bench_press_10", "incline_press_10", "overhead_press_10",
        ) if k not in benchmarks
    ]
    if missing_benchmarks:
        fail_input(f"profile strength_benchmarks missing keys: {', '.join(missing_benchmarks)}")

    # Session length buys exercise slots; the goal decides how many of them the clock affords,
    # because rest between sets is longer for strength. `sets_per_exercise` stays the
    # prescription — one meaning per field, so generation can write it onto an exercise as-is.
    style_mult = config["style_multipliers"][style]

    slots = config["exercises_per_session"][session]
    density = config["goal_exercise_density"][goal] * style_mult["exercise_density"]
    exercises_per_session = max(1, math.floor(slots * density + 0.5))
    sets_per_exercise = config["sets_per_exercise"][goal]
    target = max(1, math.floor(
        config["target_weekly_sets_per_muscle"][lifting] * style_mult["target_sets"] + 0.5
    ))
    max_scale = config["max_scale_factor"]

    weights = {
        m: config["base_weights"][m]
        * config["goal_multipliers"][goal][m]
        * config["split_multipliers"][split][m]
        for m in order
    }

    capacity = days * exercises_per_session * sets_per_exercise
    weight_total = sum(weights[m] for m in order)
    theoretical_target = target * weight_total

    scale_raw = capacity / theoretical_target if theoretical_target > 0 else 0
    scale_factor = min(scale_raw, max_scale)

    if scale_raw <= max_scale:
        allocated_total = capacity
    else:
        allocated_total = round(theoretical_target * max_scale)

    per_muscle = hamilton(weights, allocated_total, order)
    unallocated = capacity - allocated_total

    age = compute_age(dob, today)
    bodyfat_midpoint = config["bodyfat_midpoint"][bracket]
    equipment_tier = config["equipment_tier"][gym_type]
    benchmarks_cleared = sum(1 for v in benchmarks.values() if v is True)

    warnings = []
    if per_muscle and min(per_muscle.values()) < config["mev_sets_per_muscle"]:
        warnings.append("capacity_below_mev")
    if unallocated > 0:
        warnings.append("capacity_exceeds_target")
    for muscle, keys in config["muscle_benchmarks"].items():
        if not any(benchmarks.get(k) is True for k in keys):
            warnings.append(f"untrained:{muscle}")
    if split == "full_body" and days >= config["full_body_high_frequency_days"]:
        warnings.append("full_body_high_frequency")

    return {
        "model_version": MODEL_VERSION,
        "age": age,
        "bodyfat_midpoint": bodyfat_midpoint,
        "equipment_tier": equipment_tier,
        "benchmarks_cleared": benchmarks_cleared,
        "style": style,
        "exercises_per_session": exercises_per_session,
        "sets_per_exercise": sets_per_exercise,
        "reps_in_reserve": style_mult["reps_in_reserve"],
        "rest_seconds": config["rest_seconds_by_goal"][goal],
        "weekly_set_capacity": capacity,
        "weekly_sets_allocated": allocated_total,
        "unallocated_sets": unallocated,
        "target_weekly_sets_per_muscle": target,
        "scale_factor": round(scale_factor, 3),
        "per_muscle_weekly_sets": {m: per_muscle[m] for m in order},
        "warnings": warnings,
    }


def run_self_test(config):
    order = config["canonical_muscle_order"]
    goals = list(config["sets_per_exercise"].keys())
    days_range = range(3, 8)
    sessions = list(config["exercises_per_session"].keys())
    splits = list(config["split_multipliers"].keys())
    liftings = list(config["target_weekly_sets_per_muscle"].keys())
    styles = list(config["style_multipliers"].keys())

    base_profile = {
        "basics": {"date_of_birth": "1994-06-15", "bodyfat_bracket": "13-17"},
        "gym": {"type": "commercial_gym"},
        "strength_benchmarks": {
            "pullups_5": True, "pullups_10": False, "dips_10": True,
            "pushups_15": True, "bench_press_10": True,
            "incline_press_10": True, "overhead_press_10": False,
        },
    }
    today = datetime.date(2026, 8, 6)

    combos = 0
    for lifting in liftings:
        profile = dict(base_profile, experience={"lifting": lifting})
        for goal in goals:
            for days in days_range:
                for session in sessions:
                    for split in splits:
                        for style in styles:
                            v = compute_volume(
                                profile, goal, days, session, split, style, today, config
                            )
                            combos += 1
                            allocated_sum = sum(v["per_muscle_weekly_sets"].values())
                            if allocated_sum != v["weekly_sets_allocated"]:
                                print(
                                    f"FAIL: per-muscle sum {allocated_sum} != "
                                    f"weekly_sets_allocated {v['weekly_sets_allocated']} "
                                    f"for lifting={lifting} goal={goal} days={days} "
                                    f"session={session} split={split} style={style}",
                                    file=sys.stderr,
                                )
                                return False
    expected_combos = (
        len(liftings) * len(goals) * len(list(days_range))
        * len(sessions) * len(splits) * len(styles)
    )
    if combos != expected_combos or expected_combos != 2160:
        print(f"FAIL: expected 2160 combinations, ran {combos}", file=sys.stderr)
        return False

    # Worked cases pinned by value, not just by balance — a config retune or an algorithm shift
    # has to be acknowledged here rather than sliding through green. Update the expected numbers
    # deliberately when you retune, never to make the test pass.
    worked = [
        (
            "advanced/hypertrophy/6d/60-90/upper_lower/balanced",
            dict(base_profile, experience={"lifting": "advanced"}),
            dict(goal="hypertrophy", days=6, session="60-90", split="upper_lower",
                 style="balanced"),
            dict(exercises_per_session=9, sets_per_exercise=3, weekly_set_capacity=162,
                 weekly_sets_allocated=162, target_weekly_sets_per_muscle=18,
                 reps_in_reserve=2, rest_seconds="120-180"),
        ),
        (
            "beginner/strength/3d/20-40/full_body/high_intensity",
            dict(base_profile, experience={"lifting": "beginner"}),
            dict(goal="strength", days=3, session="20-40", split="full_body",
                 style="high_intensity"),
            dict(exercises_per_session=3, sets_per_exercise=4, weekly_set_capacity=36,
                 weekly_sets_allocated=36, target_weekly_sets_per_muscle=6,
                 reps_in_reserve=0, rest_seconds="180-300"),
        ),
    ]
    for label, profile, args, expected in worked:
        v = compute_volume(
            profile, args["goal"], args["days"], args["session"], args["split"],
            args["style"], today, config,
        )
        if sum(v["per_muscle_weekly_sets"].values()) != v["weekly_sets_allocated"]:
            print(f"FAIL: worked case {label} did not balance: {v}", file=sys.stderr)
            return False
        if list(v["per_muscle_weekly_sets"].keys()) != order:
            print("FAIL: per_muscle_weekly_sets is not in canonical order", file=sys.stderr)
            return False
        for key, want in expected.items():
            if v[key] != want:
                print(
                    f"FAIL: worked case {label}: {key} is {v[key]!r}, expected {want!r}",
                    file=sys.stderr,
                )
                return False

    print(f"OK: {combos} enum combinations balanced, 2 worked cases reproduced by value")
    return True


def build_parser():
    p = argparse.ArgumentParser(
        description="Compute a weekly per-muscle set allocation from a profile and program answers.",
    )
    p.add_argument("--profile", help="path to profile.json")
    p.add_argument("--goal", choices=["hypertrophy", "strength", "both"])
    p.add_argument("--days", type=int, choices=[3, 4, 5, 6, 7])
    p.add_argument(
        "--session",
        choices=["up_to_20", "20-40", "40-60", "60-90", "90-120", "over_120"],
    )
    p.add_argument("--split", choices=["full_body", "upper_lower"])
    p.add_argument("--style", choices=["balanced", "high_volume", "high_intensity"])
    p.add_argument("--today", help="YYYY-MM-DD, for deterministic age. Defaults to the real date.")
    p.add_argument("--write", help="merge the volume block into this program.json in place")
    p.add_argument("--config", help="path to volume.config.json (default: alongside this script)")
    p.add_argument("--self-test", action="store_true", help="run the built-in self-test and exit")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config or default_config_path())

    if args.self_test:
        ok = run_self_test(config)
        sys.exit(0 if ok else 1)

    if not args.profile:
        fail_usage("--profile is required")
    profile = load_json(args.profile, "profile")

    program_data = None
    if args.write:
        program_path = Path(args.write)
        if not program_path.is_file():
            fail_input(f"--write target not found: {args.write}")
        program_data = load_json(args.write, "program file")

    goal, days, session, split = args.goal, args.days, args.session, args.split
    style = args.style
    if None in (goal, days, session, split, style):
        if program_data is None:
            fail_usage(
                "--goal, --days, --session and --split are required unless "
                "--write points at a program.json that already has a program block"
            )
        existing = program_data.get("program")
        if not isinstance(existing, dict):
            fail_input(f"{args.write} has no \"program\" object to read defaults from")
        goal = goal or existing.get("primary_goal")
        days = days if days is not None else existing.get("days_per_week")
        session = session or existing.get("session_minutes")
        split = split or existing.get("split")
        # `style` post-dates the other four. A program file written before it existed gets the
        # documented default rather than a refusal — an absent optional field is not an
        # unknown value, and DEFAULT_STYLE is the no-op multiplier row.
        style = style or existing.get("style") or DEFAULT_STYLE
        if None in (goal, days, session, split):
            fail_input(f"{args.write} program block is missing goal/days/session/split")

    if args.today:
        try:
            y, m, d = (int(x) for x in args.today.split("-"))
            today = datetime.date(y, m, d)
        except (ValueError, TypeError):
            fail_usage(f"--today is not a valid YYYY-MM-DD date: {args.today}")
    else:
        today = datetime.date.today()

    volume = compute_volume(profile, goal, days, session, split, style, today, config)

    if args.write:
        program_data["volume"] = volume
        with Path(args.write).open("w", encoding="utf-8") as f:
            json.dump(program_data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"wrote volume block to {args.write}")
    else:
        print(json.dumps(volume, indent=2, ensure_ascii=False))

    sys.exit(0)


if __name__ == "__main__":
    main()
