You are now acting as a senior QA engineer + frontend engineer + audio editor UX engineer.

The current DiarizeStudio UI has already been redesigned, but it MUST NOT be considered complete just because the UI looks better.

Your task is to:

1. Open and test the actual running application in a real browser.
2. Use Playwright/browser automation to interact with the application.
3. Upload a REAL WAV audio file.
4. Run the actual diarization + ASR pipeline.
5. Verify that the real waveform, speakers, timestamps, transcript and speaker segments appear.
6. Verify that the timeline behaves like a professional video/audio editor.
7. Identify and fix all UI/interaction problems discovered during testing.
8. Re-run the complete test after every significant fix.
9. Take screenshots during testing to verify the visual result.
10. Do not claim success based only on source-code inspection.

The application is DiarizeStudio.

The main purpose is:

Audio
→ Diarization
→ Speaker timeline
→ Telugu/English transcription
→ Editable speaker segments
→ Export

The timeline is the most important part of the application.

============================================================
1. FIRST: INSPECT THE EXISTING APPLICATION
============================================================

Before changing anything:

Inspect:

- package.json
- frontend structure
- backend structure
- routing
- state management
- audio player
- waveform implementation
- timeline implementation
- transcript implementation
- diarization integration
- ASR integration
- WebSocket implementation
- upload implementation
- API endpoints
- session data model
- turn/segment model
- export implementation

Determine:

- how the frontend is started
- how the backend is started
- what URL the application runs on
- what API endpoint receives audio
- what endpoint starts processing
- how processing status is returned
- how diarization results are represented
- how ASR results are represented
- how timeline data is generated

Do NOT rewrite working backend functionality unnecessarily.

============================================================
2. USE PLAYWRIGHT FOR REAL BROWSER TESTING
============================================================

Use Playwright if it is already installed.

If it is not installed and the project allows it:

install/configure:

@playwright/test

Use Chromium.

Create an actual E2E test suite.

Example:

tests/e2e/diarizestudio.spec.ts

The tests must operate against the actual running application.

Do not mock the main diarization/ASR pipeline for the primary acceptance test.

Mocks may be used for isolated UI unit tests, but NOT for the main end-to-end test.

============================================================
3. FIND A REAL WAV FILE
============================================================

Search the repository for:

.wav
.mp3
.m4a
.mp4

Look in:

tests/
fixtures/
samples/
public/
assets/
data/

If an existing test WAV is available, use it.

If no suitable WAV exists:

DO NOT invent a fake WAV.

Report:

"REAL AUDIO FIXTURE REQUIRED"

and identify exactly where the test expects the WAV.

If a user-provided WAV is available, use that.

The primary E2E test must use actual audio.

============================================================
4. VERIFY APPLICATION STARTUP
============================================================

Start the actual application.

Verify:

Frontend loads successfully.

Backend loads successfully.

No critical console errors.

No failed API requests caused by frontend bugs.

Capture:

- browser console
- page errors
- failed network requests
- WebSocket errors

The test must fail if there are critical errors.

============================================================
5. INITIAL UI TEST
============================================================

Open the application.

Verify these elements exist:

- application header
- session name
- save state
- search
- tools
- live mic
- upload
- export
- editor toolbar
- waveform/timeline area
- speaker panel
- transcript panel

Verify:

No overlapping UI.

No clipped text.

No broken icons.

No horizontal page overflow.

No giant unused areas.

No placeholder debug text.

No raw JSON visible.

No console errors.

Take a screenshot:

01-initial-ui.png

============================================================
6. UPLOAD REAL WAV
============================================================

Locate the actual upload input/button.

Upload the real WAV file using Playwright.

Example:

await page.locator('input[type=file]').setInputFiles(wavPath)

or interact with the visible Upload button.

Verify:

- upload begins
- progress is shown
- file name appears
- duration is detected
- waveform is generated from the REAL AUDIO
- processing starts

IMPORTANT:

The application must NOT show a decorative/mock waveform.

The waveform must represent the actual audio duration.

============================================================
7. VERIFY AUDIO METADATA
============================================================

After upload verify:

