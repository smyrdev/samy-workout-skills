---
name: onboarding
description: >
  Use when someone is setting up a training profile for the first time, says they are new here, or
  asks to change their body stats, bodyfat, lifting or cardio experience, gym type, training goal,
  days per week, session length, split preference, deload preference, strength benchmarks, or
  program name. Also use when another skill reports that a training profile is missing.
---

# Training profile onboarding

Interview one person and save their answers to `profiles/<slug>/profile.json`. That file is the
input to workout generation, so a person answers these questions once rather than every time they
want a program.

Written to be run by any capable LLM agent. See [Environment notes](#environment-notes) at the end
for the two capabilities it assumes.

## What this collects

Three groups, in this order:

1. **Basics** — name, sex, date of birth, height, weight, bodyfat, lifting and cardio experience
2. **Gym** — where they train
3. **Program** — goal, days per week, session length, split, deload, strength benchmarks, program
   name and emoji

The Program answers are stored even though they change from cycle to cycle. They are **defaults,
not commitments**: the workout-generation skill shows them back and lets any of them be changed for
a single cycle without re-running this interview. A returning person should click "same as last
time", not answer twenty questions again.

Gym type is the **entire equipment model in v1**. There is no item-level equipment checklist — do
not invent one, and do not ask which machines they have.

## Choosing the profile

Several people can share this repo, one directory each. Resolve which profile is in play **before
asking anything else**, and never guess:

- **A name was supplied** (e.g. the person ran the skill with `sara`, or said "update Sara's
  profile"). Slugify it and look for `profiles/<slug>/profile.json`. Not found → say so and offer to
  create it. Found → check the `user.name` inside before using it. If it is the same person, that is
  the profile. If it is somebody else (`sara` holding "Sarah"), do not open it and do not overwrite
  it — say whose profile that slug holds and ask whether they meant that person or a new one.
- **No name, no profiles exist** → this is a new profile. The interview asks for the name.
- **No name, exactly one profile exists** → confirm rather than assume: "This is Samy's profile —
  continuing as Samy?" Cheap to ask, and it stops a housemate silently overwriting someone.
- **No name, several profiles exist** → list them and ask who this is, with an option for someone
  new.

There is no default profile and no last-used memory, on purpose. Writing to the wrong person's
profile is the main hazard of supporting more than one, and it fails silently.

**Slug rules:** lowercase, trim, spaces and underscores to hyphens, drop anything outside `a-z0-9-`,
collapse repeated hyphens, strip leading and trailing hyphens. `Anna-Maria` → `anna-maria`,
`Jean Luc` → `jean-luc`. If the result is empty, ask for something usable instead of inventing one.

**When creating a profile**, if the slug is already taken by a different person, suffix it —
`sam-2`, then `sam-3` if that is taken too — and say so out loud. Never merge two people into one
file. Checking this means reading the existing `profile.json` to compare `user.name`; reading
another profile is fine, writing to one is not.

## Flow

### 1. Resolve the profile

Follow [Choosing the profile](#choosing-the-profile). If a profile already exists and this is not an
update, stop and ask what they want: summarise it in two lines (program name and emoji, goal, days
per week) and offer **change a few fields** (go to [Updating](#updating)) or **start over** (full
re-interview, overwriting). Proceed only on an explicit answer.

Every question below lists the **options to offer** and the **value to store**. Store the value in
the right-hand column, never the display label.

**"Plus an escape" means the person can always answer in their own words** instead of picking an
offered option. Offered options are a shortcut for the common cases, never a limit on valid answers
— if someone trains 7 days a week or is 150 cm tall, that answer is accepted even though it is not
on the list. Agents with a structured question tool put this behind that tool's free-text option;
agents asking in plain text get it for free, and should mention the uncommon choices rather than
hiding them.

### 2. Basics, part one — up to 4 questions

| Question | Options offered | Stored as |
|---|---|---|
| What should I call you? | Free text | `user.name` verbatim, plus `user.slug` |
| Sex | Male · Female | `basics.sex`: `male` \| `female` |
| Which year were you born? | 1980s · 1990s · 2000s, plus an escape for an exact date | `basics.date_of_birth` |
| Units | Metric (cm / kg) · Imperial (in / lb) | `units`: `metric` \| `imperial` |

**Skip the name question if step 1 already established who this is** — do not ask twice.

Ask units here, before any measurement, so the next batch can be phrased in the person's own units.

**A decade is not an answer.** The decade buckets only narrow things down — if someone picks one,
follow up for the year ("1990s — which year?"). Store the string `"YYYY-MM-DD"` when they give a
full date, or the string `"YYYY"` when they give only a year — always quoted, never a bare number,
and never padded out to a January 1st they did not say. Never store a decade and never pick a year
for them.

### 3. Basics, part two — 4 questions

Phrase height and weight in the unit chosen above. The tables show metric; for imperial, offer
height as 5'3"–5'7" · 5'7"–5'11" · 5'11"–6'3" · 6'3"+ and weight as 130–155 lb · 155–190 lb ·
190–220 lb · 220 lb+.

| Question | Options offered | Stored as |
|---|---|---|
| Height | 160–170 cm · 170–180 cm · 180–190 cm · 190 cm+, plus an escape for an exact number | `basics.height`: `{ "value": <number>, "unit": "cm" \| "in" }` |
| Weight | 60–70 kg · 70–85 kg · 85–100 kg · 100 kg+, plus an escape for an exact number | `basics.weight`: `{ "value": <number>, "unit": "kg" \| "lb" }` |
| Bodyfat | Lean (8–12%) → `8-12` · Average (13–17%) → `13-17` · Above average (18–23%) → `18-23` · Higher (24%+) → ask which, plus an escape to the full bracket list | `basics.bodyfat_bracket`: one bracket string |
| Lifting experience | None · Beginner (under 1 year) · Intermediate (1–4 years) · Advanced (4+ years) | `experience.lifting`: `none` \| `beginner` \| `intermediate` \| `advanced` |

**Height and weight must end up as exact numbers.** The buckets exist only to save typing for agents
whose question tool makes clicking cheaper than typing — **if you are asking in plain text, skip the
buckets and ask for the number directly.** When someone does pick a bucket, follow up — "180–190 cm
— what's your actual height?" — and store the number. Never store a range in `height.value` or
`weight.value`.

The buckets deliberately do not span the full accepted range (a 150 cm or 45 kg answer is perfectly
valid) — that is what the escape is for.

Bodyfat is the opposite: it is **stored as a bracket**, because nobody knows their bodyfat to the
percent. The nine valid strings are exactly `3-4`, `5-7`, `8-12`, `13-17`, `18-23`, `24-29`,
`30-34`, `35-39`, `40+` — plain hyphens, no percent sign, no label text. The four offered options
cover the common cases and "Higher (24%+)" spans four brackets, so ask which one. The escape reaches
the leaner brackets. Store one of the nine strings, never a number and never a display label.

### 4. Cardio, gym and program shape — 4 questions

Cardio experience rides along here rather than with lifting experience purely to keep the batches at
four questions each. Ask in this order; the grouping in [What this collects](#what-this-collects)
describes the profile, not the question sequence.

| Question | Options offered | Stored as |
|---|---|---|
| Cardio experience | None · Beginner (under 1 year) · Intermediate (1–4 years) · Advanced (4+ years) | `experience.cardio`: `none` \| `beginner` \| `intermediate` \| `advanced` |
| Where do you work out? | Commercial gym · Local gym · Garage gym · Warehouse gym, with "Everything gym" behind the escape | `gym.type`: `commercial_gym` \| `local_gym` \| `garage_gym` \| `warehouse_gym` \| `everything_gym` |
| Primary goal | Muscle size (hypertrophy) · Strength · Both | `program.primary_goal`: `hypertrophy` \| `strength` \| `both` |
| Days per week | 3 · 4 · 5 · 6, with 7 behind the escape | `program.days_per_week`: integer 3–7 |

### 5. Program preferences — 3 questions

| Question | Options offered | Stored as |
|---|---|---|
| Time per session | Up to 40 min → ask which · 40–60 min → `40-60` · 60–90 min → `60-90` · 90+ min → ask which, with the full list behind the escape | `program.session_minutes`: one range string |
| Split preference | Full body (recommended) · Upper/Lower | `program.split`: `full_body` \| `upper_lower` |
| Deload week | Yes — end the program with a lighter week (recommended) · No | `program.deload`: boolean |

`session_minutes` is stored as a range string, not a number — the person answered a range. The six
valid strings are exactly `up_to_20`, `20-40`, `40-60`, `60-90`, `90-120`, `over_120`. Two of the
offered options are deliberately wide: "Up to 40 min" splits into `up_to_20` or `20-40`, and
"90+ min" splits into `90-120` or `over_120`. Ask which when someone picks either.

### 6. Strength benchmarks — one multi-select question

> "Which of these can you do right now? Select all that apply."

| Option offered | Stored as |
|---|---|
| 5+ strict, unassisted pull-ups or chin-ups | `strength_benchmarks.pullups_5` |
| 10+ strict, unassisted pull-ups or chin-ups | `strength_benchmarks.pullups_10` |
| 10+ bodyweight dips | `strength_benchmarks.dips_10` |
| 15+ strict bodyweight push-ups | `strength_benchmarks.pushups_15` |
| Barbell bench press for 10 reps | `strength_benchmarks.bench_press_10` |
| Barbell incline press for 10 reps | `strength_benchmarks.incline_press_10` |
| Barbell overhead press for 10 reps | `strength_benchmarks.overhead_press_10` |

All seven keys are always written, `true` for selected and `false` for the rest. None is ever
omitted.

**The two pull-up options are nested: 10+ implies 5+.** If someone selects 10+ without 5+, that is
not a contradiction to reject — set both to `true` and move on.

**An empty selection means "none of these", which is a valid answer, not a skip.** Confirm it in
plain text — "So none of those yet — got it" — before storing seven `false` values.

### 7. Program identity — plain text

Ask both in one message: what they want to call this program, and an emoji for it. These are free
text with no sensible option set — offering three invented program names to reject would waste
their time.

If they do not care, offer a default derived from their answers ("Full Body Hypertrophy" / 💪) and
confirm it before using it.

### 8. Echo the consequences — before writing anything

Show a compact summary: name, age, height and weight in their units, bodyfat bracket, gym type,
goal, days × session length, split, deload, and how many of the seven benchmarks they cleared.
**Name the exact path about to be written** (`profiles/samy/profile.json`). Age is computed from
their date of birth for display only and is not stored; if they gave only a birth year, show it as
approximate ("about 32").

Then say in plain English what follows from the notable answers:

- Gym type — "Garage gym, so the plan will stick to barbell, dumbbell and bodyweight work."
- Split and days — "Full body five days a week is a lot of full-body sessions; upper/lower may fit
  better. Keep full body?"
- Benchmarks — "You cleared 2 of 7, so the plan will start you on assisted or machine versions of
  the pressing and pulling patterns."

Let them veto anything before a single byte is written. If they change an answer, update the summary
and confirm again. **If they change units at this point, convert the measurements** using the
factors in [Updating](#updating) — do not relabel the numbers.

If they abandon the interview here or earlier, write nothing at all. A partial profile is worse than
no profile.

### 9. Save

Create `profiles/<slug>/` if it does not exist — including the `profiles/` parent — and write
`profile.json` there, in exactly this structure and key order. **The values below are illustrative;
only the keys, nesting and order are prescriptive:**

```json
{
  "$schema_version": "1.0",
  "created_at": "2026-08-03T14:22:00Z",
  "updated_at": "2026-08-03T14:22:00Z",
  "user": { "name": "Samy", "slug": "samy" },
  "units": "metric",
  "basics": {
    "sex": "male",
    "date_of_birth": "1994-06-15",
    "height": { "value": 178, "unit": "cm" },
    "weight": { "value": 80, "unit": "kg" },
    "bodyfat_bracket": "13-17"
  },
  "experience": { "lifting": "intermediate", "cardio": "beginner" },
  "gym": { "type": "commercial_gym", "notes": null },
  "strength_benchmarks": {
    "pullups_5": true,
    "pullups_10": false,
    "dips_10": true,
    "pushups_15": true,
    "bench_press_10": true,
    "incline_press_10": true,
    "overhead_press_10": false
  },
  "program": {
    "name": "Summer Build",
    "emoji": "💪",
    "primary_goal": "hypertrophy",
    "days_per_week": 4,
    "session_minutes": "60-90",
    "split": "full_body",
    "deload": true
  },
  "derived": {
    "note": "Computed at read time by consuming skills. Never authoritative, never hand-edited.",
    "age": null,
    "bodyfat_midpoint": null,
    "equipment_tier": null,
    "benchmarks_cleared": null
  },
  "history": []
}
```

Notes on the fields that are not direct answers:

- `$schema_version` is `1.0`. `created_at` and `updated_at` are the current UTC time as
  `YYYY-MM-DDTHH:MM:SSZ`; on a first write they are identical.
- `units` is a single string for the whole profile. The `unit` inside `height` and `weight` always
  agrees with it — `metric` means `cm` and `kg`, `imperial` means `in` and `lb`.
- `gym.notes` is `null` unless they volunteered something extra ("I also have a cable machine"), in
  which case it is that free text. It never becomes a structured list in v1.
- `derived` is written **exactly as shown** — the `note` string verbatim, the other four keys `null`.
  It is documentation naming the values that consuming skills compute at read time, not a cache for
  this skill to fill in.
- `history` starts as an empty array and belongs to the generation skill.

This layout is also kept as a standalone file at [`profile.example.json`](profile.example.json). If
the two ever disagree, that file wins — but everything needed to write a valid profile is above, so
being unable to read it never blocks this skill.

Then tell them where it went, and that the workout-generation skill will use the program answers as
defaults they can change per cycle without redoing this.

## Updating

Resolve the profile first, exactly as above. Then ask only about what they named — "change my weight
to 82" needs no questions at all, just a confirmation. If the request is vague ("update my
profile"), offer a group picker — Basics · Gym · Program · Benchmarks — and re-run only that batch.
This is never a full re-interview.

Parse the existing file, change only what was asked for, and write the whole thing back in the
structure and key order shown in step 9 — do not patch the text in place. Every field you did not
change keeps its exact value, including `created_at`. Bump `updated_at`. Three rules for fields that
interact:

- **Changing `units` converts the measurements, it does not relabel them.** 1 in = 2.54 cm,
  1 lb = 0.45359237 kg, rounded to one decimal. 178 cm becomes 70.1 in, never 178 in.
- **Changing `date_of_birth` touches nothing else** — age is derived at read time, never stored.
- **Changing the name** re-slugs the directory. **Move the whole directory**, not just
  `profile.json` — it may already contain generated plans and logs, and copying one file out before
  deleting the rest destroys them. Rename `profiles/<old-slug>/` to `profiles/<new-slug>/`, then
  update `user.name` and `user.slug` inside the file. If the directory cannot be moved, leave it
  untouched and say plainly that the rename did not happen — never delete the old one first.

## Validation

- **Plausible ranges.** Height 120–230 cm (47–91 in), weight 35–250 kg (77–550 lb), birth year
  1920–2015, days per week 3–7. Check against whichever unit they answered in; the bounds are
  generous enough that rounding at the edges does not matter. Anything outside these is a typo until
  confirmed — ask again. Never silently clamp a value and never silently store an implausible one.
- **Never invent an answer.** If someone skips a question or answers ambiguously, ask again. Do not
  fill in a reasonable-sounding height, a default gym type, or a benchmark result. Exactly two
  auto-fills are permitted: `pullups_5` from `pullups_10`, and a program name or emoji default that
  was explicitly offered and accepted.
- **Bodyfat must be one of the nine bracket strings.** Not a number, not an invented range.
- **Echoing before writing is mandatory**, including the target path. No first-pass write without
  the person seeing the summary.
- **Write only to `profiles/<slug>/profile.json`.** Never to `docs/`, never to `skills/`, never to
  another person's directory. Never modify `profile.example.json`; it is the shipped schema.
- **Never clear `history`.** It belongs to the generation skill.

## What the generation skill reads

A future workout-generation skill consumes this profile. It will:

- **Resolve a profile the same way** this skill does — same name argument, same ask-when-ambiguous
  rule, same slug derivation.
- **Read without asking:** `user.name`, `basics.*` (deriving age from `date_of_birth`),
  `experience.*`, `gym.type`, `strength_benchmarks.*`, `program.name`, `program.emoji`, `units`.
- **Read and re-confirm in one pre-filled batch:** `program.primary_goal`,
  `program.days_per_week`, `program.session_minutes`, `program.split`, `program.deload`. Keeping all
  of them is one click.
- **Never write to `profile.json`.** Per-cycle overrides belong in the generated plan, not back in
  the profile. If someone wants a change made permanent, it points them at this skill's update path.
  It may write under `profiles/<slug>/plans/` and append to `history`.
- **Fail loudly when no profile exists**, telling the person to run onboarding first rather than
  interviewing them itself.

Everything needed to run this interview is in this file. [`docs/schema.md`](../../docs/schema.md)
adds background for whoever builds that generation skill — the bodyfat midpoint map, the
gym-type-to-equipment-tier map, and the session-length-to-exercise-cap mapping — and is not needed
here.

## Environment notes

This skill needs three capabilities:

1. **Read and write a JSON file**, and create a directory.
2. **Ask the person questions.** Steps 2–6 are written for an agent that can present multiple-choice
   questions — batch them as shown, up to four questions at a time, with a free-text escape on every
   question so nobody is trapped by the offered options. An agent without a structured question tool
   asks the same questions in the same order as plain text, which works identically; the batching is
   a convenience, not a requirement.
3. **Delete or move a directory** — only for renaming a profile. Without it, everything else still
   works; say plainly that the old directory is stale instead of silently leaving two live copies.

**Paths.** All paths are relative to the repository root — the directory containing `skills/`,
`docs/` and `profiles/`. This file lives at `skills/onboarding/SKILL.md`, so the root is two levels
up from it.

Nothing here depends on a particular agent, vendor, or operating system.
