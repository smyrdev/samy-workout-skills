# Field guide

For hand-editing a copied sample instead of running the interview. One block per field: what to
literally type. The schemas (`schema/profile.schema.json`, `schema/program.schema.json`) are the
enforced contract; this is the plain-English version.

Start from `examples/profile.example.json` and `examples/program.example.json`, and validate with
`python scripts/validate-skills.py` from the repository root once you are done.

## `profile.json`

### `$schema_version`
Always the quoted string `"2.0"`. Do not change it by hand.

### `created_at`, `updated_at`
UTC timestamp, `"YYYY-MM-DDTHH:MM:SSZ"`. On a brand-new profile these are identical. Leave
`created_at` alone after that; bump `updated_at` whenever you edit anything else.

### `user.name`
Free text, exactly as you'd want it displayed. Accents and case are kept as typed. It is a label
only — no file or directory is named after it, so changing it is safe.

### `units`
`"metric"` or `"imperial"`. Controls what `unit` is expected inside `height` and `weight` below —
metric means `cm`/`kg`, imperial means `in`/`lb`. Changing this after the fact means converting the
numbers yourself (1 in = 2.54 cm, 1 lb = 0.45359237 kg) — the field is not auto-converted just by
editing the label.

### `basics.sex`
One of `"male"` or `"female"`.

### `basics.date_of_birth`
`"YYYY-MM-DD"` if you know the full date, or bare `"YYYY"` if you only know the year. Always
quoted. Never a decade, never padded to January 1st. This field exists instead of an age field on
purpose — a stored age goes stale, a birth date does not.

### `basics.height`, `basics.weight`
`{ "value": <number>, "unit": "cm" | "in" }` and `{ "value": <number>, "unit": "kg" | "lb" }`.
Always an exact number — no ranges, no strings like `"170-180"`.

### `basics.bodyfat_bracket`
One of these nine, as a quoted string:
`"3-4"` `"5-7"` `"8-12"` `"13-17"` `"18-23"` `"24-29"` `"30-34"` `"35-39"` `"40+"`
Not a number, not `"15%"`. Guess the closest bracket — nobody knows this to the percent.

### `experience.lifting`, `experience.cardio`
One of `"none"`, `"beginner"`, `"intermediate"`, `"advanced"` for each. Beginner is under 1 year,
intermediate 1-4 years, advanced 4+ years.

### `gym.type`
One of `"everything_gym"`, `"commercial_gym"`, `"warehouse_gym"`, `"local_gym"`, `"garage_gym"`.
This is the entire equipment model — there is no item-level checklist to fill in alongside it.

### `gym.notes`
`null`, or a short free-text string for something worth knowing that the gym type doesn't capture
("also has a cable machine"). Never a list or object.

### `strength_benchmarks.*`
Seven keys, every one of them `true` or `false`, none omitted:
`pullups_5`, `pullups_10`, `dips_10`, `pushups_15`, `bench_press_10`, `incline_press_10`,
`overhead_press_10`. If `pullups_10` is `true`, `pullups_5` should be too — nobody clears 10 without
clearing 5.

## `programs/program-YYYY-MM-DD.json`

### `$schema_version`, `created_at`
Same rules as in `profile.json`. `created_at` here is when this particular program file was
written, not when the profile was created.

### `program.name`
Free text, 1-60 characters. Whatever you want to call this training block.

### `program.emoji`
A single emoji, as a string.

### `program.primary_goal`
One of `"hypertrophy"`, `"strength"`, `"both"`.

### `program.days_per_week`
An integer 3-7. Not a string.

### `program.session_minutes`
One of these six range strings, quoted: `"up_to_20"`, `"20-40"`, `"40-60"`, `"60-90"`,
`"90-120"`, `"over_120"`. Not a number of minutes — the person answered a range, so the field
stores a range.

### `program.split`
One of `"full_body"` or `"upper_lower"`.

### `program.deload`
`true` or `false` — whether the program ends with a lighter recovery week.

### `volume`
Leave this out, or set it to `null`. It's the computed weekly per-muscle set allocation, filled by
`scripts/volume.py`, not something to hand-write. Run:

```
python skills/onboarding/scripts/volume.py --profile profile/profile.json \
  --write profile/programs/program-<date>.json
```

If you do want to hand-inspect the shape, `examples/program.example.json` has a filled-in one —
copy its keys, never its numbers.
