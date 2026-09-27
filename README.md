# Lecture · On apprend, ensemble.

A French reading tutor for adults, prepared for **Rise of Agents X**. The learner presses one microphone button and speaks. Letters, syllables and words appear as large clear image tiles; listening resumes after each spoken response.

**Start with [START_HERE.md](START_HERE.md).** On Windows, `SETUP.cmd` prepares the environment and provider configuration; `START.cmd` opens the local server. The screen can be viewed before credentials are available.

## Included

- A Gradio interface with one start/stop control, responsive layout, microphone permission handling and no typed learner chat.
- Gradium streaming speech recognition and synthesis, resampling to 24 kHz, playback acknowledgement, silence handling, bounded sessions and cancellation.
- Five real Dust agents provisioned through the API, with the application routing work to the coordinator, academic, support, visual and voice specialists. Existing original agents are preserved.
- A starter catalogue of 17 names/words and 11 written sound patterns, letter/syllable tiles, hyphenated syllables, whole words and post-success emoji illustrations.
- Spoken consent, private local progress, resume/forget flows and an optional protected companion screen for observed reading assessments.
- The original Pipelex method, unchanged, with a local adapter that executes its deterministic templates and uses Dust for activity selection. No third paid provider is required.
- Offline behavior tests, an upload-safe packaging script, and a GitHub Actions workflow.

## What access is still needed

Supply **Dust and Gradium API keys** in the private `apps/gradio/.env`. Dust workspace keys normally also need the workspace ID from the account URL. Setup discovers an available Dust model, creates the five app agents, verifies their instructions and selects Gaspard, a documented French male Gradium voice. Your accounts must permit these operations and have API credits. The setup command does not buy access or credits.

The code and offline provider contracts are tested; **no live Dust/Gradium conversation has been tested with real credentials**. Before using it with a learner, audition the voice and walk through a real session. See [validation](docs/validation.md).

## Teaching behavior

The learner chooses a supported name or familiar word and confirms it. Each new card invites an attempt before giving a model. Help, repetition, a different word, an easier activity and a pause are available by speech. A word outside the starter catalogue leads to an invitation to choose a supported word, rather than invented name phonology.

Practice can continue without an observer. It is recorded as **unscored practice**, never pronunciation mastery. A companion who actually hears an attempt can confirm it using a separate page; only that confirmation changes a score or reveals the corresponding word picture. A transcript or an emotional guess cannot do either. Guidance from ordinary TTS is not a validated isolated-phoneme recording.

This release takes turns: the microphone is gated during speech. The button stops playback immediately; speaking over the tutor does not interrupt it.

## Repository

| Folder | Purpose |
|---|---|
| `apps/gradio/` | Application, provider setup and browser audio |
| `agents/` | Preserved original instructions and explicit app contracts |
| `assets/` | Reusable linguistic content; visual tiles are rendered locally |
| `pipelex/` | Unchanged MTHDS source and optional native dependency |
| `tests/` | Offline provider, storage, learning and audio checks |
| `docs/` | Architecture, privacy, validation and upload instructions |
| `scripts/` | Source-only ZIP creation |

The server binds only to `127.0.0.1`. Credentials, learner files, recordings and local dependencies are excluded from the upload ZIP. Upload the **extracted contents** into a **private** GitHub repository; do not upload the ZIP as the repository's only file. No remote repository, push or publication is performed by this project.
