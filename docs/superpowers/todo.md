# TODOs

## Research first

- [ ] Science research on goal → selection: what must a strength / hypertrophy / both block
      actually contain? (anchor lifts per goal, compound-vs-isolation tilt, rep-range
      interactions). Decides bias-only vs anchor-guarantee vs both.
- [ ] Decide the scoring-function shape: one `marginal_score` with four config-driven terms
      (staple bonus, goal-pattern bonus, equipment-class preference, overshoot penalty)
      replacing `name_length_penalty` — or separate mechanisms.

## Process

- [ ] Merge the evals harness PR (branch `worktree-evals-brainstorm`) — measurement
      instrument goes to main before any tuning.
- [ ] Resume the brainstorm → finish design doc → writing-plans → generation-tuning PR.
      Verify each change with `bash evals/run-evals.sh --skip-judge` plan diffs before
      spending judge tokens.

## Generation-tuning PR (design agreed so far)

- [ ] Descriptor `staples` curation: per volume_profile (~36), 1–3 canonical exercise
      names; config holds the bonus number. Kills the backwards `name_length_penalty`
      heuristic. (finding 1)
- [ ] Descriptor `experience_gates` (hard gate, mirrors `benchmark_gates`): name patterns
      → minimum `experience.lifting` level; generate.py filters below it. (finding 4)
- [ ] Descriptor equipment → canonical equipment-class map + config per-class preference,
      so full gyms prefer free weights/machines over bands/bodyweight. (finding 3)
- [ ] Goal steering via descriptor volume_profile → canonical movement-pattern map +
      per-goal config numbers — exact mechanism pending the research above. (finding 2)
- [ ] Overshoot control: charge passenger volume into already-full groups in
      `marginal_score`; make `repair_shortfalls` overshoot-aware. (finding 5)
- [ ] Weekly dedup: per-week volume_profile cap and/or rekey `repeat_penalty` to
      volume_profile instead of exercise id. (finding 6)

## Separate projects (not this PR)

- [ ] Upstream dataset fixes in smyrdev/exercises-dataset: recategorize squat jerk (and
      audit other jerks/snatches/swings) to `olympic`; consider a future
      popularity/difficulty field the descriptor could point at.
- [ ] agentskills.io layout restructure for both skills (SKILL.md / scripts/ /
      references/ / assets/) — mechanical PR, after the tuning PR. Touches `.claude`
      wrappers, `validate-skills.py`, tests/skills/.
- [ ] Persona-narrative gap (injuries only the judge sees) — onboarding-side
      `interview_answers` hook design (explicitly out of scope for the tuning session).
