# Run the application

From the repository root, use Python 3.11+:

```sh
python -m venv apps/gradio/.venv
# Windows:
apps\gradio\.venv\Scripts\python -m pip install -r apps/gradio/requirements.txt
# macOS/Linux:
apps/gradio/.venv/bin/python -m pip install -r apps/gradio/requirements.txt
```

Copy `.env.example` to `.env` beside `app.py` without overwriting an existing file. Fill your two keys and workspace ID. On Windows the root SETUP.cmd handles environment creation and this first copy. Environment variables take precedence over `.env`; empty optional identifiers still allow the saved setup values.

Using the environment's Python:

```sh
python apps/gradio/setup_providers.py --provision
python apps/gradio/app.py
```

Open http://127.0.0.1:7865. Browser microphone access requires localhost or HTTPS; this application intentionally binds to loopback. Set `GRADIO_SERVER_PORT` if the port is occupied. The command prints the actual address. Stop the server before restarting after code/configuration changes.

Setup uses the public Dust import API and Gradium voice metadata only. It is idempotent and refuses to overwrite an unrelated same-name agent. To update this app's existing managed agents after a contract change:

```sh
python apps/gradio/setup_providers.py --provision --update-managed
```

Read-only account check: `python apps/gradio/setup_providers.py --check`. Offline template export: `python apps/gradio/setup_providers.py --export work/agent-templates`. Manual exports leave model settings for your workspace; the normal setup command discovers and fills them, including temperature and reasoning effort.

## Runtime

One conversation may run at a time. The microphone sends 80 ms PCM16 frames at 24 kHz through a same-origin WebSocket. AudioWorklet resamples other browser rates. Gradium semantic VAD waits conservatively for a completed turn; a flush includes delayed transcription. The server accepts only selected completed Dust agent replies with strict schemas. Models cannot inject arbitrary text into SVG or speak an independent answer through a free-form reply.

Speech streams to the browser as PCM. Listening resumes only after the browser confirms playback ended. Stop releases microphone tracks, the AudioContext, queued playback, sockets and tasks. Remote Dust cancellation is best effort; submitted work may already have completed or incurred charges. A session has a 15-minute cap. Two approximately 55-second silent listening periods, separated by a gentle reminder, end it without a learning error.

The learner view contains no settings or typed chat. The separate `/accompagnant` page requires the ephemeral secret in the printed private link; API operations require a token header and same-origin checks. Keys remain server-side. Never expose this local server on the public internet without an independently designed authenticated deployment and usage controls.

## Modules

- `settings.py`, `setup_providers.py`: private settings, metadata checks and app-agent provisioning.
- `dust_client.py`: real specialist conversations, strict JSON and cancellation.
- `voice_session.py`: streamed audio and session lifecycle.
- `lesson.py`, `curriculum.py`: consent, teaching, assessed versus unscored practice.
- `method_adapter.py`: source-driven local MTHDS Compose execution, with Dust selecting candidate IDs.
- `store.py`: atomic, consent-based SQLite snapshots and deduplicated observation history.
- `app.py`, `web/`: Gradio, SVG rendering and companion UI.

Test details and limits: [docs/validation.md](../../docs/validation.md).
