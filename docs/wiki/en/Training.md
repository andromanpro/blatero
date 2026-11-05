# Training studio

Open **Settings → Practice**. New practice uses a separate test meeting; choosing
a mode opens preparation without recording or calling AI. Existing attempts can
be continued. Work recordings and ready-made videos are not practice inputs by
default. Role/topic are not limited to software interviews.

## Explain a project in two minutes

1. Open the **Speech** tab, choose project and listener, then **Prepare exercise**.
   Goal/duration/other exercises expand separately; **Topic and parameters** edits
   them later.
2. **Record attempt** uses normal audio readiness/start. Wait for **Speak** after
   the countdown. Explain who needs the project and why, a concrete example,
   result and next step. Two minutes guides you; it is not an automatic cutoff.
3. **Finish and save** drains the recognizer's last words and stores a separate
   attempt. **Get review** is a separate AI action with elapsed time, not a guessed
   countdown to completion.
4. Read source-linked observations, select/edit **one change**, **Prepare repeat**
   and **Record repeat**. Topic and listener are retained.
5. Save, then **Compare the selected change**. Compare actual quotes and play both
   passages. Improvement is not assumed or guaranteed.

Text-only attempts are available. Compare text with text or microphone with
microphone, not fabricated equivalent durations. Empty capture can be cancelled;
retained WAV does not earn a review. Text has no measured pace/duration. Local
counts/estimated pace/phrases to listen to are signals for review, not a judgement
of voice, diction, confidence or emotion from transcript text.

Review/comparison use the selected AI/privacy route; audio is not sent to the
text model. Requests may cost money or use subscription quota. Quotes are checked
against saved text; unsupported quotes are discarded. Raw model output is kept
before validation. Invalid output is not automatically bought again. Reopening
a completed result uses saved data. History keeps earlier text/WAV unchanged;
speech exercises do not change the interview competence profile.

## Choose who asks and answers

| Composition | Interaction | Retained data |
|---|---|---|
| I answer | AI interviewer asks; you speak | Actual microphone WAV, transcript, evaluations/report |
| I ask | You ask; send the fresh microphone question to an AI candidate | Actual question WAV, AI replies, scene dialogue/review |
| Both AI | Two artificial participants, stepwise or automatic | Per-reply WAV, dialogue, review and a labelled edit |

The browser remembers composition; changing during an active run is blocked.
An AI scene evaluates a fictional candidate, not your competence. SIM in a normal
meeting is a separate function, not another composition.

## Prepare roles and a plan

Use a free role or a versioned competence profile: 1C developer, integration
engineer, solution architect or IT consultant. A profile supplies themes,
level expectations and observed criteria, not an asserted personal biography.
Choose junior/middle/senior/mixed and material: pasted resume/job/brief, up to
three public HTTPS links, local portfolio folder and relevant project memory.
Local/service URLs are blocked and fetched input is bounded. Privacy filtering
still applies. A plan has questions, competence, difficulty, reference answer,
criteria and graded hints.

The fictional candidate starts at the selected level: junior handles basics,
middle works independently, senior discusses ambiguity, trade-offs, risks and
verification. Mixed means uneven strengths, not mandatory ignorance. A hint adds
a condition, check or alternative; it does not turn a novice into a senior.
Uploaded resumes do not acquire invented owner experience. Preparing a new
profile archives old run data instead of rewriting existing answers/WAV.

## I answer

Prepare questions, check audio, then **Start training**. Listen to the spoken
question, answer by microphone and use the text field only for recognition
correction. Open a hint if wanted, then **Evaluate and next**. Question audio is
saved before playback and not treated as your answer through loopback echo.
**Continue training** resumes the ordinary recording route after a Stop.

Hints provide direction, key concepts or a fuller structure. Evaluations separate
content, independence/support use and readiness; a resume is not proof of an
answer you did not give. Feedback includes a concrete gap, correction, stronger
answer and likely follow-up. Timing/filler indicators use local transcript data,
not cloud audio analysis. Opening a hint is your explicit choice; its use remains
visible in the evaluation rather than being passed off as an independent answer.

Adaptive sequencing selects weak/due topics and suitable difficulty. A concrete
gap below the configured success criterion can supply the next follow-up; there
are at most three follow-ups per attempt and a follow-up does not recursively
create another. Turn adaptation off to keep the original order.

