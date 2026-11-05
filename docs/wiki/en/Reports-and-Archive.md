# Reports, archive and deletion

## Create and review

After Stop choose **Finish and create report**. The panel shows the real stage:
source check, AI draft, conclusion review, document export. Elapsed time comes
from the durable operation and returns after page refresh. A 1–3-minute guide is
not a progress percentage or a promise of remaining time.

Empty transcripts are rejected before generation. AI writes `report.draft.md`
with a self-audit; local checks connect conclusions with events, voices and
confidence. Changing transcript, roles, context, model or prompt invalidates the
old draft. The previous saved document remains accessible with a stale label.

Review warnings for missing sides, uncertain speakers, low STT confidence,
unresolved audio issues, unsupported conclusions or contradictions. Missing
confidence in an old/imported event is **unknown**, not 0% accuracy. Listen to
relevant moments rather than editing every phrase blindly.

Each conclusion can be confirmed or excluded. Exclusion stays in local audit,
not the final report; editing a conclusion clears its previous review decision.
Rebuild after source corrections is a new AI call. Confirming a valid draft
exports DOCX locally without another call. **Create with limitations** explicitly
includes known limitations instead of claiming a fully verified report.

Internal interviewer discussion after the candidate leaves, unverified personal
assumptions, service instructions and excluded conclusions must not become final
evidence. Check the boundary of the substantive interview yourself.

## Read and export

The center **Report** tab provides formatting, tables, contents and text sizing.
Download DOCX, print, or open the result folder without generation. External
images/active links in report prose are not executed. Native DOCX export needs
neither Word, LibreOffice nor Node; a separately configured converter remains
available in installations that use it. Image captions/link text are retained,
not arbitrary fetched files.

The filename includes meeting type, participant/topic and date. Correct meeting
metadata first. Re-generation archives the machine report; a manually renamed
DOCX is not overwritten. Local folder opening is loopback-only.

Timestamps/evidence links are **off by default**. When explicitly enabled they
point to local `evidence.html` and audio/events, not public Internet links. Source
workspace absolute paths are not exported as evidence identifiers.

## Memory and tasks are separate

**Review agreements** extracts proposals locally from report sections, without
another AI call. Select/edit/confirm items before they become project/client
memory. A report alone does not populate memory. Task linking/sync preserves
goal/method/status until the user explicitly changes or accepts them. Stopping a
meeting or accepting memory is not task acceptance. [Memory](Calendar-and-Memory.md).

## Archive and encrypted transfer

Archive filters work/test meetings. Open transcript, report, audio, Replay or
data/transfer for the selected session. A WAV can be deleted without deleting
text/report; active capture/background work blocks deletion.

Export creates a `.blatero-session` AES-256-GCM container; a passphrase derives
the key via scrypt and is not stored. The header/random name does not disclose
participant/topic/text. Before download the application re-decrypts and verifies
the complete manifest. Import checks password, paths, counts, sizes and SHA-256,
then publishes a new unique session. Tampering, extra files, links and traversal
are rejected, not partially imported. Keep your passphrase separately.

An exported package is an independent copy. Purging a session does not silently
delete its transfers. Remove a specific package through its separate action.

## Delete or retain

In **Settings → Maintenance → Meeting data**, calculate a plan for audio, video/
previews, transcript, reports/evidence, derived results or the whole session.
Check file counts/sizes/examples and type the exact session folder to confirm.
Deletion is irreversible: export and verify a backup first when needed.

Retention is configured per category. `0` means no expiry. Calculate/review the
queue, then explicitly apply; current/active sessions and jobs are protected.
**Clear meeting results** is for a fresh test run: it keeps metadata, resume,
dossier and scenario but deletes generated results. It is not a general backup.

The personal-data map lists known local stores. It cannot remove copies in
Downloads, backups, shadow copies, external applications or Credential Manager
for you. Local working files are not encrypted at rest by Blatero; use OS disk
encryption according to your requirements.
