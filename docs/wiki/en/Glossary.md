# Glossary

## AEC

Acoustic echo cancellation: remove a confident system-audio echo from the
microphone before recognition. It is not deletion of the original microphone WAV.

## Confidence

A recognizer's internal certainty signal for a phrase/word, not calibrated
accuracy or factual truth. A missing metric is not zero confidence.

## Diarization

Separate one track into voice clusters. A cluster is not automatically a person's
identity; assign/confirm a name after listening.

## Evidence

A local connection between a conclusion, event, speaker/time and audio passage.
It is not a public URL that works without the meeting files.

## Generation ID

An identifier of a background/model request. It connects diagnostics, response
and known usage/cost. A provider request ID and a local job ID are not always the
same thing. Unknown cost is not zero.

## Idempotency

Safely repeating the same operation reaches the same state without duplicating
data or causing additional harm. Reapplying a chosen voice map must not overwrite
source WAV a second time.

## Loopback

Local capture of what the computer sends to the selected output, used for remote
participants and as an echo reference. Microphone mute in another app is separate.

## Partial and final

Partial is a changing recognition draft. Final is the completed event saved in
canonical history; its earlier partial is no longer a separate statement.

## PCM, WAV and MKV

PCM is sampled sound. WAV stores the source audio tracks; MKV stores optional
video without audio in this version. A scene's edited WAV is not a live timeline.

## Privacy boundary

The common outgoing-text preparation applies limits and the chosen redaction
before an external LLM. It reduces risk without guaranteeing anonymity.

## Replay

A separate experiment on saved audio with recognition, echo removal or voice
clustering. Its derived results are not an in-place replacement of the original.

## STT and TTS

Speech-to-text recognizes audio. Text-to-speech synthesizes voice. Local Whisper
and cloud SpeechKit are STT routes; Chatterbox/Yandex and scene Gemini are TTS
routes with separate privacy/installation requirements.

## WER, DER and JER

Word error rate measures text against a reference; diarization error rate measures
speaker/time assignment; Jaccard error rate compares speaker regions. Lower is
generally better. Without confirmed annotation they are not quality measurements.

## Work/test environment and receipt

Work is for real meetings; test is for experiments, logically separated in the
archive/memory/metrics. It is not an OS sandbox. A turn receipt proves which card
revision an agent outcome saved, not correctness or user acceptance of the work.
