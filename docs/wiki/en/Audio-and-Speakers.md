# Audio and speakers

Open **Settings → Maintenance → Audio and speakers** for readiness checks,
Replay, clustering, names, voice bank, import and reference annotation. Normal
Replay creates derived results and does not replace source WAV or live JSONL.

## Test the microphone when you are ready

1. In audio settings choose the real input and save.
2. Click **Test microphone**. Wait for 3–2–1 and **Speak now**.
3. Speak the displayed phrase normally for 12 seconds. Watch the level/time.
4. Play **Your sample**. Check for speech, not just noise.

Cancel stops countdown/capture; repeat starts again. Delete/close clears the
sample from tab memory. This test does not call STT/cloud or create meeting
files/voiceprints. During REC use the live meters. Headphones are not mandatory
for this test, but reduce acoustic echo.

## Check all before a meeting

1. Open **Check all**, read the instructions, then click readiness.
2. Speak after the countdown for the indicated eight-second voice check.
3. Stay quiet for the generated system signal and joint capture/AEC tests.
4. Review each result. **Voice check incomplete** can mean you did not speak in
   time; it does not prove hardware failure. Repeat when ready.

The microphone speech is not kept or sent to cloud. STT uses a separate built-in
synthetic phrase; only that audio is sent if SpeechKit is selected and permitted.
Whisper transcribes locally. LLM connection testing is technical, not a meeting
request. A short pass does not prove every device or future recording.

Select the same **meeting output** that the meeting app/browser actually uses.
Muting your microphone in that app does not mute Blatero's local capture.
If a device name is duplicated, select the numbered entry. An ambiguous old
name is rejected. After replugging, refresh the list; diagnostic gaps remain
visible even when an input reconnects.

## Echo and calibration

AEC compares the system reference and microphone signal before recognition.
The original microphone WAV stays unchanged. Auto uses WebRTC AEC3 when ready,
otherwise the built-in correlation filter. WebRTC can fall back safely on error.
Text deduplication is a later safeguard for confident copies of the same phrase,
not permission to discard short answers from the other participant.

Calibrate in a quiet room using meeting devices and volume. Device/output/backend
changes can make it stale. Calibration is recommended, not an unavoidable start
condition; you can explicitly proceed without it. Do not calibrate over an
ongoing conversation or change hardware settings mid-test.

## Quick participant review

After Stop, open **Participants and voice bank → Automatically find voices**.
Local installed models cluster meeting-output tracks and compare saved profiles.
Missing models produce a reason instead of an empty successful result. Unknown
voices appear first. Listen to more than one useful sample and **Save name**.

**Save name and voice to bank** additionally needs explicit voiceprint permission.
Short or overlapping speech is not used as a profile. A similarity score is not
proof of identity. This quick review does not rewrite source WAV, transcripts
or a finished report. Applying names to transcript phrases remains a separate
detailed review; real-time personal identification is not enabled by this screen.

## Replay and detailed names

1. Open Replay for the selected archived meeting.
2. Choose a WAV/channel, Whisper model, echo options and voice clustering.
3. Set the expected speaker count if known and start the experiment.
4. Open the timeline; listen before/after doubtful passages.
5. In speaker review merge clusters of one person, split obviously mixed phrases,
   assign names or confirm a bank suggestion, then save the derived mapping.

Runs are stored under `replay-runs`; cancellation does not overwrite the original.
A matrix compares duration, events, echo indicators and reference metrics. Without
a confirmed manual reference there is no proven BEST or accuracy recommendation.
Raw Whisper confidence is not calibrated accuracy and cannot rank models alone.
Accepting a candidate selects the derivative for review, not a rewrite of RAW.

## Voice bank, editor and import

A voice profile stores a name, metadata and numeric embeddings, not a copied
source recording. Create only with an applicable basis. You can rename, test or
delete a profile. The temporary test WAV is removed on success/error. Existing
meeting originals are not removed when a profile is deleted.

The transcript editor can search, play context, correct text/time/channel/name
and split a phrase. Saving updates canonical JSONL and Markdown with an audit
trail. A stale revision conflicts rather than overwrites another tab. Back up
before editing important records; a text correction is different from Replay.

Import supports available text/subtitle/JSON/document exports through an explicit
adapter or detection. It adds a new segment, does not replace the live history,
and rejects oversized/unsafe structures before publication. Source names in the
adapter describe formats, not a dependency on one meeting service.

## Quality reference and Audio Guard calibration

Annotate the exact recording/segment/track, review and confirm the reference.
Only confirmed material contributes to WER, DER/JER, channel error and false
echo-suppression measurements. DER/JER use a 250 ms collar. A different/missing
WAV is not a valid reference. A typical calibration corpus needs 10–20 varied
confirmed work recordings; one good call is insufficient.

Audio Guard calibration uses confirmed labels plus numeric telemetry. If data
is insufficient or a metric unsupported, it shows the blocker and leaves the
current thresholds unchanged. Preview proposed thresholds before applying them;
do not claim calibrated quality from synthetic tests.

Local Replay, AEC, Whisper, clustering, editor and voice bank stay on this
computer. SpeechKit receives live audio only when selected; cloud LLM receives
text under the chosen privacy policy. [Details](Privacy-and-Providers.md).
