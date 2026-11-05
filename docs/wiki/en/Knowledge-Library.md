# Knowledge library

Open **Library** (`/projects?view=knowledge`). Depending on configured sources,
it contains project/task dossiers, documents, decision proposals, meeting/article
descriptions and supported agent history. It is a local index, not a request to
upload a disk or give a model access to every project.

## Search and check a source

Choose a project, enter words/prefixes and filter document, decision, dossier or
discussion. Open a fragment and check location, index time, truncation, basis and
state. Follow linked tasks, or **Open dossier in library** from a card. Search
does not extract files or call a model. Source HTML/commands are shown as data,
not executed. Historical versions are not labelled current decisions.

| State | Meaning |
|---|---|
| Source | Original material; not automatic acceptance of its content |
| Proposal | Agent explanation awaiting user review |
| Confirmed | A user confirmed this knowledge, not the related task |
| Latest processed snapshot | Index matches the last processed source version |
| Change queued | A newer version awaits processing |
| Recheck needed | A basis changed/disappeared; old confirmation remains historical |
| Unavailable/update error | Missing/oversized/unreadable source, not successful indexing |

**Record knowledge from this source** saves a proposal with the read basis hash.
The independent worker handles the durable command and the UI waits for its
result. A changed basis/revision requires rereading. **Confirm content** is a
separate user action. Freshness does not prove correctness; old proposals are not
silently changed into current implemented decisions.

## Worker and scope

The worker is a separate process **if configured in this installation**. Login
autostart is an additional opt-in, not a property guaranteed by unpacking portable.
It coalesces changes, resumes journal cursors and reconciles missed notifications.
Hooks send path-only pointers; they do not call AI or parse the whole conversation.

The status panel shows queue, last processing, errors and actual folders. Index/
queue/config are separate from the task SQLite. Notes contain `generated` board
snapshots, editable through cards, `notes` proposals and `history` confirmations.
A local Git snapshot is not remote publication. The package contains no author's
private index, histories, keys or configured project folders.

Document scope is selected project folders/document subfolders, not the whole
drive. MD/TXT/RST/DOCX/PDF and an explicit structured ADR source are supported.
Article catalogs may provide descriptions rather than full text. Ambiguous
project provenance stays unassigned; explicit session/task binding is time-based.
New board projects with a distinct workspace are found on later reconciliation.

Limits: 10 MiB/file, 250,000 extracted characters, 300 PDF pages, 32,000 characters/
message; truncation is labelled. OCR is not enabled here. Tree walk: 300 folders,
depth 6, 3,000 documents. One heavy operation at a time, bounded batches and
12-second document jobs. Heavy work pauses during REC, CPU ≥85% or free memory
below 768 MiB. Pause keeps search and small note commands available.

Plain/Zstandard Codex and Claude journals keep the same session identity and
decompressed cursor; plain wins when both copies exist. Zstandard processing
needs Python 3.14, not the portable 3.12 runtime. Bounded caches use 128 MiB per
archive/10 seconds/256 MiB total and are removed after reading. Corrupt/truncated/
oversized archives remain errors, not a successful empty import. Originals stay.

## Optional setup

First create board projects and their workspace paths. From the portable root,
replace the example folders with your real data/index/notes paths:

```powershell
.\runtime\python.exe .\app\knowledge_cli.py --home 'C:/BlateroData/.knowledge' init --board 'C:/BlateroData/.projects/projects.sqlite3' --notes 'C:/BlateroNotes' --without-history
.\runtime\python.exe .\app\knowledge_worker.py --home 'C:/BlateroData/.knowledge'
```

Use the same index path as the panel; set `BLATERO_KNOWLEDGE_HOME` before starting
Blatero if using another location. Do not initialize an existing configuration
again. Inspect `project_roots`, `extra_files`, `history`, `session_providers` in
its local config before collecting. `--without-history` avoids agent histories;
connecting private histories requires a deliberate source setup.

Optional `knowledge_cli.py --home PATH install-startup` with the same Python
creates a per-user VBS startup launcher and reports its path. Remove that exact
launcher to disable autostart; first stop the worker. Index/originals remain.
No always-on NAS service is included. See source-installation documentation for
advanced adapters; normal meetings do not require this setup.

## Agent notes

Use `search`, then `detail` and actually read the basis before `propose --json-file`.
A note requires title/body/kind, project/task and `references:[{id,content_hash}]`;
editing also needs ID/revision. Agents create drafts, not owner confirmations.
The API returns command ID/state; poll to complete/failed. Retry the same ID/body,
and reread on conflicts. Automatic paid knowledge synthesis is not enabled.
