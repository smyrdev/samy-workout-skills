# Field guide

What to literally type when hand-editing a copied sample instead of running the interview. The
schemas in `skills/onboarding/assets/schema/` are the enforced contract; this is the short version. Start from
`skills/onboarding/assets/examples/profile.example.json` and `skills/onboarding/assets/examples/program.example.json`, then run
`python scripts/validate-skills.py` from the repository root.

## `profile.json`

| Field | Type in | Note |
|---|---|---|
| `$schema_version` | `"1.0"` | never change by hand |
| `created_at`, `updated_at` | `"YYYY-MM-DDTHH:MM:SSZ"` UTC | identical on a new profile; bump only `updated_at` on edits |
| `user.name` | free text | a display label — nothing on disk is named after it |
| `units` | `"metric"` \| `"imperial"` | decides `height`/`weight` units below; changing it does **not** convert the numbers (1 in = 2.54 cm, 1 lb = 0.45359237 kg — do it yourself) |
| `basics.sex` | `"male"` \| `"female"` | |
| `basics.date_of_birth` | `"YYYY-MM-DD"` or `"YYYY"` | always quoted; never a decade, never padded to Jan 1. Stored instead of an age because a stored age goes stale |
| `basics.height` | `{ "value": <number>, "unit": "cm" \| "in" }` | exact number, no ranges |
| `basics.weight` | `{ "value": <number>, "unit": "kg" \| "lb" }` | exact number, no ranges |
| `basics.bodyfat_bracket` | one of `"3-4" "5-7" "8-12" "13-17" "18-23" "24-29" "30-34" "35-39" "40+"` | a bracket, not a number — guess the closest |
| `experience.lifting`, `experience.cardio` | `"none"` \| `"beginner"` \| `"intermediate"` \| `"advanced"` | beginner < 1 yr, intermediate 1-4, advanced 4+ |
| `gym.type` | `"everything_gym"` \| `"commercial_gym"` \| `"warehouse_gym"` \| `"local_gym"` \| `"garage_gym"` | the entire equipment model — no item checklist |
| `gym.notes` | `null` or a short string | never a list or object |
| `strength_benchmarks.*` | seven booleans: `pullups_5` `pullups_10` `dips_10` `pushups_15` `bench_press_10` `incline_press_10` `overhead_press_10` | none omitted; `pullups_10: true` implies `pullups_5: true` |

## `programs/program-YYYY-MM-DD.json`

| Field | Type in | Note |
|---|---|---|
| `$schema_version` | `"1.0"` | |
| `created_at` | UTC timestamp | when this program file was written |
| `program.name` | free text, 1-60 chars | |
| `program.emoji` | one emoji, as a string | |
| `program.primary_goal` | `"hypertrophy"` \| `"strength"` \| `"both"` | |
| `program.days_per_week` | integer 3-7 | not a string |
| `program.session_minutes` | `"up_to_20"` \| `"20-40"` \| `"40-60"` \| `"60-90"` \| `"90-120"` \| `"over_120"` | a range string, not minutes |
| `program.split` | `"full_body"` \| `"upper_lower"` | |
| `program.deload` | `true` \| `false` | ends with a lighter recovery week |
| `volume` | omit, or `null` | computed, never hand-written — see below |

Fill `volume` with the script, not by hand:

```
python skills/onboarding/scripts/volume.py --profile profile/profile.json \
  --write profile/programs/program-<date>.json
```

`skills/onboarding/assets/examples/program.example.json` shows a filled-in one — copy its keys, never its numbers.
