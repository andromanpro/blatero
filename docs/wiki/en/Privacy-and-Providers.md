# Privacy, providers and prompts

## Data boundaries

Outgoing text uses a common size/redaction boundary. The default removes common
structured personal data, secrets and local paths from both system instruction
overrides and user context. Meeting text/documents/memory are untrusted source
data, not authority to execute commands. Redaction reduces risk; it cannot prove
all names, indirect identifiers or OCR mistakes are anonymous.

Workspace preparation adds a local exact-text/file-selection review with Russian
name analysis and custom terms. Images need manual pixel masking and a separate
acknowledgment. This full screen is not yet used for every live hint/report/
training request; those retain the baseline filter. Raw mode needs extra server-
checked confirmation; withdrawing cloud permission clears raw permission.

| Feature | What can leave this computer |
|---|---|
| WAV recording, Whisper, AEC, local Replay/clustering | Nothing through their normal processing path |
| Cloud SpeechKit STT | The selected live audio; readiness uses separate synthetic fixture audio |
| Cloud LLM | Selected/bounded text under the privacy mode |
| Visual workspace/material analysis | Separately selected, prepared/masked images |
| Cloud TTS | Text to synthesize, not microphone speech |
| Calendar integrations | Requests/credentials to the selected calendar service |
| Optional local bridges/library | Local selected files/logs; not automatic remote publication |

The operating system, external provider or manually shared export can have
additional copies. Blatero's local data map is not proof those copies are erased.

## Three distinct permissions

The operator confirms the basis for a **work recording** at start. **Cloud
processing enabled** is an application setting, not automatic spoken-consent
detection or a per-meeting legal determination. **Voiceprint permission** is
separate before adding a person to the bank. No checkbox substitutes for your
organization's applicable policy.

Without cloud permission, new external LLM, SpeechKit and cloud TTS operations are blocked.
Local recording, models and editing remain possible when installed. A compatible
loopback endpoint is local; a remote HTTPS endpoint is cloud. Redirects with
authorization are not followed to a different provider URL.

Withdrawing permission does not cancel requests already sent or an active
SpeechKit stream. To end that stream, stop recording or switch STT to a local
model, then wait for pending audio to finish. This is not an immediate network
kill switch and does not delete data already sent to the provider.

## Credentials and providers

Use [Provider setup](Provider-Setup.md) for key creation/login. LLM tokens and
calendar credentials use Windows Credential Manager. The current SpeechKit key
is a separate legacy plaintext home file; do not confuse it with encrypted
keyring storage. Old Google token files are removed only after successful
migration to the system store.

Codex runs without agent tools and is not authorized to read arbitrary files
because a transcript says so. The selected text provider/model and actual last
Codex route are shown in context; a model name is not a privacy consent.

SpeechKit and live Whisper profiles are configured for Russian in this release.
Interface English does not change recognition language, prompt language, name
detector coverage or voice. STT switching leaves WAV capture running and does
not re-recognize earlier text automatically.

## Prompts and output safety

Open **Settings → AI and hints → Advanced → System prompts**. Choose a catalog
entry, inspect required placeholders/default, edit/save or reset it. Changes
apply to the next request. Privacy/role/tool guards remain in code outside the
editable instruction; they cannot be disabled by prompt text.

Report prose cannot make DOCX fetch arbitrary Markdown images or local files.
Web report text is displayed without executing source scripts/active links;
application-generated evidence/source actions are separate. AI conclusions
still require factual review, not merely safe rendering.

## Diagnostics and deletion

Download sanitized diagnostics for versions, states, numeric metrics and error
codes. It excludes audio/conversation/prompts/keys by design; inspect it before
sharing. Raw session logs and model responses can contain sensitive text.
Use selective deletion, retention and encrypted transfer with their explicit
previews. Local data is not encrypted at rest by Blatero; choose OS encryption
as appropriate. [Reports and deletion](Reports-and-Archive.md).
