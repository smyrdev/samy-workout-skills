#!/usr/bin/env python3
"""Validates the onboarding and generation skills against their own schemas and rules.

Stdlib only. Run from the repository root:

    python scripts/validate-skills.py

Exits 0 with nothing printed on success. Exits 1 and prints one line per failure otherwise.
This is what keeps the thin-SKILL.md / externalized-rules split from silently rotting: nothing
here is optional, everything here is checked.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "onboarding"
GEN_DIR = ROOT / "skills" / "generation"

FAILURES = []


def fail(msg):
    FAILURES.append(msg)


# --------------------------------------------------------------------------------------
# Frontmatter parsing (hand-rolled, no PyYAML) — only the subset our SKILL.md files use.
# --------------------------------------------------------------------------------------

def parse_frontmatter(text):
    """Returns (fields, raw_values, body) or (None, None, None) if malformed.

    fields: key -> parsed string value (block scalars joined with newlines)
    raw_values: key -> the raw first-line value exactly as written (used to check
                whether a value was quoted/single-line, e.g. '"..."' vs '>' or '|')
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, None, None
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, None, None
    body_lines = lines[1:end]
    body = "\n".join(lines[end + 1:])

    fields, raw = {}, {}
    i = 0
    while i < len(body_lines):
        line = body_lines[i]
        if not line.strip():
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s?(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2)
        raw[key] = val
        if val.strip() in (">", "|", ">-", "|-", ""):
            block = []
            j = i + 1
            while j < len(body_lines) and (body_lines[j].startswith("  ") or not body_lines[j].strip()):
                block.append(body_lines[j].strip())
                j += 1
            fields[key] = "\n".join(b for b in block if b)
            i = j
        else:
            v = val.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                v = v[1:-1]
            fields[key] = v
            i += 1
    return fields, raw, body


def is_quoted_single_line(raw_value):
    v = raw_value.strip()
    if v in (">", "|", ">-", "|-", ""):
        return False
    return len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"')


# --------------------------------------------------------------------------------------
# 1. SKILL.md frontmatter shape
# --------------------------------------------------------------------------------------

def check_skill_frontmatter():
    checks = (
        (SKILL_DIR / "SKILL.md", True),
        (ROOT / ".claude" / "skills" / "onboard" / "SKILL.md", False),
        (GEN_DIR / "SKILL.md", True),
        (ROOT / ".claude" / "skills" / "generate" / "SKILL.md", False),
    )
    for path, exact_keys in checks:
        rel = path.relative_to(ROOT)
        if not path.is_file():
            fail(f"{rel}: file not found")
            continue
        fields, raw, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        if fields is None:
            fail(f"{rel}: frontmatter does not parse (missing --- delimiters)")
            continue
        if "name" not in fields or "description" not in fields:
            fail(f"{rel}: frontmatter must contain both name and description")
            continue
        if exact_keys and set(fields.keys()) != {"name", "description"}:
            extra = set(fields.keys()) - {"name", "description"}
            fail(f"{rel}: frontmatter must carry exactly name + description, found extra keys: {sorted(extra)}")
        if not is_quoted_single_line(raw.get("description", "")):
            fail(f"{rel}: description must be a quoted, single-line string")


# --------------------------------------------------------------------------------------
# 2. Portable SKILL.md is vendor-neutral
# --------------------------------------------------------------------------------------

VENDOR_TOOL_WORDS = ["AskUserQuestion", "Bash"]
# "Write" / "Read" only count as violations when used as a tool reference, not as plain verbs.
VENDOR_TOOL_PHRASES = [
    "the Write tool", "the Read tool", "use Write", "use Read", "call Read", "call Write",
]
ABS_PATH_PATTERNS = [
    re.compile(r"(?:^|[\s`(\[])/(?:home|Users|root)/"),
    re.compile(r"[A-Za-z]:\\\\"),
    re.compile(r"[A-Za-z]:\\[^\\]"),
]


def check_portable_skill_neutrality():
    for path in (SKILL_DIR / "SKILL.md", GEN_DIR / "SKILL.md"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)

        for word in VENDOR_TOOL_WORDS:
            if re.search(rf"\b{re.escape(word)}\b", text):
                fail(f"{rel}: contains vendor tool name {word!r} — keep this file vendor-neutral")
        for phrase in VENDOR_TOOL_PHRASES:
            if phrase in text:
                fail(f"{rel}: contains vendor tool reference {phrase!r} — keep this file vendor-neutral")
        for pattern in ABS_PATH_PATTERNS:
            if pattern.search(text):
                fail(f"{rel}: appears to contain an absolute or Windows-specific path")


