# Materials during a meeting

## Add a file or image

1. Click **+ material** in the meeting toolbar.
2. Add files, drag into the drop area, or paste an image with `Ctrl+V`.
3. The local copy is saved in this meeting without stopping audio.
4. Click **Review before analysis**. Inspect extracted text and local privacy
   findings, exclude files or add terms to hide, then **Recheck locally**.
5. Confirm sending only after checking the recipient, model and exact text.
6. Read what is new, what needs rechecking and what to ask now. These are AI
   proposals, not accepted project decisions.

Images are unselected by default. Visual analysis needs explicit image selection,
pixel masks, recheck and separate image permission. Original OCR of a selected
image is not also sent, so masked information is not leaked as unmasked text.
Local detection cannot guarantee anonymous pixels. [Formats](Meetings-and-Preparation.md).

Limits: 10 MiB upload, 50 materials per meeting, additional extraction/time limits.
Identical name+content is deduplicated; changed content is a separate version.
Unreadable content is not reported as successfully analyzed. Legacy Office needs
LibreOffice; embedded pictures and scanned PDFs are not automatically visualized.

## Screenshot an area

Choose **Capture area**, grant the browser's screen/window permission, then select
a rectangle on the received frame. X/Y/width/height fields support keyboard use.
**Add selected area only** uploads the crop, not the entire frame; the screen
stream ends after a frame. Cancel sends nothing. If unavailable, capture with
Windows and paste into the material panel. Images still require sending review.

In **Shortcuts and new files**, choose `Ctrl+Shift+S`, `Ctrl+Shift+X`, or Off;
default is S. **Handle Print Screen in the active Blatero tab** is a separate
off-by-default option. These are tab-local, ignored in text fields, and do not
install global Windows interception. The system Print Screen action can still
occur; browser permission is required each time.

## New files in the workspace

Enable watching in the material panel after setting a workspace. The first poll
establishes a baseline; subsequent polls, about every 15 seconds, compare sizes
and modification times. Changes that preserve both can be missed. Watching pauses
in a hidden tab/during analysis and must be enabled again for a new meeting.
Secret/service directories are excluded. At most 100 changes appear per batch;
adding them reveals further entries.

Click a changed file to add it to the local queue and review it. Nothing is sent
to AI automatically. Following hints and reports receive up to the latest 12
material analyses/18,000 characters; older analyses remain in the list. Previous
hints and a saved report are not silently rewritten. Rebuild a report explicitly
after context changes.

Copies/results are under `live-materials` in the session. Derived-data cleanup
or deleting the session removes these copies, not workspace originals. A late
job from another meeting cannot publish into the current meeting. Changed files,
model/context/settings invalidate a prior sending review.
