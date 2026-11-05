# Installation, models, updates and recovery

## Portable Windows x64

Download the complete portable ZIP and SHA-256, compare the checksum, extract
everything into a dedicated folder, then start `Blatero.exe`. Choose Start or
Open help. No system Python, Word, Node.js or LibreOffice is required for basic
startup/native DOCX. The root contains launcher, short README, `app`, `docs`,
`runtime` and `_integrity`; technical files stay inside these folders.

The launcher uses the Windows UI language for its labels/help when available.
**Check installation** checks required files and writable data/token locations;
it is not a real microphone, STT or AI quality test. Run Check all in the app.
If the launcher cannot start, `app/start_blatero.cmd` is the fallback entry point.
Offline help opens at `docs/wiki/Home.html` or `docs/wiki/en/Home.html`.

Meeting data uses the actual Windows Documents known folder's `Blatero`
subdirectory, including redirected/OneDrive folders. Removing application files
does not remove this data. Credentials are configured per user on the recipient's
machine; they are not bundled. Do not run from inside the ZIP viewer.

Optional components: LibreOffice for legacy DOC/XLS/PPT/RTF/VSD, Codex CLI for its
login route, chosen speech/voice models and a configured independent knowledge
worker. Install only what you use. Chatterbox has a separate environment; the
portable runtime uses virtualenv where needed.

## Integrity and local access

The portable manifest covers all payload files and is signed with the owner's
Ed25519 release key. To verify an archive using the bundled validator:

```powershell
.\runtime\python.exe .\app\ci\build_windows_portable.py --verify 'C:/Downloads/blatero-portable-VERSION-win-x64.zip'
```

This is package-integrity signing, **not public Authenticode/MSIX publisher trust**.
Windows SmartScreen warnings are still possible. A new publisher certificate is
not part of this release. Use the owner's supplied checksum/public key/channel,
not an untrusted replacement key from the same suspicious download.

The launcher prepares a random local access token under `%LOCALAPPDATA%/blatero`,
waits for readiness and opens a browser session. The initial token is removed
from the address bar after sign-in; do not share that first URL/log. Host/Origin
and token guards protect local actions. Do not expose the port directly to an
untrusted LAN/Internet. Local browser auto-login is a deliberate option, not a
guarantee for all installations.

## Local models

Open **Settings → Maintenance → Local models**. Inspect purpose, license, ready/
partial/missing state, requirements, size and location before install/remove.
Whisper uses managed model folders; an unrelated shared Hugging Face cache is
not deleted. Removing Chatterbox keeps its separate voice sample. A voiceprint
or voice sample has its own deletion action. Active recognition/model usage
blocks unsafe removal. Source installations must install into the runtime that
actually hosts Blatero, not an arbitrary system Python.

## Updating portable

Use a complete portable package, not a source ZIP.

1. Stop recordings and background operations, then shut down the server.
2. Download the new portable ZIP, verify SHA-256 and extract it into a new folder.
3. Find the existing data path under **Settings → Maintenance → Installation
   and updates**. Back up that data folder separately from the application.
4. Start the new `Blatero.exe`. The default Documents/Blatero folder reconnects
   automatically. For a custom path, start from CMD with a variable limited to
   that command window:

   ```bat
   set "BLATERO_DATA_DIR=F:\My meetings\Blatero"
   "F:\Apps\Blatero-NEW-VERSION\Blatero.exe"
   ```

   Substitute your own paths. The portable launcher has no data-folder chooser.
   Check meetings, settings and the new version's offline help.
5. Point your shortcut to the new executable. Keep the old application folder
   until verification is complete. Do not delete the data folder.

Do not copy `app`, `runtime` or help over an old installation. The update manager
rejects source-only packages in portable to avoid mixed code, dependencies and
help versions. An incompatible package staged by an older version is cancelled
at startup; the staged ZIP remains in the updates directory.

To return from 1.0.2-rc.7 to 1.0.1, stop the new version and any separately
running Library worker first. Let pending note saves finish, then launch the
old `Blatero.exe` with the same data folder. Do not restore an older data
backup over it: that would remove cards and notes created after the upgrade.
Do not run both versions against the same data at once.

## Source installation updates and rollback

Open **Maintenance → Installation and updates**, choose a local release ZIP,
check signature/version/file list, then stage it. Verification rejects wrong
hashes/sizes, extra files, path traversal and links. A running server is not
overwritten. Stop recordings/jobs and restart explicitly to apply the staged
action. The previous code and a durable transaction journal support recovery
to entirely old or entirely new code after an interrupted application.

Source updates do not run pip into an active environment. If pinned dependencies
change, use the complete compatible portable/installer instead; the source
update is rejected/rolled back rather than leave a mixed runtime. The rollback
panel names the available previous version; stage it and restart while idle.
Git source checkouts are not replaced by release ZIPs.

Rollback replaces program files, not the data folder. Cards and notes
written in 1.0.2-rc.7 remain readable in 1.0.1. If the Library is writing a
note or has an unresolved save journal, rollback waits until it is resolved.
Do not delete the journal manually.

For a full installer upgrade with changed dependencies, install into a new
application folder and select the existing data folder. Stop the server and back
up data first. Check meetings and settings in the new installation, then update
the shortcut. Keep the old program until verification is complete; do not copy
its `.venv` over the new environment.

## Interrupted data or jobs

After a crash, recovery distinguishes incomplete WAV/JSONL from completed data.
Repair first makes a byte-identical backup and only fixes a provably incomplete
tail. You may leave files unchanged and label the session interrupted. Unknown
internal corruption needs manual review; insufficient space blocks repair.
Continuing creates a new segment and does not overwrite old audio.

Background jobs use process/heartbeat/locks/generation identity. A stale heartbeat
alone does not justify taking over a live process. A complete saved report draft
with the matching source hash can return to review without another AI request.
An uncertain paid operation is not automatically retried without confirmation.
Old-session jobs cannot publish into a new session.

Session-schema migrations save metadata backups/journals atomically and can retry
after interruption. A session from a newer unsupported schema is blocked without
changing its files. [Troubleshooting](Troubleshooting.md).