# --------------------------------------------------------------------------------------
# 3. SKILL.md and CLAUDE.md contain no rule content (enum values / bracket strings)
# --------------------------------------------------------------------------------------

def rule_content_tokens():
    profile_schema = load_json(SKILL_DIR / "schema" / "profile.schema.json")
    program_schema = load_json(SKILL_DIR / "schema" / "program.schema.json")
    tokens = set()
    if profile_schema:
        tokens.update(profile_schema["properties"]["basics"]["properties"]["bodyfat_bracket"]["enum"])
        tokens.update(profile_schema["properties"]["gym"]["properties"]["type"]["enum"])
    if program_schema:
        prog = program_schema["properties"]["program"]["properties"]
        tokens.update(prog["session_minutes"]["enum"])
        tokens.update(prog["primary_goal"]["enum"])
    # "strength" and "both" are ordinary English words and would false-positive constantly;
    # "hypertrophy" is the distinctive, unambiguous member of primary_goal worth checking.
    tokens = {t for t in tokens if t not in ("strength", "both")}
    return tokens


def check_no_rule_content():
    tokens = rule_content_tokens()
    if not tokens:
        fail("could not derive rule-content tokens from schemas — skipping is not an option, fix the schemas")
        return
    targets = [
        SKILL_DIR / "SKILL.md",
        ROOT / ".claude" / "skills" / "onboard" / "SKILL.md",
        GEN_DIR / "SKILL.md",
        ROOT / ".claude" / "skills" / "generate" / "SKILL.md",
        ROOT / "CLAUDE.md",
    ]
    for path in targets:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        for token in sorted(tokens):
            if token in text:
                fail(f"{rel}: contains rule content {token!r} — belongs in questions.yaml or FIELDS.md")


# --------------------------------------------------------------------------------------
# 4. questions.yaml — minimal hand-rolled parser, every `stores`/`store` path exists in schema
# --------------------------------------------------------------------------------------

def parse_flow_map(line):
    inner = line.strip()
    inner = re.sub(r"^(?:-\s*)?\{", "", inner)
    inner = re.sub(r"\}\s*$", "", inner)
    result = {}
    parts = re.findall(r'(?:[^,"]|"(?:[^"\\]|\\.)*")+', inner)
    for part in parts:
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        result[k] = v
    return result


def parse_questions_yaml(text):
    lines = text.splitlines()
    entries = []
    current = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^- id:\s*(.+)$", line)
        if m:
            if current is not None:
                entries.append(current)
            current = {"id": m.group(1).strip(), "options": [], "options_imperial": []}
            i += 1
            continue
        m = re.match(r"^  ([a-zA-Z_]+):\s?(.*)$", line)
        if m and current is not None:
            key, val = m.group(1), m.group(2)
            if key in ("options", "options_imperial"):
                items = []
                j = i + 1
                while j < len(lines):
                    # An option is either a one-line flow map, or a block whose keys are
                    # indented under it — the block form is what carries a `stores:` map.
                    if re.match(r"^\s{4}- \{.*\}\s*$", lines[j]):
                        items.append(parse_flow_map(lines[j]))
                        j += 1
                        continue
                    m_opt = re.match(r"^\s{4}- ([a-zA-Z_]+):\s?(.*)$", lines[j])
                    if not m_opt:
                        break
                    option = {}
                    option[m_opt.group(1)] = m_opt.group(2).strip().strip('"').strip("'")
                    j += 1
                    while j < len(lines):
                        m_kv = re.match(r"^\s{6}([a-zA-Z_]+):\s?(.*)$", lines[j])
                        if not m_kv:
                            break
                        k2, v2 = m_kv.group(1), m_kv.group(2).strip()
                        if v2.startswith("{"):
                            option[k2] = parse_flow_map(v2)
                        else:
                            option[k2] = v2.strip('"').strip("'")
                        j += 1
                    items.append(option)
                current[key] = items
                i = j
                continue
            if val.strip() == "|":
                block = []
                j = i + 1
                while j < len(lines) and (lines[j].startswith("    ") or not lines[j].strip()):
                    block.append(lines[j][4:] if lines[j].startswith("    ") else lines[j])
                    j += 1
                current[key] = "\n".join(block)
                i = j
                continue
            v = val.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                v = v[1:-1]
            current[key] = v
            i += 1
            continue
        i += 1
    if current is not None:
        entries.append(current)
    return entries


