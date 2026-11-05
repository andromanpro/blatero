# Provider setup

Reviewed against Blatero and official setup references on 1 November 2026.
Provider consoles change; use their linked instructions if a menu moves.
Use your own credentials. A colleague's portable ZIP does not contain the
author's subscription login, keys, profile or meetings.

## Choose a route

| Need | Setup |
|---|---|
| Local recognition | Install/select Whisper; no audio leaves the computer |
| Cloud recognition | Yandex SpeechKit service-account API key and permission |
| One key for multiple text models | OpenRouter account/key and available credit |
| Codex subscription route | Installed/logged-in Codex CLI under this Windows user |
| Direct text API | The selected provider's API key and project access |
| Local text AI | Running compatible local server/model and endpoint |

In **Settings → AI and hints**, choose provider, enter its token if needed,
choose hint/report models (or automatic Codex route), save/test. Compatible
routes also need Base URL/model. Testing uses technical metadata, not your
resume/transcript/workspace. A token is not shown back to the browser. LLM tokens
are saved through Windows Credential Manager; legacy configured sources can
still supply credentials separately.

## OpenRouter

1. Sign in at [API keys](https://openrouter.ai/settings/keys).
2. Create a named key and set a spending limit appropriate for this test.
3. Copy its secret into Blatero, select models, then test the connection.
4. If access is rejected, check account credit, key limit and model availability.

The app uses the OpenRouter endpoint with a Bearer key. Key credit limits are
documented in [OpenRouter authentication](https://openrouter.ai/docs/api_reference/authentication).
Never put a key in article text, a shared screenshot, Git or the browser URL.

## Codex / ChatGPT

Install the CLI using [official Codex setup](https://developers.openai.com/codex/cli).
In a Windows terminal run `codex login`, finish the browser sign-in, then check
`codex login status`. In Blatero choose **Codex / ChatGPT subscription** and test.
No API token field is used for this route. See [official authentication](https://learn.chatgpt.com/docs/auth#codex-cli).

Blatero supplies meeting data without enabling agent tools. The available model
and quota depend on the signed-in account/route; use the displayed actual model
when diagnosing hints. A Codex login is not a portable credential to give another
user or a key to place in an unrelated provider's field.

## Direct OpenAI and other API providers

Create your own [OpenAI project API key](https://platform.openai.com/api-keys),
enter it in the **OpenAI** route, select models and test. This is API authentication,
not reuse of a Codex login; check access/quota/billing in your API project.
[Official API setup](https://developers.openai.com/api/docs/quickstart).

For Anthropic or DeepSeek use that provider's own console/key, select the matching
route and test. Do not paste one provider's token into another route. The app
does not silently fall back across providers when authentication fails.

## Yandex SpeechKit

1. Create/select a Yandex Cloud folder and a service account.
2. Grant `ai.speechkit-stt.user` on the folder for recognition; additionally
   `ai.speechkit-tts.user` if you need synthesis.
3. Create a service-account **API key**, with scope `yc.ai.speechkitStt.execute`
   and, for TTS, `yc.ai.speechkitTts.execute`. A scope does not replace a role.
4. Save its secret as one ASCII line in `%USERPROFILE%\.yc-speechkit-key`, without
   an added `.txt` extension. This version has **no UI field** for that key.
5. Select SpeechKit in **Audio and speech**, save, and explicitly permit cloud
   processing if applicable. Run Check all and inspect real recognition results.

The current adapter uses `Api-Key`. An IAM token or authorized-key JSON file is
not interchangeable with that file. It is a **plaintext secret file**, not a
Credential Manager entry. Restrict filesystem access, keep it out of Git/package/
support diagnostics, and revoke/replace a leaked key. Sources:
[SpeechKit authentication](https://aistudio.yandex.ru/en/docs/speechkit/concepts/auth),
[API-key scopes](https://yandex.cloud/en/docs/iam/concepts/authorization/api-key).

Check account roles, scope, account credit/limits and cloud permission if rejected.
For voice synthesis choose a Yandex question-voice route and test the selected
voice. The key/roles alone do not prove audio quality. Studio Gemini is a different
OpenRouter route and does not change ordinary Yandex/Chatterbox voices.

## Local compatible server

Start your own Ollama/LM Studio/vLLM-compatible server, enter its Base URL (for
example `http://127.0.0.1:11434/v1`) and exact installed model name. Leave token
blank only if that server permits it, then test. HTTP is allowed for loopback;
an external endpoint needs HTTPS and cloud permission. A local URL does not
install/download a model by itself. Restrict remote access according to your policy.

## Share a test package

Give the colleague the complete portable ZIP, SHA-256 file and instructions for
which provider/account to use and who pays. Offline RU/EN help is included.
Do not copy your API/Yandex key, Codex auth, `config.json`, voice profile, sessions
or real exported meetings without a separate deliberate data-sharing decision.
