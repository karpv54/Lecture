# Architecture

```text
One learner microphone button
  -> AudioWorklet resampling / WebSocket
  -> Gradium STT (transcript, not pronunciation evidence)
  -> Dust coordinator interprets choice/request
  -> Local lesson controller
      -> Dust academic selects an allowed activity ID
      -> Dust visual + voice specialists review new cards
      -> Dust support handles expressed adaptations/check-ins
  -> Local SVG teaching tiles and approved catalogue speech
  -> Gradium TTS / browser playback acknowledgement
  -> Listening resumes
```

The five `*-App` agents are genuinely called. Their orchestration is implemented in Python through Dust conversations, not through presumed Run agent tools. The original contexts are preserved, and each imported agent appends its `app-contract.md` explaining this transport. Toolsets are empty deliberately: these agents cannot directly write local files or call an unavailable MCP tool. No external Pipelex service is assumed.

## Learning authority

`assets/phonetics.json` owns spelling, segmentation, model text and optional word emoji. Dust chooses within the current eligible group; it cannot invent an activity, segmentation, URL or score. The first card for a target is an independent invitation; its model is only delivered after an attempt or an explicit help request. Separate syllables are SVG tiles separated by dashes; the combined word follows later.

`done` records unscored exploration. `mastered`, observed scores and ordered `validated_stages` are separate. Exploring harder or later examples is not represented as passing a stage. Names outside the curated catalogue are not guessed; the learner is offered a supported familiar word. Names inside the catalogue must still be confirmed by their owner, since spelling alone cannot settle personal pronunciation.

## Original method integration

The unchanged MTHDS defines evidence qualification, score reduction, five-result tone groups, progression constraints, candidate verification and result construction. The local adapter reads those exact Compose templates with strict Jinja handling. Dust academic supplies the model-selected candidate at the original PipeLLM boundary. This is a purpose-built adapter for this method, not a general MTHDS interpreter, native Pipelex SDK run or hosted deployment.

For an observed independent attempt, the application runs this rule path, displays its recommendation to the companion, and atomically saves the confirmed result. It adds the previously undefined failure policy: +25, capped at 100; success remains -25, floored at 0. A first scored target starts at 100; unknown -1 remains unknown. Guided attempts and uncertainty never change scores. Four independent confirmed successes can reduce a fresh target to 0. A later failure removes current mastery without erasing history. The method recommendation never silently substitutes for learner choice in unscored practice.

## State and cleanup

A random HttpOnly, SameSite cookie identifies a browser profile. Before storage consent, only in-memory lesson state exists; the empty SQLite database/schema may exist. Consented snapshots and an append-only assessment journal live in ignored `data/learners.sqlite3`. Event IDs prevent duplicate scoring. Writes and snapshots share a SQLite transaction. No raw transcript or audio is persisted locally.

The companion endpoint can enqueue only an observation for the exact active, answered attempt. The session applies it serially between speech turns. Stale and duplicate observations are rejected. A meaning picture is released only for the observed current word. New targets and stopping clear the picture. The app caps concurrency at one active voice session and closes all local audio tasks on stop/disconnect.
