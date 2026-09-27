# Five specialists, one learner-facing voice

The original `instructions.md` files remain unchanged. `catalog.json` records their roles and the separate `*-App` names. Each app agent appends `app-contract.md`, which explicitly replaces assumptions about unavailable tools with the real backend routing, strict JSON output, local rendering, Gradium speech and application-owned storage.

Run the provider setup utility to create/reuse these app agents. The academic agent selects catalogue activity IDs, support returns a requested adaptation, visuals and voice review new cards, and the coordinator interprets the learner's request. Python invokes each real Dust API agent and validates its result. There are no unused local prompt files masquerading as a remote multi-agent configuration.

The original Dust-only setup in `reference/` remains available for a separate native Run agent arrangement. Do not mix that arrangement's tool assumptions with this app's contracts. The older `coordinator/voice-channel.md` is retained for provenance; `app-contract.md` is authoritative for the completed app.
