# Field guide

For hand-editing a copied sample instead of running the interview. One block per field: what to
literally type. The schemas (`schema/profile.schema.json`, `schema/program.schema.json`) are the
enforced contract; this is the plain-English version.

Start from `examples/profile.example.json` and `examples/program.example.json`, and validate with
`python scripts/validate-skills.py` from the repository root once you are done.

## `profile.json`

### `$schema_version`
Always the quoted string `"1.0"`. Do not change it by hand.

### `created_at`, `updated_at`
UTC timestamp, `"YYYY-MM-DDTHH:MM:SSZ"`. On a brand-new profile these are identical. Leave
`created_at` alone after that; bump `updated_at` whenever you edit anything else.

### `user.name`
Free text, exactly as you'd want it displayed. Accents and case are kept as typed.

### `user.slug`
Lowercase, hyphenated version of the name, and must match the directory it lives in
(`profiles/<slug>/`). Spaces and underscores become hyphens; anything outside `a-z0-9-` is
dropped. `Jean Luc` → `jean-luc`.

### `basics.date_of_birth`
`"YYYY-MM-DD"` if you know the full date, or bare `"YYYY"` if you only know the year. Always
quoted. Never a decade, never padded to January 1st. This field exists instead of an age field on
purpose — a stored age goes stale, a birth date does not.

### `basics.bodyfat_bracket`
One of these nine, as a quoted string:
`"3-4"` `"5-7"` `"8-12"` `"13-17"` `"18-23"` `"24-29"` `"30-34"` `"35-39"` `"40+"`
Not a number, not `"15%"`. Guess the closest bracket — nobody knows this to the percent.

### `experience.lifting`
One of `"none"`, `"beginner"`, `"intermediate"`, `"advanced"`. Beginner is under 1 year,
intermediate 1-4 years, advanced 4+ years.

### `gym.type`
One of `"everything_gym"`, `"commercial_gym"`, `"warehouse_gym"`, `"local_gym"`, `"garage_gym"`.
This is the entire equipment model — there is no item-level checklist to fill in alongside it.

### `strength_benchmarks.*`
Seven keys, every one of them `true` or `false`, none omitted:
`pullups_5`, `pullups_10`, `dips_10`, `pushups_15`, `bench_press_10`, `incline_press_10`,
`overhead_press_10`. If `pullups_10` is `true`, `pullups_5` should be too — nobody clears 10 without
clearing 5.

### Optional fields nothing reads
The schema still accepts `units`, `basics.sex`, `basics.height`, `basics.weight`,
`experience.cardio` and `gym.notes`, and a profile written before they were dropped keeps them.
The interview no longer asks, and neither the volume model nor the generator reads any of them —
leave them out unless you want the record for yourself.

## `programs/program-YYYY-MM-DD.json`

### `$schema_version`, `created_at`
Same rules as in `profile.json`. `created_at` here is when this particular program file was
written, not when the profile was created.

### `profile_slug`
Must match the `user.slug` of the profile this program belongs to, and the directory it sits
under (`profiles/<slug>/programs/`).

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

### `program.style`
One of `"balanced"`, `"high_volume"`, `"high_intensity"` — which school of training volume the
plan follows. `balanced` is the no-op default and what to write if you have no opinion.
`high_volume` raises the per-muscle target by about a third and stops sets short of failure;
`high_intensity` cuts it to roughly 60% and takes them to failure. It is a program field, not a
profile one, so changing it means a new dated program file and a `volume.py` re-run.

A program file written before this field existed still computes — `volume.py` falls back to
`balanced` — but the schema requires it on anything written now.

### `program.deload`
`true` or `false` — whether the program ends with a lighter recovery week.

### `volume`
Leave this out, or set it to `null`. It's the computed weekly per-muscle set allocation, filled by
`scripts/volume.py`, not something to hand-write. Run:

```
python skills/onboarding/scripts/volume.py --profile profiles/<slug>/profile.json \
  --write profiles/<slug>/programs/program-<date>.json
```

If you do want to hand-inspect the shape, `examples/program.example.json` has a filled-in one —
copy its keys, never its numbers.