Completed attempts update the role's local skill history/next focus; unfinished
ones affect only the current screen. The model receives aggregates/recent question
wording, not every previous answer. Reset current attempt keeps plan/history;
reset history is a separate confirmed deletion. Finishing drains the final reply,
evaluates it and creates training review, report and DOCX with role/date.

## I ask

Prepare candidate roles, inspect the legend/voice, start normal microphone
recording, ask one question and wait for transcription. **Send microphone
question** consumes only fresh your-channel events, not an earlier question.
If text is not ready it asks you to wait, rather than resending old content.
The manual field corrects STT. Your voice is never replaced with synthetic TTS.
**Stop and review** preserves the recognition tail and produces the scene review.

## Both AI and the hint audience

Choose roles, level, 2–10 rounds, style/materials and voices, then prepare.
Stepwise advances explicitly; automatic timing advances after speech playback.
The interviewer sees public requirements/profile, not hidden candidate gaps;
the candidate sees its legend, not the evaluation rubric. A separate review can
see both. An invalid profile is rejected before AI/material work.

**Hints for** is explicit:

- **Candidate · answer with help:** first thoughts → hear/read the saved hint →
  click to continue with it. Only the candidate receives that help; provenance
  says the answer was assisted, not independent. Replay reuses the original hint.
- **Interviewer · independent participants:** observer guidance helps assess or
  choose follow-ups; neither fictional participant receives it. Playback pauses
  after a question until you continue.

Do not switch audience during an active scene. A human takeover uses microphone/
input, not a fabricated human opening. Missing/invalid hints do not trigger an
assisted answer. New scenes suggest candidate assistance; older scenes keep
their previous audience/settings.

Scene hints read **heard** dialogue, not future prepared candidate answers or the
hidden profile. After a question a short scaffold can appear before details,
with route/model/time. A separate **OpenRouter Flash** hint route can use the
saved OpenRouter key without changing the main AI provider. These are distinct
potentially paid calls. Replaying saved voices does not imply hints are free.

## Voices, transcript timing and retained audio

New scene defaults are the configured Gemini Kore interviewer/Charon candidate
through OpenRouter. Actual catalog names/availability are provider-dependent.
Normal question voice, Yandex and Chatterbox settings are independent. Older
scenes retain their voices. A synthesis failure is visible; there is no silent
switch to another paid voice. Original response/generation identifiers are kept.

The visible transcript follows actual playback time, not pre-exposed future
text. Saved synthetic WAVs use local Whisper word timings; install the local
model first. Missing local timing support is shown, not an automatic cloud audio
upload. Pause stops word reveal; replay reuses saved timings. Source text is kept
separately for terms that STT misreads.

Every spoken reply is saved exclusively before playback with a checksum. Same
voice/reply replay uses that WAV. New voice variants do not overwrite old ones.
The pronunciation dictionary expands WMS/1C/HTTP/API/JSON/XML/SQL for the synth
input only, not stored dialogue/report or previous audio.

Streaming-phrase Kore/Charon begins with a short phrase while later ones prepare.
PCM is flushed to disk before playback and the complete WAV uses those samples.
This is a phrase pipeline; a provider can buffer a whole phrase, so first-audio
latency remains. On Stop, started parts/receipts remain; ready parts replay
without buying them again, missing parts may need explicit synthesis. Incomplete
speech is not marked complete. Cleanup/shutdown is blocked during persistence.

At completion the scene can create a **stereo edit**, interviewer left/candidate
right with 0.25-second gaps. It is an edited sequence, **not wall-clock capture**.
In I ask it contains only AI audio; your real microphone WAV is separate and not
automatically mixed. Missing speech is counted; a partial scene is not labelled
fully voiced. Source dialogue/review/WAV remain available after a new run/reset,
not silently replaced. Only explicit cleanup/deletion removes them.

## Avatars and SIM

Two sharp-contour blobs follow actual saved audio/playhead. Paused audio is not
shown as speaking. A human mic level is signal, not identity/emotion detection.
Thinking means a model request is pending. You can hide avatars or choose a
fictional calm/friendly/thoughtful/tense character; colour is that chosen style,
not a psychological assessment. Human mood selection is disabled. OS reduced
motion and the workspace motion choice are respected without stopping audio.

SIM instead uses the ordinary meeting and a bot role from meeting parameters.
It supplies one probable participant response, not a verified reference answer.
It can use local Chatterbox or explicitly permitted Yandex speech/fallback.
Cloud TTS permission, recording permission and voiceprint permission are distinct.
