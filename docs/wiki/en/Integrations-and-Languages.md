# Integrations and languages

Blatero works without Neon Legion, Granka or Motivellium. Connections are off by
default and apply to the local project database, not one meeting. The local user
controls them; enabling does not prove an application is installed/reachable.

## Enable a local connection

Open **Settings → Connections** (the board's shared Settings also offers them),
choose the source and save. Refresh Materials for Granka or open Efficiency for
Neon. Disabled sources are not scanned/run. Existing snapshots/links remain;
no new cards/dates are created from disabled sources. Originals stay unchanged.

**Neon Legion** connects local AI usage logs to tasks through exact sessions and
binding times. It reports API-equivalent usage, not your subscription invoice
or measured human time/savings. Unknown price/coverage is not zero. Default is a
sibling `neon-legion` folder; `BLATERO_NEON_ROOT` can select another before startup.

**Granka** is a separate article editor/version/publishing tool. Blatero reads its
catalog and connects articles to cards; editing remains in Granka. This does not
send meeting reports to a channel, modify articles or publish automatically.
Default is sibling `granka` with `tools/blatero_export.py`; overrides are
`BLATERO_GRANKA_ROOT` and `BLATERO_GRANKA_PYTHON`. The local exporter runs only when
enabled. An error keeps the earlier snapshot visibly stale/unavailable.

**Motivellium** is introduced under **Help → Other applications** as a separate
video tool. No direct bridge exists in this version, so there is no fake enable
switch or requirement to install it for meetings.

## RU/EN

In meeting Settings choose **Appearance → Interface language**; on the board use
shared Settings. The preference is per browser, shared by its meeting/board pages,
and applies without a server restart. Forms keep input/focus/selection, and
changing language is not an operation such as install, save, analyze or delete.

Navigation, settings, meeting/results, task workflows, studio, library, labs and
maintenance have owned RU/EN labels. An external/native error can remain in its
original language. Documents, names, paths, keys, model identifiers and user-
entered text are not interface phrases and are not translated automatically.

English help is offline beside Russian help, with a language link in the top
navigation. It does **not** switch live STT, meeting/AI-response language or TTS.
The present live recognizer profiles and local name detector are Russian-focused.
No cloud/voice permissions or personal settings are reset by this choice.
