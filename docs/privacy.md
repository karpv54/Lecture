# Local progress and provider data

The learner chooses by voice whether to retain local progress. Refusal leaves learning state in memory until the session closes. Consent stores the chosen catalogue anchor, explored cards, confirmed preferences, observed scores/mastery and deduplicated assessment events in `data/learners.sqlite3`. The random browser cookie contains no name. One browser profile identifies one local learner; do not use a saved profile for someone else without the new-session flow.

No raw transcript, audio recording or inferred emotion is saved locally. Dust receives transcripts and necessary lesson context; Gradium receives microphone audio and text for speech. Each provider's account settings and retention terms still apply. Saying “efface mes progrès” and confirming removes the local profile and observation history, not remote provider data. Manage provider deletion separately in the corresponding account.

The companion link is a fresh local access secret on each process start. Keep it private. It lets a person who hears the learner submit an observation; it is not an automatic pronunciation assessor. The local server has one active voice session and is not an internet-ready shared service.

Keep `.env`, `data/`, recordings, logs and dependencies out of GitHub. The packaging utility excludes them independently of Git's ignore rules. The ZIP contains only source and documentation. A private repository is the intended upload destination.