def resolve_schema_path(schema, path):
    node = schema
    for part in path.split("."):
        props = node.get("properties")
        if not isinstance(props, dict) or part not in props:
            return False
        node = props[part]
    return True


def check_questions_yaml(profile_schema, program_schema):
    path = SKILL_DIR / "questions.yaml"
    if not path.is_file():
        fail("skills/onboarding/questions.yaml not found")
        return
    text = path.read_text(encoding="utf-8")
    try:
        entries = parse_questions_yaml(text)
    except Exception as e:  # pragma: no cover - defensive
        fail(f"skills/onboarding/questions.yaml failed to parse: {e}")
        return
    if not entries:
        fail("skills/onboarding/questions.yaml: no question entries found")
        return

    schemas = {"profile": profile_schema, "program": program_schema}
    for entry in entries:
        qid = entry.get("id", "<unknown>")
        scope = entry.get("scope")
        if scope not in schemas:
            fail(f"questions.yaml[{qid}]: scope must be 'profile' or 'program', got {scope!r}")
            continue
        schema = schemas[scope]

        qtype = entry.get("type")
        if qtype not in ("choice", "multi_select", "text"):
            fail(f"questions.yaml[{qid}]: type must be choice/multi_select/text, got {qtype!r}")

        # Entries may store per-option instead of via a single `stores:` path — one path via an
        # option's `store`, or several at once via an option's `stores` map.
        option_stores = []
        for o in entry.get("options", []):
            if "store" in o:
                option_stores.append(o["store"])
            if isinstance(o.get("stores"), dict):
                option_stores.extend(o["stores"].keys())
        if option_stores:
            for store_path in option_stores:
                if not resolve_schema_path(schema, store_path):
                    fail(f"questions.yaml[{qid}]: option store path {store_path!r} not found in {scope} schema")
        elif "stores" in entry:
            if not resolve_schema_path(schema, entry["stores"]):
                fail(f"questions.yaml[{qid}]: stores path {entry['stores']!r} not found in {scope} schema")
        else:
            fail(f"questions.yaml[{qid}]: has neither `stores` nor per-option `store`")


# --------------------------------------------------------------------------------------
# 5. A tiny JSON Schema (2020-12 subset) validator — only what our two schemas use.
# --------------------------------------------------------------------------------------

def validate_instance(instance, schema, path, errors):
    if "oneOf" in schema:
        matches = [s for s in schema["oneOf"] if _matches(instance, s)]
        if len(matches) != 1:
            errors.append(f"{path}: does not match exactly one branch of oneOf ({len(matches)} matched)")
        return

    if "const" in schema:
        if instance != schema["const"]:
            errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
        return

    if "enum" in schema:
        if instance not in schema["enum"]:
            errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")
        return

    types = schema.get("type")
    if types is not None:
        allowed = types if isinstance(types, list) else [types]
        if not any(_type_matches(instance, t) for t in allowed):
            errors.append(f"{path}: expected type {allowed}, got {type(instance).__name__}")
            return

    if schema.get("type") == "object" or (isinstance(instance, dict) and "properties" in schema):
        if not isinstance(instance, dict):
            return
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{path}: missing required key {key!r}")
        props = schema.get("properties", {})
        extra = sorted(set(instance.keys()) - set(props.keys()))
        additional = schema.get("additionalProperties")
        if additional is False:
            if extra:
                errors.append(f"{path}: unexpected keys {extra}")
        elif isinstance(additional, dict):
            # Open-keyed map with a fixed value shape — targets in plan.schema.json.
            for key in extra:
                validate_instance(instance[key], additional, f"{path}.{key}", errors)
        for key, subschema in props.items():
            if key in instance:
                validate_instance(instance[key], subschema, f"{path}.{key}", errors)

    if schema.get("type") == "string" and isinstance(instance, str):
        if "pattern" in schema and not re.match(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} does not match pattern {schema['pattern']}")
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: longer than maxLength {schema['maxLength']}")

    if schema.get("type") in ("number", "integer") and isinstance(instance, (int, float)):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} above maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: {instance} not above exclusiveMinimum {schema['exclusiveMinimum']}")

    if schema.get("type") == "array" and isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: more than maxItems {schema['maxItems']}")
        item_schema = schema.get("items")
        if item_schema:
            for idx, item in enumerate(instance):
                validate_instance(item, item_schema, f"{path}[{idx}]", errors)


