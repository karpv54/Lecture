# Validation

## Offline checks

From the repository root, using the installed app environment:

```sh
python -m unittest discover -s tests -q
node tests/test_audio.cjs
```

The completion run passed 46 Python behavioral tests and JavaScript audio checks at 24, 44.1, 48 and 96 kHz. These cover explicit consent, declined storage, resume/forget, attempt before model, guarded illustration reveal, no scores from transcripts, guided versus independent practice, observed scoring, stale/duplicate feedback, SQLite transaction/deduplication, method prerequisites, restricted provider reply parsing, setup idempotence, workspace discovery, read-only setup, companion authorization, cross-origin rejection, cancellation, image-load acknowledgement, playback acknowledgement and STT flush behavior. The tests use explicit fake providers/HTTP responses and never load real credentials to make inference calls.

The actual Gradio page was opened locally and its missing-key behavior inspected. Syntax checks pass for browser JavaScript. The upload ZIP is checked for required dotfiles, archive integrity and excluded private folders.

## Live acceptance after access arrives

Live provider authentication, workspace credits, remote agent creation, actual speech quality and microphone hardware could not be verified without credentials. No paid provider inference was run during completion. Offline tests do not establish these live results.

After SETUP succeeds, use a short operator session: consent or decline, choose a supported word, confirm it, attempt a displayed card, ask for help, hear the model, and stop. Check that listening resumes only after playback, no answer is spoken before the initial attempt, and no picture appears without a real companion confirmation. In the companion page, confirm one observed word; check that its picture appears and an independent score decreases once. Restart and check consented resume. Say “efface mes progrès” and confirm when testing local erasure.

Audition contextual sound models and the selected voice for your audience. STT has no acoustic grading role. This is a local literacy prototype with a finite starter catalogue, not a validated educational or pronunciation-assessment instrument. The original native/hosted Pipelex engine was not run; the default app tests the local adapter against the supplied method source.