- duration > 0
- sample rate information if available
- channels
- file name
- audio loading state

The UI currently showed:

00:00.0 / 00:00.0

while a waveform was visible.

This MUST be fixed.

If real audio is loaded, the duration must display correctly.

Example:

00:00.000 / 03:42.581

NOT:

00:00.000 / 00:00.000

============================================================
8. VERIFY WAVEFORM
============================================================

The waveform must correspond to the actual audio.

Verify:

- waveform has non-zero duration
- waveform width corresponds to audio duration
- playback cursor exists
- cursor starts at 0
- waveform can be clicked
- clicking waveform seeks audio
- playback cursor moves during playback

Test:

1. click around 25% of waveform
2. verify current time changes
3. click around 50%
4. verify current time changes
5. press Play
6. wait
7. verify current time increases

Take:

02-audio-loaded.png

============================================================
9. WAIT FOR REAL DIARIZATION
============================================================

Wait for the actual processing state.

The UI must clearly show:

Processing

Diarization
Transcription
Alignment

If backend exposes progress, display real progress.

Do NOT display fake progress percentages.

If exact progress is unavailable:

show:

Processing diarization...

instead of inventing:

87%

============================================================
10. VERIFY SPEAKERS
============================================================

After processing:

Verify actual diarization results exist.

Example:

Speaker 0
Speaker 1

or:

Mohan
Priya

depending on current naming.

Verify:

speaker count > 0

if the test audio contains multiple speakers.

IMPORTANT:

Do not create fake speaker lanes just to make the UI look complete.

If the model returns zero speakers:

display:

"No speakers detected"

and investigate why.

Do not hide the failure.

============================================================
11. CRITICAL TIMELINE REQUIREMENT
============================================================

The timeline MUST behave like a professional video editor.

Do NOT create a simple list of speaker segments.

The structure must be:

TIME RULER
──────────────────────────────────────────────────────

AUDIO TRACK
──────────────────────────────────────────────────────
██████████████████████████████████████████████████████

SPEAKER 0
──────────────────────────────────────────────────────
██████████████                  █████████████

SPEAKER 1
──────────────────────────────────────────────────────
              █████████████████

SPEAKER 2
──────────────────────────────────────────────────────
                              ███████████

TRANSCRIPT / CAPTION TRACK
──────────────────────────────────────────────────────

This must visually communicate:

WHO spoke
WHEN they spoke
HOW LONG they spoke
WHICH speakers overlapped
WHERE the speaker changed

============================================================
12. TIMELINE TIME RULER
============================================================

The ruler must be based on REAL audio duration.

Example:

00:00
00:05
00:10
00:15
00:20
00:25
...

When zoomed:

00:10.000
00:11.000
00:12.000
00:13.000

At high zoom:

00:12.000
00:12.100
00:12.200
00:12.300

The ruler must dynamically adapt to zoom.

Do not hard-code timestamps.

============================================================
13. SINGLE HORIZONTAL COORDINATE SYSTEM
============================================================

This is extremely important.

The following must share the SAME horizontal time coordinate:

- waveform
- time ruler
- speaker lanes
- transcript segments
- playhead
- selection region
- markers

If:

10 seconds = X coordinate 300px

then every track must use that same mapping.

Do NOT implement each track with independent scrolling.

Scrolling the timeline must scroll all tracks together.

Zooming must zoom all tracks together.

============================================================
14. SPEAKER COLORS
============================================================

Every detected speaker must receive a persistent color.

Example:

Speaker 0
BLUE

Speaker 1
GREEN

Speaker 2
ORANGE

Speaker 3
PURPLE

The exact colors are up to the design system.

But:

- colors must be visually distinct
- not neon
- accessible
- persistent for the entire session

The same speaker must always have the same color.

============================================================
15. SPEAKER SEGMENTS
============================================================

Each speaker segment must be represented by a real editable timeline block.

Example:

Speaker 0:

┌─────────────────────────────┐
│ Mohan                       │
│ 00:12.200 → 00:18.700       │
└─────────────────────────────┘

The block must contain:

- speaker name
- optional transcript preview
- start time
- end time when selected

Hover:

show:

Speaker: Mohan
Start: 00:12.200
End: 00:18.700
Duration: 00:06.500

============================================================
16. SEGMENT RESIZING
============================================================

Users must be able to resize a speaker segment.

Left edge:

drag → change start time

Right edge:

drag → change end time

While dragging:

show a vertical guide.

Show exact time:

Start: 00:12.200

or:

End: 00:18.700

Use frame/time snapping appropriate to the audio resolution.

Do NOT make resizing imprecise.

============================================================
17. MOVE SEGMENT
============================================================

Allow moving a segment when appropriate.

Dragging the center should move the segment.

But prevent accidental movement.

Use a clear cursor:

grab

while hovering.

Show a preview before committing.

============================================================
18. SPLIT SEGMENT
============================================================

This is essential.

User should be able to:

1. move playhead to 00:15.500
2. select speaker segment
3. click Split

Result:

Before:

Speaker 0
████████████████████████

After:

Speaker 0
████████████

Speaker 0
            ███████████

Both retain:

same speaker

but different timestamps.

The transcript must also be updated appropriately.

============================================================
19. MERGE SEGMENTS
============================================================

If two adjacent segments belong to the same speaker:

Speaker 0
████████

Speaker 0
        ████████

Allow:

Merge

Result:

Speaker 0
████████████████

Merge must update:

- timeline
- transcript
- timestamps
- export

============================================================
20. REASSIGN SPEAKER
============================================================

Right-click or toolbar action:

Change Speaker

Example:

Speaker 0
↓
Speaker 1

The segment changes color immediately.

Transcript speaker changes immediately.

Speaker statistics update.

Export reflects the change.

============================================================
21. OVERLAPPING SPEECH
============================================================

Test the timeline using audio containing overlapping speakers.

If:

Speaker 0:
████████████████

Speaker 1:
       ███████████████

the overlapping region MUST remain visible.

Do not force the second speaker to disappear.

Use stacked lanes.

Show:

OVERLAP

when selected.

============================================================
22. PLAYHEAD SYNCHRONIZATION
============================================================

The playhead must span the complete timeline.

Example:

                    │
                    │
                    ▼
00:00    00:10    00:20    00:30
─────────│─────────│─────────│──────
Audio    │         │
Speaker0 │█████████│████████
Speaker1 │     ████│████
Transcript       │
                 ▼

When audio plays:

playhead moves smoothly.

When user clicks timeline:

audio seeks.

When user clicks transcript:

playhead jumps.

Everything stays synchronized.

============================================================
23. CLICK TIMELINE → TRANSCRIPT
============================================================

Click a speaker segment.

Expected:

1. segment becomes selected
2. corresponding transcript turn becomes selected
3. transcript scrolls into view
4. audio seeks to segment start
5. inspector updates

This must work reliably.

============================================================
24. CLICK TRANSCRIPT → TIMELINE
============================================================

Click transcript turn.

Expected:

1. turn becomes selected
2. timeline scrolls to corresponding timestamp
3. segment becomes highlighted
4. playhead moves
5. speaker lane becomes highlighted

============================================================
25. AUDIO PLAYBACK
============================================================

Test:

Play
Pause
Seek
Previous
Next
Speed

Verify actual audio playback.

Playback speed must NOT change timeline time calculations.

The timeline always represents real media time.

============================================================
26. ZOOM
============================================================

Implement professional timeline zoom.

Controls:

-

+

Fit

100%

Allow:

Ctrl + mouse wheel

or:

mouse wheel over timeline

Zooming must:

- preserve playhead location where possible
- preserve selected segment
- update time ruler
- scale all tracks together

Test:

Fit entire audio.

Then zoom to:

2x
4x
8x
16x

At every zoom level:

segments must remain correctly positioned.

============================================================
27. HORIZONTAL SCROLL
============================================================

Long audio must not compress into unreadable tiny blocks.

For a 1-hour recording:

timeline should remain horizontally scrollable.

The user should be able to inspect:

00:00 → 01:00

with proper zoom.