def _type_matches(instance, t):
    if t == "object":
        return isinstance(instance, dict)
    if t == "array":
        return isinstance(instance, list)
    if t == "string":
        return isinstance(instance, str)
    if t == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if t == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if t == "boolean":
        return isinstance(instance, bool)
    if t == "null":
        return instance is None
    return True


def _matches(instance, schema):
    errs = []
    validate_instance(instance, schema, "$", errs)
    return not errs


def validate_file_against_schema(path, schema, label):
    data = load_json(path)
    if data is None:
        fail(f"{label}: not valid JSON")
        return
    errs = []
    validate_instance(data, schema, str(path.relative_to(ROOT)), errs)
    for e in errs:
        fail(e)


# --------------------------------------------------------------------------------------
# 6. volume.config.json covers every enum the schemas define
# --------------------------------------------------------------------------------------

def check_volume_config_coverage(profile_schema, program_schema):
    config_path = SKILL_DIR / "scripts" / "volume.config.json"
    config = load_json(config_path)
    if config is None:
        fail("skills/onboarding/scripts/volume.config.json: not valid JSON")
        return

    prog_props = program_schema["properties"]["program"]["properties"]
    session_enum = set(prog_props["session_minutes"]["enum"])
    goal_enum = set(prog_props["primary_goal"]["enum"])
    split_enum = set(prog_props["split"]["enum"])
    style_enum = set(prog_props["style"]["enum"])
    lifting_enum = set(profile_schema["properties"]["experience"]["properties"]["lifting"]["enum"])
    bracket_enum = set(profile_schema["properties"]["basics"]["properties"]["bodyfat_bracket"]["enum"])
    gym_enum = set(profile_schema["properties"]["gym"]["properties"]["type"]["enum"])
    muscles = set(
        program_schema["properties"]["volume"]["oneOf"][1]["properties"]["per_muscle_weekly_sets"]["required"]
    )

    def need(cfg_key, expected, sub=None):
        table = config.get(cfg_key, {})
        if sub:
            table = table.get(sub, {})
            cfg_key = f"{cfg_key}.{sub}"
        have = set(table.keys())
        missing = expected - have
        if missing:
            fail(f"volume.config.json[{cfg_key}]: missing entries for {sorted(missing)}")

    need("exercises_per_session", session_enum)
    need("sets_per_exercise", goal_enum)
    need("goal_exercise_density", goal_enum)
    need("style_multipliers", style_enum)
    need("rest_seconds_by_goal", goal_enum)
    need("target_weekly_sets_per_muscle", lifting_enum)
    need("equipment_tier", gym_enum)
    need("bodyfat_midpoint", bracket_enum)

    have_muscles = set(config.get("base_weights", {}).keys())
    if have_muscles != muscles:
        fail(f"volume.config.json[base_weights]: muscle set {sorted(have_muscles)} != schema's {sorted(muscles)}")
    if set(config.get("canonical_muscle_order", [])) != muscles:
        fail("volume.config.json[canonical_muscle_order]: does not match the schema's muscle set")

    for goal in goal_enum:
        need("goal_multipliers", muscles, sub=goal)
    for split in split_enum:
        need("split_multipliers", muscles, sub=split)


# --------------------------------------------------------------------------------------
# 7. Script self-tests
# --------------------------------------------------------------------------------------

def check_script_self_test(script, label):
    if not script.is_file():
        fail(f"{script.relative_to(ROOT)} not found")
        return
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--self-test"],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:  # pragma: no cover - defensive
        fail(f"{label} --self-test failed to run: {e}")
        return
    if result.returncode != 0:
        fail(f"{label} --self-test failed (exit {result.returncode}): {result.stderr.strip()}")


# --------------------------------------------------------------------------------------
# 8. Generation skill: datasets.json descriptor is complete and internally consistent
# --------------------------------------------------------------------------------------

DESCRIPTOR_REQUIRED_KEYS = [
    "repo", "ref", "data_file", "fields", "category_filter",
    "equipment_tiers", "muscle_map", "muscle_ignore", "benchmark_gates",
]
DESCRIPTOR_REQUIRED_FIELDS = [
    "id", "name", "equipment", "category", "primary_muscle", "movement_group", "volume",
]


