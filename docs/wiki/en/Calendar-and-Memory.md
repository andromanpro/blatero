# Calendar and project memory

## Events and the common plan

The calendar has day/week views with actual event durations. A calendar event
is a schedule, not an audio recording. Preparing it creates a session only after
you check role, topic, client and workspace. Manual events accept time, title,
format, participant/company and optional folder; they do not send invitations
or call AI on their own.

Sources include local schedule, Google Calendar OAuth and compatible CalDAV.
Calendar secrets/refresh tokens are in Windows Credential Manager. Insecure
remote HTTP is rejected; loopback HTTP is for local development. A failed source
does not hide successful sources. Removing a connection removes its secret/cache,
not meetings already created from it.

The common **Plan** combines meetings, task intervals/deadlines and optional
Granka publication dates. Task time input uses computer timezone; the weekly
overview is Moscow time. A linked task/meeting with the same interval is not
double-booked. The board reads the last calendar snapshot, not a new authorization
or automatic synchronization. See [Projects](Projects.md).

## Confirm agreements after a report

Memory stores decisions, actions/promises, open questions and confirmed facts.
A report is not memory by itself. Open **Review agreements** beside a completed
report, including an older one. Candidates come from explicit sections locally;
no new AI generation is needed.

1. Select relevant items; correct text, owner and deadline.
2. Expand **Basis in report** to check the source.
3. Choose project for project-specific continuity, client for cross-project facts.
4. Click **Confirm and save**. Only these selected items become confirmed memory.

Unselected items remain drafts after refresh. **Later** closes without acceptance.
Rejecting remaining proposals is a separate confirmation and does not erase the
report/confirmed memory. Empty owner/date is not invented. If there are no
proposals, add an item manually or explicitly mark nothing to save.

Changed report/project/draft in another tab blocks stale confirmation. A new
draft archives the old version. Legacy drafts without a source fingerprint stay
labelled for source checking. Repeating a save does not duplicate it or reopen
an already closed commitment. Test meetings do not write into work memory through
this route. Confirming memory does not accept tracker tasks or rewrite WAV/text.

## Reuse and edit

Identity uses explicit client/project or a normalized workspace path. A moved
repository can be connected to an existing profile without two divergent histories.
Next preparation uses confirmed decisions/facts, open questions, outstanding
actions/dates and relevant workspace changes—not every old transcript.

Edits/status/date changes use revisions; a stale tab conflicts. The last 20
revisions remain. ISO dates and `DD.MM.YYYY` produce overdue/today/soon labels.
Other date text stays a note rather than an invented calendar date.

Clearing records keeps workspace/snapshot for future diffs. **Forget project/
client completely** also removes history, path, snapshots and aliases. Both need
confirmation; they are not interchangeable.

Workspace re-analysis compares added/changed/deleted/unchanged files. Only the
selected diff, deletion list and previous map are sent through privacy review.
An empty folder is not treated as successful preparation. Secret data and local
absolute paths are excluded by the outgoing boundary, but manually review risk.