Do not shrink a 1-hour timeline so that every speaker block becomes a 2-pixel line.

============================================================
28. TIMELINE MINIMAP
============================================================

If the recording is long:

show a compact overview/minimap.

Example:

██████░░████████░░████████████████░░███

Current viewport:

       [──────────]

Dragging the viewport moves the main timeline.

============================================================
29. TRANSCRIPT TRACK
============================================================

Add a transcript/caption lane associated with the timeline.

Example:

Transcript

┌──────────────────┐
│ Hello everyone   │
└──────────────────┘

                     ┌────────────────────┐
                     │ How are you?       │
                     └────────────────────┘

The transcript blocks should align horizontally with their actual timestamps.

============================================================
30. TELUGU + ENGLISH
============================================================

The application must correctly display code-mixed transcripts.

Example:

నేను office కి వస్తాను, but evening meeting ఉంది.

Do NOT force everything into English.

Do NOT transliterate automatically.

Do NOT replace Telugu with boxes/squares.

Verify browser rendering of Telugu.

Use:

Noto Sans Telugu

or another verified Telugu-capable font.

============================================================
31. TRANSCRIPT EDITING
============================================================

Double click a transcript block.

Allow inline editing.

Example:

Original:

నేను office కి వస్తాను.

User edits:

నేను office కి 5 PM కి వస్తాను.

Save.

Verify:

- transcript updates
- underlying turn updates
- export updates
- undo works

============================================================
32. UNDO / REDO
============================================================

Test:

Edit text

Ctrl+Z

Expected:

original text restored.

Ctrl+Shift+Z

Expected:

edited text restored.

Also test undo for:

- split
- merge
- resize
- speaker reassignment
- speaker rename

============================================================
33. SPEAKER MANAGEMENT
============================================================

Right sidebar:

SPEAKERS

● Mohan
42.3 min
18 turns

● Priya
31.7 min
14 turns

Each speaker:

Rename
Change color
Mute
Solo
Merge

Speaker total time must be calculated from actual segments.

Do not use hard-coded values.

============================================================
34. SPEAKER MERGE
============================================================

Test:

Speaker 0
Speaker 2

Select:

Merge Speakers

Result:

All Speaker 2 segments become Speaker 0.

Timeline colors update.

Transcript updates.

Statistics update.

Export updates.

Raw model output remains preserved.

============================================================
35. INSPECTOR PANEL
============================================================

When a segment is selected:

show:

SEGMENT

Speaker:
Mohan

Start:
00:12.320

End:
00:18.720

Duration:
00:06.400

Language:
Telugu + English

Confidence:
if available

Overlap:
Yes/No

Actions:

Edit
Split
Merge
Reassign
Reset

============================================================
36. RIGHT CLICK CONTEXT MENU
============================================================

Right-click segment:

Play From Here

Edit Transcript

Change Speaker

Split At Playhead

Merge With Previous

Merge With Next

Adjust Start

Adjust End

Add Marker

Reset To Model Output

Delete Segment

============================================================
37. MARKERS
============================================================

Allow timeline markers:

Important
Question
Action Item
Review

Marker:

🔖

Click:

seek to timestamp.

============================================================
38. TRACK CONTROLS
============================================================

Each speaker track should have:

speaker icon
speaker name
color indicator
mute
solo
lock

Example:

👤 Mohan
[ M ] [ S ]

Audio track:

🔊 Master Audio
[ M ] [ S ]

Do not overcomplicate the UI.

============================================================
39. LOCKING
============================================================

Allow optional track locking.

When locked:

timeline segments cannot accidentally move.

Useful for preventing accidental edits.

============================================================
40. AUTO-SCROLL
============================================================

During playback:

timeline follows playhead.

Provide:

[✓ Follow Playhead]

When user manually scrolls away:

automatically disable follow mode or provide a clear state.

During live recording:

default:

Follow Live

User can disable it.

============================================================
41. LIVE MODE
============================================================

Test live microphone.

When active:

🔴 LIVE

Audio should enter timeline continuously.

New speaker segments should appear.

Interim transcript:

gray/italic.

Final transcript:

normal.