def check_datasets_descriptor(program_schema):
    path = GEN_DIR / "datasets.json"
    descriptor = load_json(path)
    if descriptor is None:
        fail("skills/generation/datasets.json: not valid JSON")
        return

    datasets = descriptor.get("datasets")
    if not isinstance(datasets, dict) or not datasets:
        fail("datasets.json: no datasets defined")
        return
    default = descriptor.get("default")
    if default not in datasets:
        fail(f"datasets.json: default {default!r} is not a defined dataset")

    canonical = set(
        program_schema["properties"]["volume"]["oneOf"][1]["properties"]["per_muscle_weekly_sets"]["required"]
    )
    profile_schema = load_json(SKILL_DIR / "schema" / "profile.schema.json")
    benchmark_keys = set(
        profile_schema["properties"]["strength_benchmarks"]["required"]
    ) if profile_schema else set()

    for name, ds in datasets.items():
        missing = [k for k in DESCRIPTOR_REQUIRED_KEYS if k not in ds]
        if missing:
            fail(f"datasets.json[{name}]: missing keys {missing}")
            continue
        missing_fields = [k for k in DESCRIPTOR_REQUIRED_FIELDS if k not in ds["fields"]]
        if missing_fields:
            fail(f"datasets.json[{name}]: fields missing {missing_fields}")

        seen_equipment = {}
        for tier_str, names in ds["equipment_tiers"].items():
            if not tier_str.isdigit():
                fail(f"datasets.json[{name}]: equipment tier key {tier_str!r} is not an integer")
            for eq in names:
                if eq in seen_equipment:
                    fail(f"datasets.json[{name}]: equipment {eq!r} in tiers "
                         f"{seen_equipment[eq]} and {tier_str}")
                seen_equipment[eq] = tier_str

        bad_groups = sorted(set(ds["muscle_map"].values()) - canonical)
        if bad_groups:
            fail(f"datasets.json[{name}]: muscle_map maps to unknown groups {bad_groups} "
                 f"— canonical groups come from program.schema.json")
        overlap = sorted(set(ds["muscle_ignore"]) & set(ds["muscle_map"]))
        if overlap:
            fail(f"datasets.json[{name}]: muscles both mapped and ignored: {overlap}")

        for bench_key in ds["benchmark_gates"]:
            if benchmark_keys and bench_key not in benchmark_keys:
                fail(f"datasets.json[{name}]: benchmark_gates key {bench_key!r} is not a "
                     f"profile strength benchmark")

    # The default descriptor must fully cover the bundled fixture's vocabulary — the offline
    # stand-in for the real dataset. Unmapped real-dataset muscles are refused at run time.
    fixture = load_json(GEN_DIR / "scripts" / "generate.fixture.json")
    if fixture is None:
        fail("skills/generation/scripts/generate.fixture.json: not valid JSON")
        return
    if default in datasets:
        ds = datasets[default]
        known = set(ds["muscle_map"]) | set(ds["muscle_ignore"])
        tiered = set(seen for tier in ds["equipment_tiers"].values() for seen in tier)
        for rec in fixture:
            muscles = set(rec.get("volume", {})) | (
                {rec["primary_muscle"]} if rec.get("primary_muscle") else set())
            unmapped = sorted(muscles - known)
            if unmapped:
                fail(f"fixture record {rec.get('id')}: muscles {unmapped} not covered by "
                     f"datasets.json[{default}] muscle_map/muscle_ignore")
            if rec.get("equipment") not in tiered:
                fail(f"fixture record {rec.get('id')}: equipment {rec.get('equipment')!r} "
                     f"not in any tier of datasets.json[{default}]")


# --------------------------------------------------------------------------------------
# 9. Generation skill: generate.config.json is complete and consistent
# --------------------------------------------------------------------------------------

