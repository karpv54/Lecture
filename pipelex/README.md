# Original method and local integration

`methods/tuteur_francais/main.mthds` is preserved byte-for-byte from the existing project. Domain: `tuteur_francais`; entry: `accompagner_apprentissage`; inputs: `session: Session` and `catalogue: Activite[]`; output: `Reponse`.

The running tutor uses `apps/gradio/method_adapter.py` to execute this file's deterministic Compose templates, with Dust academic supplying the candidate at `choisir_activite`. The backend creates a real catalogue from `assets/phonetics.json`, qualifies observed evidence, validates the proposed ID and applies deduplicated updates in SQLite. It does not send audio to the method.

This local adapter is deliberately limited to this supplied method. It is not a hosted Pipelex invocation or a general replacement for the Pipelex engine. No Pipelex account, deployment or inference credit is required for the default application. The native source dependency remains separately recorded as `pipelex==0.66.0`; do not install it into the default app environment unless you intentionally work on native Pipelex execution.

The original method leaves the failure increment to its caller. The application now defines +25, capped at 100; independent confirmed success retains -25 to zero. Guided practice and transcription-only evidence do not change scores. An unknown score remains unknown. The original source is not edited to hide these application responsibilities.

Standalone learner practice is tracked separately from evidence-based progression. When a companion supplies an observation, the full local rule path runs and its suggestion is visible in the companion panel. Ordered validated stages require observed mastery of their targets. Simply exploring a card never validates a stage.

Offline checks exercise source templates, evidence qualification, score bounds, idempotence, tone groups, unknown choices, wrong anchors and prerequisites. No current native Pipelex or hosted run was made; the Pipelex workshop was unavailable in the completion session. The source method's earlier historical validation is not a claim of live execution here.
