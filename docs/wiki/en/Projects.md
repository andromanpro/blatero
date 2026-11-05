# Projects, tasks and agent outcomes

Projects works locally without AI accounting calls. Open **Projects** in the
shared header. Cards retain goal, method, rationale and next step; source links,
checks and revision history preserve the basis of work. Meeting audio is not
required to use the board.

## Cards and statuses

Create a project, optionally give it a workspace, then create a task. In a card,
title/goal/next step precede method/rationale. **Save card** is also in the sticky
header. Add priority, due date, planned start/duration, evidence or a parent.
Parent/child links stay within a project and cannot form a cycle. Remove such
links before moving a task to another project.

Inbox, Active, Waiting and Review are working statuses. Done needs an explicit
record of what was checked/accepted by an owner or authorized reviewer. A worker
cannot grant itself reviewer rights. Dragging and the keyboard-operable status
menu share the same permissions. Each column loads its own next batch, up to 40,
without resetting other columns. Imported historical statuses remain provisional.

## Close and restore

**Close task** requires a reason. Closed means obsolete/out of current work, not
successful acceptance. All-time Closed search includes the reason. Restore to
Inbox or Active explicitly; reopening an old chat does not restore a task.
Sources, sessions, knowledge, costs, ratings and history remain. Closed tasks are
excluded from current focus/attention/task plan/recall. Independent meetings or
publications stay on the calendar. Earlier acceptance is not erased by closing.

**×** beside a project closes it in the left list with an optional reason and
unfinished-task count. It moves to **Closed projects**, where it can be inspected
or restored. Tasks are not deleted or assigned another status merely because
the project list was tidied. These owner actions persist across browsers.

## Meetings, materials and planning

**Meeting tasks** explicitly links a session and project/card. Folder/name-based
suggestions are labelled and do not create links. **Create meeting card** stores
a source snapshot; **Link selected task** checks revisions. Other project tasks
are separate from those linked to this meeting. Source refresh does not replace
method/status or accept results.

For quick preparation, choose **New meeting**, a project, 1–20 tasks, Moscow date/
time and duration, then **Load context**. Review documents/registries/confirmed
memory/past reports before **Create and open**. It saves agenda, dossier and
source snapshots, adds calendar/task links, but does not record, send invitations
or call AI. Missing folders are warnings, not fabricated context. Creation retries
are idempotent. Closed/merged cards cannot receive a new link without restoration.
[Preparation limits](Meetings-and-Preparation.md).

**Materials** lists meetings, confirmed commitments/questions and optional article
exports. Refresh reads locally; a repeating source read does not copy audio or
send transcripts to AI. Link/create verifies source and task revisions. Repeat
creation for the same material returns its existing card. Unlink preserves the
original basis in history. Changed/removed sources remain visible as changed/
unavailable, not a reason to erase the task.

Articles can be linked in a card's meetings/articles section; an exact root/file
link opens **Edit in Granka** when a local source exists. Published-only entries
offer the public reading link. Identical titles are not the identity. Granka is
optional/read-only from Blatero; task edits do not modify articles or publication
dates. **Plan** uses meetings, task intervals/deadlines and last calendar snapshots.
Computer-local time input and Moscow weekly display differ explicitly. Linked
items with one interval are not double-booked. [Today](Daily-Workspace.md).

## Knowledge, recall and efficiency

Notes require source evidence. Agent proposals remain drafts until a user confirms
content. Freshness is separate from correctness/acceptance. **Open dossier in
library** returns to task sources. [Knowledge library](Knowledge-Library.md).

**Recall goal and method** reveals a card after your own explanation, then asks
for a 0/1/2 self-rating with a 1/3/7-day return. No model grades/stores the retelling;
there are no automatic reminders. This does not change task acceptance.

Efficiency reads optional Neon Legion session logs. Attribution uses explicit
session binding and its time; duplicates/corrections retain canonical identities
and signs. Unknown coverage/prices are not zero. API equivalent is not your plan
invoice, measured human time, productivity, quality or proven savings.

## Agent protocol and turn receipts

The local CLI works while the browser is closed. Worker is the default role.
From the unpacked portable root, replace UUIDs and actual read revisions:

```powershell
.\runtime\python.exe .\app\project_cli.py projects
.\runtime\python.exe .\app\project_cli.py context TASK
.\runtime\python.exe .\app\project_cli.py bind TASK --system codex --session SESSION
.\runtime\python.exe .\app\project_cli.py update TASK --revision N --method TEXT --rationale TEXT --next-step TEXT --system codex --session SESSION --turn TURN
```

Change a session's task only with explicit `bind --switch`. Mutations include
system/session/turn provenance; source hashes and the primary origin of a user
reply are separate fields. Manual legacy commands remain labelled manual, not
assigned a guessed current chat. An environment-based context must provide the
complete three identifiers for that process. Conflict → reread context, not an
unconditional overwrite. Queued delivery retains event ID/time/body on retries.

Finish each substantive turn with the read revision and real result:

```text
project_cli.py finish-turn TASK --revision N --summary TEXT --method TEXT --rationale TEXT --next-step TEXT --system codex --session SESSION --turn TURN
project_cli.py outcome-status --system codex --session SESSION --turn TURN
```

`state=applied` includes an immutable receipt: event, actor identifiers, task,
applied revision, snapshot SHA-256, summary and saved time. It commits in the same
transaction as the card. The same retry returns the original receipt. `queued`
is not a receipt; wait for application and check status. A same-turn later edit
can stale it and needs a new finish. Another actor's edit does not erase history.

Stop checks the current turn/binding and asks for a missing outcome once, then
records a warning rather than looping. It does not write the rationale itself,
verify model correctness, confirm knowledge or accept work. A supported old Codex
client can resolve current-turn metadata from the exact same-session primary
journal header and bounded 8 MiB tail; ended/foreign/unknown data returns no ID.
Never reuse a prior turn ID or infer one from the working directory.

Native Codex/Claude hooks add context and session events. New hook definitions
may require client trust before activation; unsupported dispatchers must pass
context through CLI/API. The hooks installer merges with existing definitions
and saves a backup, not an unconditional replacement. Hermes uses the general
protocol rather than an asserted native adapter.

The Bearer agent API has separate worker keys and permissions; an `actor` field
does not confer rights. Signed file queues are cross-process locked; a lock file
alone does not prove a live lock. Temporary Windows file contention leaves the
event for retry. A stopped session never means a completed card.

## Storage and backup

The data directory's `.projects` contains SQLite, queues, hook errors and local
keys; none are shipped as application source. Stop writers before copying the
whole directory, or use SQLite's backup API. Do not copy only the database while
ignoring a live WAL. Schema migrations are transactional and newer unsupported
schemas are blocked. History, source refresh and classifications do not perform
owner acceptance.
