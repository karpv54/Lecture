# Dust configuration

Run `python apps/gradio/setup_providers.py --provision` after adding credentials. It reads accessible agent metadata, discovers an available model, and imports five managed `Lecture-*-App` agents. The original `Lecture-*` agents are not overwritten. Run `--check` for a read-only metadata check; use `--provision --update-managed` to refresh an older app contract.

The API key needs access to your workspace and permission to import/configure agents. A workspace key usually also needs the non-secret `DUST_WORKSPACE_ID` from the workspace URL. The program attempts `/api/user` only when the workspace is unknown and accepts discovery only when there is one unambiguous workspace. Set `DUST_BASE_URL` to your account's region. If no model is discoverable, supply both `DUST_MODEL_PROVIDER` and `DUST_MODEL_ID`; the setup code fills all required generation fields.

The application orchestrates the five real API agents. The coordinator classifies learner intent, the academic agent selects a constrained activity, visual and voice specialists review new cards, and support handles adaptations. Each agent receives the original instructions plus its explicit application addendum. The backend provides current state on every call; it never assumes a specialist shares another's conversation memory. No Run agent tool or Pipelex MCP connection is implied in this mode.

Only strict structured outputs are accepted. Independent invitations and rendered teaching text come from the controlled catalogue, not free-form model output. Provider messages, raw error bodies and specialist notes are never spoken. Interrupted POST requests are not automatically retried. Submitted generation is cancelled best effort on session closure.

Workspace programmatic credits are separate from personal seat access. A valid key does not purchase or guarantee available credits. Conversations/transcripts are stored by Dust according to your account settings. Do not share the workspace or conversation links publicly.

Official references used: [OpenAPI](https://raw.githubusercontent.com/dust-tt/new-docs/main/docs/developer-platform/dust-api-documentation/openapi.json), [agent import](https://docs.dust.tt/api-reference/agents/import-agent-configuration), [actual import schema](https://github.com/dust-tt/dust/blob/main/front/lib/agent_yaml_converter/schemas.ts), [credit management](https://docs.dust.tt/docs/user-documentation/admins/usage-seats-and-credits/credit-management).

Setup uses the API-key-compatible admin `view=all_unrestricted` agent list so it can find and reuse hidden tutor agents. Use an admin-scoped workspace API key for setup. To create missing tutor agents, also set `DUST_EDITOR_EMAIL` in the private `.env` to the email of an existing member of the same Dust workspace. Dust requires at least one editor for API-key imports. Existing configured agents can be checked or reused without this setting.
