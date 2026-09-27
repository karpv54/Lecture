# Source material

## Original agent contexts

`dust-literacy-setup.md` is a copy of the document supplied from the user's Downloads folder. Its five `text` blocks were extracted in order into:

1. `agents/academic/instructions.md`
2. `agents/support/instructions.md`
3. `agents/visuals/instructions.md`
4. `agents/voice/instructions.md`
5. `agents/coordinator/instructions.md`

The instruction wording is preserved. This document is a historical reference, including its original statements about what was accessible during its preparation.

## Pipelex source

`pipelex/methods/tuteur_francais/main.mthds` comes from `tuteur-francais/methods/tuteur_francais/main.mthds` in the local Codex **X-AI hackaton** project, chat **pipelex**. The complete method is copied unchanged. The source project used Pipelex 0.66.0.

No activity catalogue or temperament-file implementation was present in that method folder. The copy does not alter or deploy the original method.

## Gradio source

`apps/gradio/app.py` comes from the earlier Desktop project `a journey/X-AI hackaton/app.py`. It already contained Dust API conversation handling, Gradium speech output, and Gradio controls.

The first repository copy added an explicit `.env` path and configurable voice. The app has since been reworked into a single-button voice interface, with Dust handling in `dust_client.py` and Gradium turn handling in `voice_session.py`. The original Desktop app remains untouched.

No private `.env`, API key, virtual environment, learner record, or generated recording was copied into this repository.