Do not continuously re-render the whole application.

============================================================
42. PROCESSING STATES
============================================================

During processing:

Do not show fake timeline segments.

Instead:

Waveform:
visible if audio is available.

Diarization:

Processing...

ASR:

Processing...

Alignment:

Waiting...

Once actual results arrive:

replace placeholders with actual results.

============================================================
43. ZERO-RESULT STATE
============================================================

If no diarization result exists:

Do NOT show:

fake speaker lanes.

Show:

"No speaker segments yet"

If waveform exists:

keep waveform.

If transcript exists but diarization failed:

show transcript normally and indicate:

"Speaker attribution unavailable."

============================================================
44. VISUAL TESTING
============================================================

After processing the real WAV:

Take screenshots:

01-initial.png
02-uploaded.png
03-processing.png
04-diarized-timeline.png
05-selected-speaker.png
06-zoomed-timeline.png
07-editing-segment.png
08-overlap.png
09-transcript.png
10-final.png

Inspect these screenshots.

Look specifically for:

- alignment
- clipping
- incorrect colors
- timeline overflow
- overlapping elements
- unreadable text
- incorrect timestamps
- waveform/timeline mismatch
- broken Telugu rendering
- empty areas
- inconsistent spacing

============================================================
45. AUTOMATED ASSERTIONS
============================================================

Playwright must assert actual values.

Examples:

expect(duration).toBeGreaterThan(0)

expect(speakerCount).toBeGreaterThan(0)

expect(transcriptTurns).toBeGreaterThan(0)

expect(timelineSegments).toBeGreaterThan(0)

expect(waveform).toBeVisible()

expect(playhead).toBeVisible()

Do NOT use:

expect(page).toHaveScreenshot()

as the only test.

Functional assertions are required.

============================================================
46. TIMESTAMP VALIDATION
============================================================

For every timeline segment:

assert:

start >= 0

end > start

end <= audioDuration

No segment may exist outside the audio duration.

Example:

Audio duration:

120.5 sec

Invalid:

start = 130

end = 145

The application must reject or correct invalid data.

============================================================
47. CROSS-VIEW CONSISTENCY TEST
============================================================

This is a mandatory test.

Choose a random timeline segment.

Read:

speaker
start
end
text

Then find corresponding transcript.

Verify:

speaker matches

start matches

end matches

text matches

Then edit the transcript.

Verify:

timeline-linked data updates.

Then change speaker.

Verify:

timeline color changes.

Then resize segment.

Verify:

transcript timestamp changes.

This confirms that the application has ONE source of truth.

============================================================
48. EXPORT TEST
============================================================

After editing:

Export JSON.

Read exported JSON.

Verify it contains:

speaker
start
end
text
translation if enabled

Then export:

SRT

VTT

TXT

DOCX

Verify files are created.

Verify timestamps are valid.

Verify edited text is present.

============================================================
49. PERFORMANCE TEST
============================================================

Measure:

Initial load

Upload time

Processing time

Time to first transcript

Timeline rendering

Interaction latency

Do not allow:

entire timeline re-render on every playhead frame.

Do not update React state at 60+ times per second unnecessarily.

Use requestAnimationFrame or direct rendering where appropriate.

Virtualize long transcript lists.

============================================================
50. IMPORTANT: DO NOT FAKE SUCCESS
============================================================

You MUST NOT say:

"Everything works"

unless the actual browser test confirms it.

If something fails:

report:

FAILED

Component:
Timeline

Problem:
Speaker segments not rendered

Evidence:
Screenshot / console error / network response

Root cause:
...

Fix:
...

Then fix it and rerun the test.

============================================================
51. IF BACKEND IS BROKEN
============================================================

If upload works but:

ASR fails

or

Diarization fails

do NOT replace it with mock results.

Instead:

identify the exact backend/API failure.

Fix the integration if the problem is in the application.

If credentials/model access are genuinely unavailable:

report the exact blocker.

The UI should still correctly represent the unavailable state.

============================================================
52. DO NOT USE MOCK TIMELINE DATA
============================================================

This is critical.

Do NOT generate:

