# AI Handoff

Updated: 2026-09-29.

## Current focus

Build an informed, revisable interpretation of Miku before selecting the birthday song's direction. Target: 2027-08-31. This is a public, AI-assisted fan project; the owner authorized useful project commits and pushes to `main`.

## Last meaningful changes

- Reviewed whale-listen at `7b3e2c7` and ran a controlled Windows/ONNX trial. See `experiments/whale-listen/README.md`, reproducible probe, dependency snapshot, and recorded report.
- Four original isolated pitches were recovered with onset errors up to 7 ms. The unmodified tool misreported a 12-second file as 7 seconds; a separate exact-note test proved false silence under overlap and a last-note duration error. Treat output as estimates; do not trust those summaries.
- Added `journal/2026-09-27-gift-and-disagreement.md`, comparing creator statements around PinocchioP's *Because You're Here* and Hachi's Miku version of *DUNE*.
- The provisional invitation-to-create idea now explicitly permits disagreement. Criticism and invitation need not be opposites; the narrator remains a choice to test.
- Hachi's scene diagnosis is his perception, not verified cultural decline. Wada Takeaki disputes that framing. PinocchioP denies intending his song as an answer to *DUNE*. The note labels these Natalie statements as indexed excerpts because direct pages failed.
- Existing foundations: official background, listening map, first journal, rights/contribution guidance, and roadmap toward original MIDI and a licensed Miku vocal.
- At the owner's request, changed the existing follow-up to daily at 20:00 Asia/Shanghai through 2027-08-31. Keep sessions small; revisits count and no daily quota of new songs or long reviews is required. The schedule is local app state in the owning Codex task, not installed by cloning the repository.

## Open decisions and limitations

- Song research still uses text and metadata. The audio trial used synthetic tones only; no Miku-song analysis, lyric recognition, perceptual listening, or vocal rendering has been verified.
- The local whale-listen checkout and Python 3.10 environment live under ignored `local/`; rerun instructions are in the experiment README. No global skill or upstream patch was installed. Keep recordings and full transcriptions private. A first song file/path or creator-provided download was requested from the owner.
- No music software inventory, voicebank selection, song language, genre, or final narrative is settled. No composition program has been built yet.
- A licensed voicebank/editor request should follow a concrete phrase ready for testing.
- Reuse licensing for our own eventual code and music remains open; third-party rights are separate.
- Optional ChatGPT 6 Pro consultation was verified against this workspace with project-only memory on 2026-09-25; not rechecked or used this session. Private connection and conversation state stay outside this repository.

## Verification status

- Started the tool evaluation clean at `2255f77`, matching `origin/main`; a fast-forward pull reported already up to date.
- Release records and the Real Sound/Pia interview were directly retrieved on 2026-09-27. Original video access failed; no musical or visual observations are claimed. Natalie excerpts have explicit access limits.
- The audio conversion and deterministic summary counterexample both ran. Dependency consistency check passed for all 42 installed packages; the probe compiled. Source/model hashes and measured results are recorded in the experiment report.
- Independent review caught a checkout-line-ending issue in the source hash guard; normalization fixed it and the probe rerun reproduced the results. All 15 relative links resolve across 11 Markdown files; the private-data pattern check passed for 15 public candidate files; `git diff --check` passed.
- Authenticated local Git works for publishing; the GitHub app's write API previously returned 403.

## Next step

If a local song or creator-provided download becomes available, analyze one short passage with the reviewed tool, exact version and timestamps. Label results machine-estimated audio evidence; confirm notes against listening feedback and use separate verified text for lyrics. Do not infer the vocalist or emotional meaning from note JSON. Until then, follow the first journal's *Double Lariat* connection into Megurine Luka: what did Agoaniki's work make possible for another creator? Verify original upload and credits, then write one bounded note. Broader exploration still needs a less visible creator and another language/community.

For the outstanding listening gate, use the exact original uploads in the latest note with actual audio access, or request owner listening feedback. Record timestamps for a change in address and the ending; distinguish sound from captions/visuals and owner reports from agent observations. Do not declare the musical-direction gate complete from text research. Keep the roadmap's early-2027 sketch milestone.
