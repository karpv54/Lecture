# Gradium speech

Set `GRADIUM_API_KEY` in the private app `.env`. Setup selects **Gaspard** (`iEu63s1rhn_kegTr`), documented as a warm French masculine voice, and verifies that its metadata is accessible. `GRADIUM_VOICE_ID` can override it. Metadata verification is not a voice audition; listen with your account before learner use.

The default server is `https://eu.api.gradium.ai/api/`. You may select the official US/global endpoint with `GRADIUM_BASE_URL`. Never put the key in browser code. The browser talks to the local application; the server talks to Gradium.

Input is mono PCM16 at 24 kHz in 80 ms frames. An AudioWorklet converts device rates before transport. French STT uses `delay_in_frames=16` and a conservative three-second semantic VAD horizon, followed by a flush. Delayed text is included before the next turn. The model is not biased with the expected reading answer.

TTS streams PCM using the sample rate returned in its ready message. Playback acknowledgement, not synthesis completion, reopens the microphone. The stop button cancels queued audio immediately. This release has no speech barge-in. No local audio recordings are saved.

STT provides a transcript, not a pronunciation score or an emotion detector. The app never interprets Gradium output as either. Pattern models use contextual French words/syllables; TTS is not a verified isolated-phoneme recording. Replacing difficult demonstrations with educator-reviewed recordings remains an optional enhancement.

References: [streaming STT](https://docs.gradium.ai/guides/speech-to-text), [streaming TTS](https://docs.gradium.ai/guides/text-to-speech), [flagship voices](https://docs.gradium.ai/guides/voices/flagship-voices), [voice metadata](https://docs.gradium.ai/api-reference/endpoint/get-voice).
