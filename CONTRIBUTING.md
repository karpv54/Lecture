# Contributing

Use Python 3.11+, install `apps/gradio/requirements.txt` in a virtual environment, and run the offline checks in `docs/validation.md`. Never use real provider credentials in tests or commit learner records.

Keep one learner microphone button and no typed learner chat. Preserve attempt-before-answer behavior, the separation between practice and observed mastery, and the rule that a transcript is not pronunciation evidence. Render only controlled, escaped teaching content. A meaning picture belongs to one confirmed current word attempt.

Update tests when changing state transitions, audio cancellation, provider contracts or scoring. Treat `agents/*/instructions.md` and the original MTHDS as preserved source material; application-specific changes belong in the addenda and adapter. Review and audition linguistic content before extending it.

Use `scripts/package.py` for source archives. It excludes private state independently of Git. No publishing or paid inference is part of the default development workflow.
