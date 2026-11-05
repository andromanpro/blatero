# Blatero

By **androman** · [androman.pro](https://androman.pro) · [Telegram](https://t.me/andromanpro1c)

Blatero's own code is [MIT-licensed](LICENSE). See [third-party notices](THIRD_PARTY_NOTICES.md)
for components distributed under their own licenses.

A local workspace for meetings, tasks and project knowledge. Capture microphone
and meeting audio separately, keep the original recordings, transcribe speech,
request live hints and prepare a reviewable report. Tasks retain their goal,
method, rationale, sources and next step.

## English interface status

Select **English** in
**Settings → Appearance → Interface language**. On the standalone task board,
open **Settings** in the top bar. Meeting/results, settings, task workflows,
studio, library, labs and maintenance have RU/EN interface labels. External/native
diagnostics can retain their original language. Detailed [English help](docs/wiki/en/Home.md)
and Russian help are included as offline HTML in portable.

The choice is saved in this browser. It does not change the meeting language,
the transcription engine or the language of AI-generated text. User names,
tasks, source documents and reports are not automatically translated. Current
live recognition profiles are Russian-focused; EN interface is not EN STT support.

## Optional apps

Blatero does not require Granka, Neon Legion or Motivelium.

- **Neon Legion**: read local AI usage logs and match them to linked tasks.
  API-equivalent cost is not the subscription bill.
- **Granka**: read article snapshots and publishing dates. Editing stays in Granka.
- **Motivelium**: a separate tool for video work; no direct connector is implemented.

Neon Legion and Granka are disabled by default. Enable them in **Settings →
Connections**. Disabling keeps existing snapshots and links. There is no automatic
installation or launch of their interfaces. Reading Granka runs its local exporter
only after opt-in; its article originals are not modified by the Blatero adapter.

The built-in **Help → Other apps** section links to the related projects.

## Data and providers

Original WAV files are separate from speech recognition. Switching a recognition
engine must not restart capture or rewrite existing WAV files. New recording
segments and training attempts use separate files.

Local Whisper can recognize speech without a cloud key. Yandex SpeechKit sends
audio to Yandex. AI hints and reports use the selected provider; cloud processing
requires explicit acknowledgment. UI language is not a cloud permission.
See [privacy and data flows](PRIVACY.md).

## Development status

This is a development release candidate, not a stable portable release. The
current work is checkpointed in Gitea. The release checklist tracks final
documentation, full owner-signed portable and verification of the unpacked package.
See the [architecture plan](docs/ARCHITECTURE_NEXT.md) and [roadmap](docs/ROADMAP.md)
(currently Russian).

Windows audio development uses Python 3.12 and the pinned dependencies in
`requirements.lock`. Run tests against disposable data with paid/cloud calls
mocked. `tests/offline/sitecustomize.py` provides an opt-in external-network guard
when `tests/offline`, `tests` and the repository are on `PYTHONPATH`.
