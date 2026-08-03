# samy-workout-skills

A portable onboarding skill that interviews you once about your training situation and saves it as a
profile, so a workout generator can read it instead of asking you twenty questions every time.

It is a **skill**, not an app — a markdown file of instructions any capable LLM agent can follow.
There is no server, no account, and no install. The repository is the whole thing.

> Not medical advice. Everything here is self-reported and unverified — if you have an injury or a
> medical condition, talk to someone qualified before training around it.

## Quickstart

**In Claude Code**, from the repository root:

```
/onboard
```

**With any other agent**, point it at the skill file and let it run:

> Read `skills/onboarding/SKILL.md` and follow it.

Either way you answer about twenty questions in five or six rounds, see a summary before anything is
saved, and end up with `profiles/<your-name>/profile.json`.

## What it asks

Three groups:

- **Basics** — name, sex, date of birth, height, weight, bodyfat bracket, lifting and cardio
  experience
- **Gym** — where you train, as one of five gym types
- **Program** — goal, days per week, session length, split, deload, seven strength benchmarks, and a
  name and emoji for your program

The program answers are saved even though they change from cycle to cycle. They are defaults, not
commitments: the generator shows them back and lets you change any of them for one cycle without
redoing the interview.

Nothing is written until you have seen a summary of every answer and the exact path it is going to.

## Several people, one repository

Each person gets a directory:

```
profiles/
├── samy/
│   └── profile.json
└── sara/
    └── profile.json
```

Run `/onboard sara` to go straight to a profile. Run `/onboard` with no name and it asks who you
are — it never picks a default, because writing to someone else's profile fails silently.

To change something later:

```
/onboard --update
/onboard sara --update
```

That asks only about the fields you name, and leaves everything else byte-for-byte identical.

## Where your data lives

`profiles/` is gitignored in full. Your body stats are never committed, even by accident. The schema
lives at [`skills/onboarding/profile.example.json`](skills/onboarding/profile.example.json), with
every field documented in [`docs/schema.md`](docs/schema.md).

Your profile is a plain JSON file you can read, edit, back up, or delete. Nothing else touches it.

## Honest limitations

- **Gym type is a coarse proxy for equipment.** Five tiers, no item-level checklist. The original
  spec left that list unwritten and it is deliberately deferred until there is an exercise database
  to validate it against — so "commercial gym" assumes a machine selection you may not actually
  have.
- **The seven strength benchmarks are self-reported.** Nothing verifies them.
- **Bodyfat is a self-estimated bracket**, not a measurement, and it is stored as a range for
  exactly that reason.
- **Nothing is generated yet.** This repository records a profile. The workout generator is
  specified — the contract is at the end of
  [`skills/onboarding/SKILL.md`](skills/onboarding/SKILL.md) — but not built.

## Roadmap

- Workout generation reading these profiles
- Item-level equipment selection, seeded by gym type
- Session logging and progression under `profiles/<slug>/`

## Layout

```
skills/onboarding/SKILL.md          the skill — vendor-neutral, the source of truth
skills/onboarding/profile.example.json   the schema, by example
.claude/skills/onboard/SKILL.md     thin wrapper so /onboard works in Claude Code
docs/schema.md                      every field, enum, and derivation explained
docs/onboarding.md                  the original hand-written spec, kept as-is
profiles/                           your data, gitignored
```

## License

MIT.
