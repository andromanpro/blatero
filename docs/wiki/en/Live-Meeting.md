# Live meeting

## Before recording

**New meeting** accepts a topic or a project/tasks/time. **Load context** reads
local task records, selected project documents, confirmed memory and earlier
reports; **Create and open** does not record or call AI. The detailed wizard
adds role/material preparation. A task's **Discuss in a new meeting** carries
its topic/goal; a closed or merged task is not silently reopened.

Run **Check all** before REC. Read the instructions, click readiness, speak after
the countdown, then stay quiet for the system signal. It checks capture, STT,
models, AI connection and writable results. A configured key is not proof that
speech recognition works. The recognizer must transcribe a built-in synthetic
phrase; SpeechKit sends only that fixture audio for this test. Local Whisper is
checked on two channels and fails readiness if too slow, even with correct text.
The 25-second STT limit is not a guarantee of live latency under every load.

Changing devices/model/recognizer invalidates readiness. The combined check is
blocked during REC. If calibration is absent/stale, calibrate or explicitly
continue without it. A work recording additionally requires a statement that
participants are notified or another applicable basis exists. Cloud processing
and voiceprints have separate permissions.

## Start and stop

**Record** offers audio only, audio with a screen, or audio with a window. Video
requires source selection and preview before confirming the meeting recording.
**Stop** stops the audio and the video linked by that action. Standalone video
started through Materials is not automatically part of that pair.

Microphone and system loopback are separate WAV tracks. Final recognition events
are saved in JSONL and rendered to Markdown. **Stop** drains the last phrase;
forced interruption is for a hang, not normal use. **Continue recording** adds a
new segment without overwriting old tracks. Source files are not concatenated
in place. Video MKV is silent; audio stays in WAV. [Video details](Video-Recording.md).

## Switching speech engines

Use **Settings → Audio and speech → Switch engine** or the dedicated local-model
action. The new recognizer prepares while the old one continues. Only PCM
consumers change; devices, WAV files and their timeline remain open. The old
recognizer can finish its queued tail separately. A preparation failure leaves
the old route active. Install missing models while idle. Hardware replugging is
different and can interrupt the physical signal. Earlier transcript text is not
re-recognized automatically; compare it in Replay later.

## Reading and managing hints

**Only essentials** hides navigation, scenario and auxiliary rows without
stopping recording. **Normal view** restores them. **A− / A+ / percentage** changes
only hint text size; the percentage resets to 100%. General UI scale is separate.

The hint button or `P` sends the current context to the selected route. Hints
mean next questions for an interviewer, an answer scaffold for a candidate,
clarifications/risks for consulting, or missed decisions for other meetings.
Automatic hints can be off, pause-triggered or interval-triggered. The server
shows that it accepted a request, elapsed time, completion or failure. This is
not a separate receipt from an external provider. A lost connection is not shown
as proof that AI is still working. The total hint deadline is 45 seconds; late
results do not replace the current state. STT delay and AI-generation delay differ.

The first set appears immediately. Later hints wait behind **Show new · N**,
so reading does not jump. On reveal, new cards appear above; old unpinned cards
fade into history over 45 seconds. Hover/focus pauses fading. Multiple pins are
supported. **×** records irrelevant/useless/duplicate, **Answered** resolves a
question, **Resolved** a risk. These choices persist and inform future hints.
Fading is not resolution. Historical resolved risks/questions and dismissed
cards have separate collapsed groups; **Restore** brings an item back.

The right-hand scenario contains prepared questions, reasons, source facts and
hidden reference answers. Mark asked questions as you go. `Ctrl+B` toggles it,
`Ctrl+J` history, `Ctrl+K` commands; shortcuts do not replace ordinary controls.

## Transcript and audio guard

Adjacent fragments may be visually grouped. Initially the last 200 final events
are shown for a long meeting; the counter identifies hidden earlier events and
offers the complete history. **Full transcript** combines final segments.
Changing partial text is normal; it is not a saved final statement.

The compact Audio Guard row watches silence, clipping, wrong output, echo,
device loss, STT queue/delay, WAV lag and disk space. It does not expand over
hints automatically. Open it for the cause, action and verification criterion;
the expanded area scrolls internally. RTF below 1 means faster-than-real-time
processing of that fragment, not recognition accuracy.

## After Stop

Choose **Finish and create report**. Speaker review is offered when useful;
you do not have to sort every phrase. **Analysis / Report / Transcript / Materials**
keep the result in the same window. The saved web report supports headings,
tables, contents, text sizing, DOCX download and browser printing without a new
AI call. A draft or stale report remains labelled. **Generate again** is a
separate confirmed operation, not an effect of opening/downloading the report.

**Review agreements** proposes memory items for your confirmation; task acceptance
is separate. [Reports](Reports-and-Archive.md), [Memory](Calendar-and-Memory.md).

## Diagnostics and SIM

Download sanitized diagnostics from audio settings for support. Raw `live.log`
and `hints.jsonl` can contain conversation text; do not send the whole session.
`diagnostics.jsonl` records bounded technical timings/codes, rotates at 4 MiB,
and is removed by result cleanup. Inspect even a sanitized export before sharing.

SIM is a voice bot in the current meeting, not a fourth studio composition.
Its role comes from meeting settings; the bot speaks through the selected TTS
and the microphone still listens to you. Its generated text is not a verified
reference answer. [Training/SIM](Training.md).
