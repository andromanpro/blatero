# Troubleshooting

## Launcher cannot prepare an access token

Check `%LOCALAPPDATA%/blatero` is writable and not an unavailable redirected profile.
Check antivirus/Controlled Folder Access. Do not delete the token while a server
uses it; a stopped server's next launcher start can create a new one. Run browser
and server under the same ordinary Windows user. Do not send the token to support.

## Server is running but no page opens / port is busy

Try the normal local address. If authentication is requested, use the launcher
to establish the browser session. A stopped server cannot be started by a URL
alone. A busy port can be an existing Blatero or an unrelated process: identify
it first. Do not kill all Python processes or reuse an unknown server.

## No microphone signal

Select the exact device, refresh after replugging, check hardware mute/Windows
level and desktop-app microphone access. Close only a known app holding exclusive
access. Duplicated device names need their numbered entry. Browser permissions
alone do not fix a server-side audio-device denial.

For a self-paced test click Test microphone, wait for Speak now, talk for 12 s,
then listen. Voice check incomplete in Check all can mean missed timing, not
a broken device. Repeat when ready; do not green-check mere PCM noise as speech.

## Remote audio missing / everything labelled as me

Loopback must be the output the meeting app really uses. Check its audio settings
and Windows mixer; Bluetooth profiles/defaults can change on reconnect. Renaming
a channel does not fix a wrong capture source. Microphone mute inside the meeting
app does not mute Blatero. Check acoustic leakage, sidetone/listen/virtual mixers,
then calibrate with the actual devices/volume.

## Speech appears late or broken

Open the full transcript and check the counter: initially only the last 200
final events can be visible. Partial text legitimately changes until final.
Check Audio Guard's queue/latency and CPU/model load. Try a smaller **installed**
Whisper model or a permitted SpeechKit switch via its dedicated action; WAV
capture continues. An unavailable new recognizer leaves the old one running.
Reconnecting physical hardware can still cause a genuine gap.

If an older session contains `transcript-2.md`, do not rename files until backed
up. The complete transcript selects canonical substantive events across segments.
Use Replay to investigate source WAV; it does not overwrite RAW in a normal run.

## Speakers or confidence look wrong

Listen to several useful passages; set a plausible voice count, merge duplicate
clusters and split mixed phrases. A bank similarity is a suggestion, not identity.
Missing models must be installed before clustering. Missing confidence in an
old/imported transcript is unknown, not real 0% quality. Objective WER/DER/JER
needs a confirmed reference, not an appealing cluster count.

## Hints are missing, repeated or slow

Check live transcript, selected role and prepared context first. STT delay is not
the same as AI generation time. Read the displayed route/model/status; a server
receipt is not a provider receipt. Show new cards explicitly, pin useful ones,
mark duplicates/irrelevant or resolved items. A 45-second timeout re-enables the
request without stopping audio; it does not secretly pay for an automatic retry.

## Report contains internal discussion or timestamps

Check where the substantive interview ended, correct source boundaries if needed,
exclude the unsupported conclusion in review, and keep timestamps off. Source
changes invalidate a draft: rebuild explicitly when necessary. Confirming the
same valid draft exports locally; it does not regenerate the analysis.

## DOCX does not open or export

Portable has native DOCX export; Word/Node/LibreOffice are not required to create
it. Save other open work, close only the window holding this file and retry the
correct file rather than an old recent-documents entry. Check size, disk space,
permissions and exporter error. Keep Markdown. Only a separately configured
external converter needs Node/tool-path diagnostics. Do not force-kill all office
processes with unrelated unsaved work.

## AI or SpeechKit connection fails

Match token to provider, save/test, check account access/limits, model availability
and cloud permission. Codex CLI must be logged in under the same Windows user.
Remote compatible endpoints require HTTPS. SpeechKit requires its API-key file,
not a nonexistent UI field/IAM-token substitution. Check both service-account role
and key scope. [Setup](Provider-Setup.md). Authentication tests do not send meeting
materials; successful key presence is not real STT readiness.

## Update/recovery is blocked

Stop audio/video/background work. Confirm signature/version and use a complete
compatible package when dependencies changed. Never disable verification to force
an update. Preserve partial media and inspect recovery before cleanup. A live
process with an old heartbeat cannot be taken over based on time alone.

## Send a useful issue report

Include application/server version, work/test environment without participant
name, exact safe error code, reproduction steps and sanitized diagnostics. Say
whether it reproduces on synthetic test material. Inspect screenshots/diagnostics
before sharing; do not include keys, whole configuration, audio, transcript or
resume without a separate decision to share those data.