def check_generate_config(program_schema, rules_schema):
    config = load_json(GEN_DIR / "scripts" / "generate.config.json")
    if config is None:
        fail("skills/generation/scripts/generate.config.json: not valid JSON")
        return

    canonical = set(
        program_schema["properties"]["volume"]["oneOf"][1]["properties"]["per_muscle_weekly_sets"]["required"]
    )
    goals = set(program_schema["properties"]["program"]["properties"]["primary_goal"]["enum"])
    splits = set(program_schema["properties"]["program"]["properties"]["split"]["enum"])

    # order_rules is the single source for the ordering vocabulary: generate.py reads it,
    # rules.schema.json's enum must equal it, and the shipped default must draw from it.
    order_rules = config.get("order_rules")
    if not isinstance(order_rules, list) or not order_rules:
        fail("generate.config.json[order_rules]: missing or empty")
        order_rules = []
    if rules_schema:
        schema_rules = rules_schema["properties"]["order"]["items"]["enum"]
        if sorted(schema_rules) != sorted(order_rules):
            fail(f"rules.schema.json[order.items.enum] {sorted(schema_rules)} does not match "
                 f"generate.config.json[order_rules] {sorted(order_rules)}")

    default_rules = config.get("default_rules", {})
    for rule in default_rules.get("order", []):
        if rule not in order_rules:
            fail(f"generate.config.json[default_rules.order]: unknown rule {rule!r}")
    errs = []
    if rules_schema:
        validate_instance(dict(default_rules, **{"$schema_version": "1.0"}),
                          rules_schema, "generate.config.json[default_rules]", errs)
    for e in errs:
        fail(e)

    split_sessions = config.get("split_sessions", {})
    missing_splits = splits - set(split_sessions)
    if missing_splits:
        fail(f"generate.config.json[split_sessions]: missing entries for {sorted(missing_splits)}")
    for split, template in split_sessions.items():
        for focus in template.get("pattern", []):
            if focus not in template.get("groups", {}):
                fail(f"generate.config.json[split_sessions.{split}]: pattern focus {focus!r} "
                     f"has no groups entry")
        for focus, groups in template.get("groups", {}).items():
            unknown = sorted(set(groups) - canonical)
            if unknown:
                fail(f"generate.config.json[split_sessions.{split}.{focus}]: unknown muscle "
                     f"groups {unknown}")

    missing_goals = goals - set(config.get("reps_by_goal", {}))
    if missing_goals:
        fail(f"generate.config.json[reps_by_goal]: missing entries for {sorted(missing_goals)}")
    for goal, table in config.get("reps_by_goal", {}).items():
        for kind in ("compound", "isolation"):
            if kind not in table:
                fail(f"generate.config.json[reps_by_goal.{goal}]: missing {kind!r}")

    unknown_trailers = sorted(set(config.get("trailer_groups", [])) - canonical)
    if unknown_trailers:
        fail(f"generate.config.json[trailer_groups]: unknown muscle groups {unknown_trailers}")


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

def load_json(path):
    path = Path(path)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def main():
    check_skill_frontmatter()
    check_portable_skill_neutrality()
    check_no_rule_content()

    profile_schema = load_json(SKILL_DIR / "schema" / "profile.schema.json")
    program_schema = load_json(SKILL_DIR / "schema" / "program.schema.json")
    if profile_schema is None:
        fail("skills/onboarding/schema/profile.schema.json: not valid JSON")
    if program_schema is None:
        fail("skills/onboarding/schema/program.schema.json: not valid JSON")

    if profile_schema and program_schema:
        check_questions_yaml(profile_schema, program_schema)

        validate_file_against_schema(
            SKILL_DIR / "examples" / "profile.example.json", profile_schema, "profile example"
        )
        validate_file_against_schema(
            SKILL_DIR / "examples" / "program.example.json", program_schema, "program example"
        )

        for profile_path in sorted((ROOT / "profiles").glob("*/profile.json")):
            validate_file_against_schema(profile_path, profile_schema, str(profile_path))
        for program_path in sorted((ROOT / "profiles").glob("*/programs/*.json")):
            validate_file_against_schema(program_path, program_schema, str(program_path))

        check_volume_config_coverage(profile_schema, program_schema)

    plan_schema = load_json(GEN_DIR / "schema" / "plan.schema.json")
    rules_schema = load_json(GEN_DIR / "schema" / "rules.schema.json")
    if plan_schema is None:
        fail("skills/generation/schema/plan.schema.json: not valid JSON")
    if rules_schema is None:
        fail("skills/generation/schema/rules.schema.json: not valid JSON")

    if program_schema and plan_schema and rules_schema:
        check_datasets_descriptor(program_schema)
        check_generate_config(program_schema, rules_schema)

        validate_file_against_schema(
            GEN_DIR / "examples" / "plan.example.json", plan_schema, "plan example"
        )
        validate_file_against_schema(
            GEN_DIR / "examples" / "rules.example.json", rules_schema, "rules example"
        )

        for plan_path in sorted((ROOT / "profiles").glob("*/plans/*.json")):
            validate_file_against_schema(plan_path, plan_schema, str(plan_path))
        for rules_path in sorted((ROOT / "profiles").glob("*/rules.json")):
            validate_file_against_schema(rules_path, rules_schema, str(rules_path))

    check_script_self_test(SKILL_DIR / "scripts" / "volume.py", "volume.py")
    check_script_self_test(GEN_DIR / "scripts" / "generate.py", "generate.py")

    if FAILURES:
        for f in FAILURES:
            print(f"FAIL: {f}")
        print(f"\n{len(FAILURES)} failure(s)")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