Speaker 0
████████

Speaker 1
     ███████

just to make the screenshot look good.

Every block must originate from:

real diarization output.

Every transcript block must originate from:

real ASR output.

Every waveform must originate from:

real audio.

============================================================
53. CURRENT UI PROBLEM TO FIX
============================================================

The current screenshot shows:

- professional-looking top bar
- waveform
- timeline area
- speaker panel

BUT:

"Speakers (0)"

"00:00.000 / 00:00.000"

"No diarization speakers detected yet"

and an enormous empty transcript area.

The application currently needs to prove that the complete data pipeline actually reaches the UI.

Do NOT optimize only the appearance.

Verify:

REAL AUDIO
↓
REAL DURATION
↓
REAL WAVEFORM
↓
REAL DIARIZATION
↓
REAL SPEAKER SEGMENTS
↓
REAL ASR
↓
REAL TRANSCRIPT
↓
REAL ALIGNMENT
↓
REAL TIMELINE
↓
EDITABLE RESULT

============================================================
54. FINAL TIMELINE DESIGN
============================================================

The final timeline should look conceptually like:

                    00:00      00:10      00:20      00:30
                      │          │          │          │
                      ▼          ▼          ▼          ▼
────────────────────────────────────────────────────────────
MASTER AUDIO
████████████████████████████████████████████████████████████
────────────────────────────────────────────────────────────
👤 MOHAN
███████████████                 █████████████████
     00:02 → 00:09                    00:21 → 00:31
────────────────────────────────────────────────────────────
👤 PRIYA
              ███████████████
              00:09 → 00:17
────────────────────────────────────────────────────────────
👤 RAVI
                              █████████████
                              00:17 → 00:24
────────────────────────────────────────────────────────────
TRANSCRIPT
[నమస్కారం అందరికీ]
                 [Okay, ఎలా ఉన్నారు?]
                              [I am fine]
────────────────────────────────────────────────────────────

The user must be able to understand the entire conversation visually
WITHOUT reading the transcript.

The timeline alone should communicate:

WHO
WHEN
HOW LONG
WHO OVERLAPPED
WHERE SPEAKER CHANGED

============================================================
55. FINAL ACCEPTANCE CRITERIA
============================================================

The task is complete ONLY when:

[ ] Application loads without critical errors

[ ] Real WAV uploads

[ ] Real audio duration appears

[ ] Real waveform appears

[ ] Play/Pause works

[ ] Seeking works

[ ] Playhead works

[ ] Real diarization runs

[ ] Speakers appear

[ ] Speaker colors appear

[ ] Speaker segments appear

[ ] Timeline ruler represents real time

[ ] Speaker segments align with real timestamps

[ ] Transcript appears

[ ] Telugu renders correctly

[ ] Telugu + English code-mix renders correctly

[ ] Transcript and timeline are synchronized

[ ] Clicking transcript seeks timeline

[ ] Clicking timeline selects transcript

[ ] Segment resize works

[ ] Segment split works

[ ] Segment merge works

[ ] Speaker reassignment works

[ ] Speaker rename works

[ ] Speaker merge works

[ ] Overlapping speakers are visible

[ ] Zoom works

[ ] Horizontal scroll works

[ ] Long recordings remain usable

[ ] Undo/redo works

[ ] Export works

[ ] Live mode works if configured

[ ] No fake data is used

[ ] No critical console errors

[ ] No broken API requests

[ ] Playwright E2E test passes

[ ] Screenshots have been inspected

[ ] Production build succeeds

============================================================
56. FINAL REPORT
============================================================

When finished, report:

1. What was tested
2. Audio file used
3. Audio duration
4. Number of detected speakers
5. Number of transcript turns
6. Number of timeline segments
7. Whether Telugu transcription worked
8. Whether English transcription worked
9. Whether Telugu-English code-mixing worked
10. Whether timeline synchronization worked
11. Whether editing worked
12. Whether overlap worked
13. Whether export worked
14. Playwright test result
15. Remaining issues
16. Exact files changed

Do NOT provide a generic:

"UI improved successfully."

Provide measurable results.