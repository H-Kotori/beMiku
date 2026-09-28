# AI Handoff

Updated: 2026-09-29.

## Current focus

Build an informed, revisable interpretation of Miku before selecting the birthday song's direction. Target: 2027-08-31. This is a public, AI-assisted fan project; the owner authorized useful project commits and pushes to `main`.

## Last meaningful changes

- Added `journal/2026-09-29-39-first-audio-passage.md`: first real-recording analysis, 00:40–01:12 of the owner's local *39* MP3, plus a limited reading of its LRC. The tentative creative idea is gratitude with hesitation still present.
- The owner supplied a local MP3/LRC library and offered to obtain specific unavailable songs when needed. Its path is stored only in ignored `local/audio-library.json`; do not publish the library inventory or private paths. NCM files in the separate player-managed folder were not processed.
- Reviewed whale-listen at `7b3e2c7` and ran a controlled Windows/ONNX trial. See `experiments/whale-listen/README.md`, reproducible probe, dependency snapshot, and recorded report.
- Four original isolated pitches were recovered with onset errors up to 7 ms. The unmodified tool misreported a 12-second file as 7 seconds; a separate exact-note test proved false silence under overlap and a last-note duration error. Treat output as estimates; do not trust those summaries.
- Added `journal/2026-09-27-gift-and-disagreement.md`, comparing creator statements around PinocchioP's *Because You're Here* and Hachi's Miku version of *DUNE*.
- The provisional invitation-to-create idea now explicitly permits disagreement. Criticism and invitation need not be opposites; the narrator remains a choice to test.
- Hachi's scene diagnosis is his perception, not verified cultural decline. Wada Takeaki disputes that framing. PinocchioP denies intending his song as an answer to *DUNE*. The note labels these Natalie statements as indexed excerpts because direct pages failed.
- Existing foundations: official background, listening map, first journal, rights/contribution guidance, and roadmap toward original MIDI and a licensed Miku vocal.
- At the owner's request, changed the existing follow-up to daily at 20:00 Asia/Shanghai through 2027-08-31. Keep sessions small; revisits count and no daily quota of new songs or long reviews is required. The schedule is local app state in the owning Codex task, not installed by cloning the repository.

## Open decisions and limitations

- Real mixed-audio analysis now works, but *39*'s exact release/master and LRC wording/alignment remain unverified. No perceptual listening, automatic lyric recognition, or vocal rendering is claimed. Note estimates cannot identify Miku's part or establish emotion.
- The local whale-listen checkout and Python 3.10 environment live under ignored `local/`; rerun instructions are in the experiment README. The private *39* runner is `local/analyze_39_passage.py`, with results under `local/audio-analysis/39-first-passage/`. No global skill or upstream patch was installed. Keep recordings, LRC text, and full transcriptions private.
- No music software inventory, voicebank selection, song language, genre, or final narrative is settled. No composition program has been built yet.
- A licensed voicebank/editor request should follow a concrete phrase ready for testing.
- Reuse licensing for our own eventual code and music remains open; third-party rights are separate.
- Optional ChatGPT 6 Pro consultation was verified against this workspace with project-only memory on 2026-09-25; not rechecked or used this session. Private connection and conversation state stay outside this repository.

## Verification status

- Started the real-song trial clean at `a9a8d2d`, matching `origin/main`; a fast-forward pull reported already up to date.
- Release records and the Real Sound/Pia interview were directly retrieved on 2026-09-27. Original video access failed; no musical or visual observations are claimed. Natalie excerpts have explicit access limits.
- The audio conversion and deterministic summary counterexample both ran. Dependency consistency check passed for all 42 installed packages; the probe compiled. Source/model hashes and measured results are recorded in the experiment report.
- The *39* crop produced 343 estimated events. Four equal windows had 73/89/104/77 starts and RMS values within about 0.26 dB; these are mixed-signal measurements, not vocal or loudness judgments. MP3/LRC hashes were unchanged after processing. Official text sources verified work credits, not the local master or lyrics.
- Independent review checked the measurements and evidence labels. All 16 relative links resolve across 12 Markdown files; the private-data pattern check passed for 16 public candidate files; library configuration and trial artifacts are ignored; `git diff --check` passed.
- Authenticated local Git works for publishing; the GitHub app's write API previously returned 403.

## Next step

Seek listener feedback on 00:40–01:12 of the local *39* version: check LRC alignment and identify arrangement/vocal changes behind the measurements. Keep feedback distinct from agent inference. Continue the *Double Lariat*/Luka research connection independently, requesting an ordinary playable download from the owner when a specific unavailable song is needed. Broader exploration still needs a less visible creator and another language/community.

For the outstanding listening gate, use the exact recording/version identified in the relevant journal entry with actual audio access, or request owner listening feedback. Record timestamps for a change in address and the ending; distinguish sound from captions/visuals and owner reports from agent observations. Do not declare the musical-direction gate complete from text research or unvalidated note estimates. Keep the roadmap's early-2027 sketch milestone.
