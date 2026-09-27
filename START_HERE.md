# Start here

## Windows

1. Extract the complete folder somewhere you can keep it. Python 3.11 or later is required.
2. Double-click **SETUP.cmd**. It installs the local dependencies once and creates `apps/gradio/.env` if missing.
3. Open that `.env` file in a text editor. Fill `DUST_API_KEY`, `GRADIUM_API_KEY` and normally `DUST_WORKSPACE_ID`. Keep the file private. Copy the workspace ID from `/w/ID/` in your Dust address. If your account uses `eu.dust.tt`, change `DUST_BASE_URL` to match.
4. Run **SETUP.cmd** again. It creates or reuses the five application agents and saves their IDs privately. It also verifies the default French male voice. This setup does not request speech or model inference.
5. Double-click **START.cmd**, then open **http://127.0.0.1:7865**. Keep the terminal window open. Press the microphone button and allow microphone access. Press the same button to stop.

You can run START before setup to view the screen. It clearly reports that conversation is unavailable, without pretending to connect.

If model discovery is unavailable, set both `DUST_MODEL_PROVIDER` and `DUST_MODEL_ID` to a model available in your Dust workspace. The setup program prints the exact next action when permissions or configuration are missing. Keys and a paid seat do not automatically supply programmatic credits.

## With a companion

The terminal displays a separate **Companion (private link)**. Open it in another tab or window while keeping the learner screen open. After you actually hear a reading attempt, select “Lecture confirmée”, “À reprendre”, or “Je ne peux pas évaluer”. Never judge from the speech transcript. The link changes on every app restart.

Without a companion, the learner can practise freely with models and repetition. Pronunciation remains ungraded and meaning pictures stay hidden. Confirmed guided repetitions do not establish independent mastery.

## Progress and privacy

At the beginning, the tutor asks whether to keep progress on this device. Saying no leaves the session temporary. Saying yes stores a small local learning record; a later start offers to resume it. Say “efface mes progrès” and confirm to delete local progress. This does not delete provider-side conversations. One browser profile represents one learner; changing learner requires the new-session flow.

No audio recordings or raw transcripts are saved locally. Audio is sent to Gradium and transcripts to Dust to provide the service. Their account retention settings apply. See [privacy](docs/privacy.md).

## What remains to check with your API access

The application is implemented and offline-tested. Real account permissions, available credits, voice quality, latency, recognition of a particular accent/name, and actual microphone hardware must be checked with your own access. Start with an adult operator's short practice session before inviting a learner. The starter content should also be reviewed by a literacy professional for your audience.

## Uploading to GitHub

Create a **private** repository, extract the delivered upload ZIP, and upload its **contents**, preserving folders and dotfiles such as `.gitignore` and `.env.example`. Never add your private `.env`, `data/`, or recordings. Instructions: [docs/github.md](docs/github.md).

To stop the server, press Ctrl+C in its terminal. To run local tests, double-click CHECK.cmd. For Linux/macOS and manual commands, see [apps/gradio/README.md](apps/gradio/README.md).

Setup uses the API-key-compatible admin `view=all_unrestricted` agent list so it can find and reuse hidden tutor agents. Use an admin-scoped workspace API key for setup. To create missing tutor agents, also set `DUST_EDITOR_EMAIL` in the private `.env` to the email of an existing member of the same Dust workspace. Dust requires at least one editor for API-key imports. Existing configured agents can be checked or reused without this setting.
