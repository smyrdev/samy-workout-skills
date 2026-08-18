# Workout design rules

The training-design knowledge this skill applies when it chooses exercises from a brief. `SKILL.md`
holds the flow, `rules.md` holds the rules around the flow; this file holds the coaching judgment
the flow asks for.

Everything here is guidance except where marked *Enforced*. The script enforces almost none of it —
see [What the script actually enforces](#what-the-script-actually-enforces). That is deliberate: a
number the script can compute is a number you should see, not a gate it should close behind you.
Where a rule matters and is not enforced, honour it and say when you do not. Rules that need
per-set performance history are out of scope until session logging exists.

## 1. Training intensity and rep targets

**1.1 The hypertrophy intensity band is 30–90% of 1RM.** Taken close to failure, any set in this
band produces similar growth per set. Below ~30%, performance is limited by metabolic factors,
motor unit recruitment stays incomplete, and the set does not count as effective volume.

**1.2 Intensity → rep target.** 90% → 3 · 85% → 5 · 80% → 8 · 75% → 10 · 70% → 12 · 65% → 15 ·
60% → 20.

**1.3 Default intensity by training status.** Compounds run heavier than isolation at every level.

| Status | Isolation | Compound |
|---|---|---|
| Novice | ~55–60% (15–20 reps) | ~60% (20 reps) — nothing to gain above 60% |
| Intermediate | ~65% (15 reps) | ~80% (8 reps) |
| Advanced | ~70% (12 reps) | ~85–90% (3–5 reps) |

The brief hands you a rep band per candidate (`reps_band`). Use 1.2 and 1.3 to place the target
inside it — heavier and lower for compounds, lighter and higher for isolation, both shifting up as
training status rises.

**1.4 Rep floors.** When the goal includes muscle growth, never plan below the `rep_floors` in
`generate.config.json` — below them, time under tension is insufficient: sets of 2–4 build less
muscle than sets of 8–12 despite building more 1RM strength. If heavier work is programmed anyway,
add sets to restore total tonnage. *Enforced: `rep_floors`, on the goals `rep_floor_goals` names.
A `strength` goal keeps its lower band — this rule scopes itself to growth, and so does the check.*

**1.5 Program both higher-rep and lower-rep work for each muscle group** for anyone past the
novice stage. The two run partly different growth pathways; combining them beats either alone.
Same session or different days — it does not matter.

**1.6 Match rep range to the exercise, not only to the table.** Compounds tolerate heavy, low-rep
work; isolation exercises tolerate high reps but break down technically at low reps — a lateral
raise 1RM is useless and injurious. Front squats are bad for high reps: upper back and breathing
fail before the legs. No table catches either error.

**1.7 Tendon threshold: ≥70% of 1RM.** Below that only muscle adapts. Injured or injury-prone →
bias below it now, but plan heavy work back in later: strong muscles on weak tendons is an injury
setup.

**1.8 Low intensity is *more* fatiguing than high, not less.** A 30RM set costs far more total work
and recovery than a 2RM set. High-rep work is not the easy option and must not become the default
because the loads are light.

## 2. Training volume

Weekly set targets are **not** yours to compute — `volume.py` owns them and the brief reports them.
What is yours is how they land in a session.

**2.1 The unit of volume is hard sets per muscle group per week**, tracked per muscle, never per
body region — volume is local and non-transferable. You cannot move sets from glutes to biceps; if
biceps volume was already optimal, adding to it only causes overreaching.

**2.2 Ceiling: 6–10 sets per muscle group per session.** Growth per session plateaus around 6 sets;
MPS around 10; programs exceeding ~10 per muscle per session consistently underperform. This is the
single most important constraint in the model — it is what forces frequency up. The brief reports
`sets_per_muscle` per session so you can see it directly. Nothing stops you going over; when the
split and day count leave no alternative, say so and name the program answer that would fix it,
rather than handing over a session that quietly breaks the rule it was built on.

**2.3 Strength is far less volume-dependent than size.** A strength-goal client does not need
hypertrophy volume; diminishing returns start well before those for hypertrophy.

## 3. Training frequency

**3.1 Cap frequency *per exercise* at 2×/week** when the goal is muscle growth. Per **lift**, not
per muscle: training chest six days a week is fine, putting the same bench press on all six is not
— higher frequency on one lift raises overuse risk in tendons and ligaments. Raise muscle frequency
by adding different exercises, not by repeating one.

**3.2 The split is given.** It is a saved program answer, not something this skill derives, and it
should have been an output of volume and frequency, not an input. When the per-session load it
produces has no good answer, refuse to pretend: say so and point at the program answer to change.

**3.3 Recovery is rarely the binding constraint people assume.** Trained lifters recover strength
from 4+ hard sets within 24 h and from 12 sets to failure within 48–72 h. Do not lower frequency
out of caution — only for a stated reason.

## 4. Session ordering

Sets per muscle are already spread evenly across the days that train it (`sets_per_muscle` in the
brief). Within a session, order is yours; the person's `## Order` rules travel in the brief as
`rules_applied.order` and are their standing instruction, with `trailer_groups` naming what
`trailer_groups_last` means. Beyond that: put the most strenuous session immediately before the
longest rest gap, the easiest immediately before the most important, and priority work first
within a session so it is done unfatigued. Which session is "most strenuous" and which "most
important" is a judgment about this client — nothing in the data decides it. Rest costs time:
`max_exercises_per_session` is a ceiling from the session-length answer, not a quota, and a
session filled to it at strength rests may not fit its slot — longer rests mean fewer exercises,
never a longer workout.

## 5. Exercise selection — the six principles

Applied in this order when comparing candidates for a muscle. **Scoring exercises against these is
the core judgment this skill asks of you.** The brief filters for legality — equipment, benchmarks,
the person's exclusions — and ranks by how much needed volume each candidate delivers. It does not
know any of what follows.

**5.1 The limit factor** — *the target muscle must be what fails.*

- Grip must not be the limiter. If grip fails first on deadlifts or rows, prescribe straps or
  change the lift.
- Bi-articulate conflicts kill volume: hamstrings during squats (they antagonise the quads — squats
  are a poor hamstring exercise); rectus femoris during squats (needs a leg extension);
  gastrocnemius during squats and leg presses; long head of triceps during pulldowns and chin-ups
  unless the arm stays straight; biceps during pressing.
- Unstable-surface work makes balance the limiter — keep it to core and rehab. Split squats and
  Bulgarian split squats are **not** unstable; they are excellent lifts.
- Dumbbell presses recruit the triceps about half as well as barbell presses. Swapping barbell →
  dumbbell means adding triceps isolation.

**5.2 Eccentric contractions are required.** Rule out as primary mass builders anything without a
loaded lowering phase: Olympic lifts, sled work, cycling, touch-and-go deadlifts dropped from the
top.

**5.3 Load the muscle at long lengths.**

- Full ROM is the default. Cutting ROM needs a stated reason; "I can go heavier" is not one.
- High tension in the stretched position is what matters, not maximum joint ROM: seated leg curls
  beat lying; overhead triceps extensions beat pushdowns by ~40% growth; preacher curls beat
  incline curls; squats beat partial squats.
- Long-length partials beat full ROM only where a top-end sticking point forces a lighter load
  (leg extensions, calf raises). Where the top is free (bench, squat), it is free volume; keep it.
- Both active and passive tension matter — hip thrusts match squats for glute growth by winning on
  active tension at short lengths.

**5.4 Stimulate muscle without overloading connective tissue.**

- Avoid behind-the-body pushing and pulling by default — behind-the-neck pulldowns and presses,
  dips. No unique stimulus, high shoulder cost. Substitute regular pulldowns, military press,
  push-ups.
- Prefer freedom of movement — rotating handles, rings, cables, TRX over a fixed straight bar for
  pulling. Same muscle activity, much less elbow and wrist pain.
- Slight preference for closed kinetic chain over open.
- **Pain signals override all of the above.** A machine that fits a client's structure beats a
  better free-weight lift that hurts them.

**5.5 Unilateral > bilateral, all else equal.** More muscle activity and force per limb. But *all
else equal* is often false — split squats are not one-legged back squats. Applies most cleanly to
machine and isolation work: leg curls and extensions unilateral whenever possible. Include at
least one unilateral exercise per muscle; one is normally enough. Start every unilateral set with
the weaker side and match its reps with the stronger.

**5.6 Microloadability.** The load increment must be no more than ~2.5% of the working weight.
5 lb is fine for squats and absurd for a lateral raise. Bodyweight exercises fail on absolute load
for strong clients; cable lateral raises fail on increment for light ones. Where the increment is
unusable, replace the exercise.

## 6. Counting volume per exercise

The dataset carries a per-exercise volume map on the fractional-set convention (100% / 75% / 50%,
anything below 40% rounded to zero; warm-ups never count), and the brief reports what a week
delivers against each target. Where to distrust it:

- **Known fractions:** squats give hamstrings, rectus femoris and gastrocnemius approximately
  nothing. Deadlifts give gastrocnemius and quads 50%, erector spinae 100%. Rows give biceps 50%;
  full-ROM pulldowns and chin-ups 100%; pressing 0%. Pulling gives the long head of triceps 0%
  unless the arm stays straight. Barbell presses give triceps 100%, dumbbell presses 50%. **Where
  the dataset disagrees with this list, this list is the better guide — say so rather than silently
  trusting the map.**
- **The functional units are finer than the ten muscle groups** — gastrocnemius/soleus, rectus
  femoris/vasti, three delts, three triceps heads. Neither the targets nor the dataset can express
  them; reason in compartments anyway.
- **The exact fraction depends on execution and anthropometry** — grip width, ROM, lever lengths.
  Adjust with a stated reason.

## 7. Exercise variety

**7.1 About 2 exercises per muscle group *per session*, and cap there for most muscles.** More in
one session is not necessary and quite possibly detrimental. Beginners are fine with one. Per
session, not per week: a muscle trained four times may see four or six distinct lifts across the
week, each still bound by 3.1's twice-a-week limit.

**7.2 Variety should be proportional to the number of muscle *functions*, not to boredom.** Minimum
coverage per muscle:

| Muscle | Required coverage |
|---|---|
| Pecs | One good horizontal press or fly; other functions come from vertical press and pull |
| Traps | Elevation, retraction and depression — shrug, reverse fly, pulldown |
| Delts — anterior | None. Covered by all pressing; more often overworked than under |
| Delts — lateral | A lateral raise, or a wide-grip elbows-out overhead press |
| Delts — posterior | Reverse fly or high row — most pulls lack full ROM here |
| Lats | Two pull angles: one shoulder-extension, one adduction |
| Biceps | One isolation with the elbow at the side, given other pulling exists |
| Triceps | One long-head isolation; lateral and medial come from horizontal pressing |
| Quads | A squat pattern **and** a leg extension pattern |
| Hamstrings | A knee-flexion **and** a hip-extension exercise |
| Glutes | A bent-knee **and** a straight-leg hip extension, plus abduction for the medius |
| Calves | A straight-leg **and** a bent-knee (seated) calf raise for soleus |
| Erector spinae | Squats and deadlifts usually suffice; add high-rep back extension for growth |

**7.3 Two exercises for one muscle must differ in fibre emphasis or muscle length.** Same fibres at
the same length is wasted variety.

**7.4 A fixed, complementary selection — rotated across cycles, never randomised session to
session.** Random selection measurably underperformed a fixed one; progression on a solid core
beats chasing every fibre. Flexible self-selection from a curated list is for experienced,
motivated clients only.

## 8. Recommended exercise menu

Default candidates that score well on §5. Filter by what the brief offers, then by injury and
preference. These are the book's names — the dataset may spell them differently or not carry them,
so match on the movement, not the string.

- **Pecs** — deficit or suspended push-ups; flys (cable, dumbbell, ring); dumbbell bench press flat
  or at 15°; convergent chest press machine
- **Lateral delts** — military press with elbows out and a wide grip; dumbbell overhead press;
  cable, side-lying, lean-in or butterfly lateral raises
- **Upper traps** — overhead shrugs; wide shrugs
- **Rear delts, lower and middle traps** — reverse Bayesian fly; side-lying reverse fly;
  shoulder-pulls; face-pulls; high rows
- **Lats and teres major** — lat prayers; chin-ups and pull-ups; lat pulldowns; pull-overs
- **Biceps** — Bayesian (hammer) curls; preacher or Scott curls
- **Triceps** — overhead triceps extensions; skull-overs; forward-leaning pushdowns
- **Quads** — squat patterns; reverse lunges; leg extensions; reverse Nordic curls
- **Erector spinae** — back extensions; squats; deadlifts
- **Hamstrings** — glute-ham raise; RDLs; 45° hip extension; suspended leg curls; leg curl machines
  (seated preferred); goodmornings; pull-throughs
- **Glute max** — squat patterns; lunges; leg presses; 45° hip extension; deficit hip thrusts;
  pull-throughs; RDLs; goodmornings; reverse hyperextensions; glute kickbacks
- **Glute medius** — full-stretch hip abduction
- **Calves** — calf jumps; standing calf raises; seated or bent-knee calf raises for soleus
- **Rectus abdominis** — ball crunches; reverse crunches

**Not defaults**, beyond what §5 already rules out: two-arm kickbacks; barbell curls (no tension in
the stretch, forced supination); powerlifting deadlifts as a mass builder (concentric-only, ROM set
by plate radius, grip and erectors limit first — prefer RDLs and leg extensions); rows as a *lat*
builder (half ROM, no stretch — they are a mid-trap, rear-delt and lower-trap exercise). Nothing in
the script blocks these — the brief offers them if the dataset has them. When the person agrees one
should never appear again, offer the `rules.md` exclusion snippet (`rules.md` § Personal rules).

## 9. Weak points

**Strength asymmetry up to 10% is normal.** "Underdeveloped body part" is usually a wish, not a
fact — check it against genetic potential first. If genuinely more than 10% behind, audit in this
order: is enough weekly volume allocated, are all its muscle functions trained (7.2), is it early
enough in the session order. Specialisation is only for the time-constrained; with enough training
days, train everything at its optimum and lagging parts catch up as growth slows near potential.
Correcting a measured asymmetry needs per-limb strength data this skill lacks — out of scope.

## What the script actually enforces

Two refusals: **an exercise that was not on offer** — the pool already had the equipment,
benchmarks and exclusions applied, so choosing outside it is refused by name — and **the 1.4 rep
floors**, on the growth goals only. Per-muscle weekly allocation is *reported*, not enforced: a
group under target is named in `warnings` and said out loud before anything is written.

Everything else here is yours to weigh. The script computes and reports — sets per muscle per
session, what the week delivers against each target, what each candidate is worth
(`effective_volume` in the brief — the only column whose sum matches the check table) — and
stops there. It has no opinion about whether 12 sets of chest on one day is a good idea; you do.

Where two rules conflict, say which one you followed and why. A stated override is a coaching
decision; a silent one is a bug.
