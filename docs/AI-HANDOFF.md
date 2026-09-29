# AI Handoff

Updated: 2026-09-30.

## Current focus

Build an informed, revisable interpretation of Miku before selecting the birthday song's direction. Target: 2027-08-31. This is a public, AI-assisted fan project; the owner authorized useful project commits and pushes to `main`.

## Last meaningful changes

- Added [MikuFiesta and belonging](../journal/2026-09-30-mikufiesta-and-belonging.md): official Spanish-language identification, AlexTrip Sands' account of retaining his style while introducing Miku, one attributed reader response, and fans including the absent creator remotely. New writing prompt: name an absent addressee and a concrete act of welcome. Text research only; no lyric or audio assessment this session.
- Added [the local audio diagnostic](../experiments/audio-listener/README.md) and [failed listening-gate assessment](../journal/2026-09-29-local-listener-diagnostic.md). Actual waveforms reached Qwen2-Audio-7B-Instruct locally, but two blinded trials invented sounds and missed substantial silence. **Model usefulness failed. The owner chose to finish the diagnostic and defer browser integration and additional model trials.**
- The diagnostic has `devices`, bounded `capture`, and offline `analyze` commands. WASAPI capture accepts stdin observations/finish; only consistent observation-bracketed intervals enter session analysis. It records missing data separately from silence. All analysis reports retain the failed model-validation label.
- Added `journal/2026-09-29-double-lariat-and-permission.md`: a Luka work's influence on PinocchioP, Agoaniki's account of his own voice through Vocaloid, and a creator-text reading. New hypothesis: encourage by concrete example instead of automatically writing an explicit invitation.
- Added `journal/2026-09-29-39-first-audio-passage.md`: first real-recording note analysis, 00:40–01:12 of the owner's local *39* MP3, plus a limited reading of its LRC. The tentative creative idea is gratitude with hesitation still present. The new model trial establishes no additional musical facts.
- The owner supplied a local MP3/LRC library and offered to obtain specific unavailable songs when needed. Its path is stored only in ignored `local/audio-library.json`; do not publish the inventory or private paths. NCM files in the separate player-managed folder were not processed.
- Reviewed whale-listen at `7b3e2c7` with Windows/ONNX controls. It recovered isolated pitches but misreported duration and silence under overlapping notes. See `experiments/whale-listen/README.md`; its outputs remain estimates, not verified vocal or emotional descriptions.
- The provisional invitation-to-create idea permits disagreement; criticism and invitation need not be opposites. Existing background, listening map, rights guidance, and roadmap remain the foundation.
- The existing follow-up runs daily at 20:00 Asia/Shanghai through 2027-08-31. Keep sessions small; revisits count and there is no quota of new songs or long reviews. This schedule is local app state in the owning Codex task, not installed by cloning the repository.

## Local runtime and evidence

- Separate Python 3.11 runtime: `local/audio-listener-venv/`. Verified model: `local/models/qwen2-audio/`, revision `0a095220c30b7b31434169c3086508ef3ea5bf0a`. BF16/SDPA on the local GPU worked. Reproduction instructions and pinned dependencies are public; weights and detailed reports are ignored.
- Initial results: `local/audio-listener-probe-initial/`. Retest: `local/audio-listener-probe-retest/`. Seventeen clip inferences completed with source hashes unchanged; measured peak CUDA allocation was 16.259 GiB. Raw generated descriptions remain private and unverified. Silence detection in code would be a measurement, not a model-understanding pass.
- Standalone hardware results: `local/audio-listener-hardware-standalone/`. Authored stereo tones were recovered at 48 kHz PCM16. The result stayed partial because of startup clock uncertainty; five mapped spans totaled about 10.033 seconds. Explicit finish took 32 ms. The no-observation lease reported shutdown at 60.016 seconds with zero packets, without manufacturing silence.
- The whale-listen checkout and Python 3.10 environment under `local/` are unchanged. Private *39* runner: `local/analyze_39_passage.py`; crop/results: `local/audio-analysis/39-first-passage/`. Keep recordings, LRC text, transcriptions, and machine configuration private.

## Open decisions and limitations

- *39*'s exact release/master and LRC wording/alignment remain unverified. Its note estimates cannot identify Miku's part or establish emotion. Codex received model text estimates, not direct audio input; no verified perceptual listening or automatic lyric recognition is claimed.
- No browser playback orchestration was implemented or tested. Capture was exercised with authored tones, not a browser song. Sparse playback observations cannot exclude every interruption between them; the output mix includes other applications. Device-clock jitter under 5 ms is unresolved, and absolute synchronization is approximate.
- *Double Lariat* has no matching playable local MP3/LRC. Creator reference: `https://piapro.jp/t/M34f`; original work `nm6049209`. A request for Agoaniki's Luka vocal version is pending with the owner as of 2026-09-29; avoid duplicate requests. Distinguish karaoke/remakes/live versions before assigning timestamps. Piapro text was read; playback/download not verified.
- No music software inventory, voicebank selection, song language, genre, or final narrative is settled. No composition program or vocal render exists. Request a licensed editor/voicebank when a concrete original phrase is ready for testing.
- Reuse licensing for our own eventual code and music remains open; third-party rights are separate.
- Optional ChatGPT 6 Pro consultation was verified against beMiku with project-only memory on 2026-09-25; not rechecked or used this session. Private connection state stays outside the repository.

## Verification status

- The September 30 research session began clean at `8220b0f` on `codex/makeCodexHearSongs`; switched to `main` and safely fast-forwarded it to the same published commit. Only the new journal, README, and this handoff are in scope; the diagnostic code is unchanged.
- This documentation session passed independent primary-source review, 33 relative-link checks across 16 Markdown files, a private-data pattern scan of the three changed files, and `git diff --check`. No code tests were rerun for these prose changes; the implementation results below are from the prior diagnostic session.
- The audio listener's behavioral suite passed 51 tests in the isolated Python 3.11 runtime. Real hardware exposed COM-apartment and device-clock jitter issues; both received fixes and regression coverage. All 48 locked packages passed dependency consistency checks.
- Fourteen downloaded checkpoint files passed pinned Git blob/LFS verification. Inference rechecks SHA-256 hashes and loads model/processor offline. Real processor checks confirmed different features for silence and tones. Successful inference does not override the failed controls.
- Independent review checked code boundaries, private-data handling, evidence labels, and public metrics against the private reports. Authenticated local Git works for publishing; the GitHub app's write API previously returned 403.

## Next step

Keep browser integration deferred as requested. A future local model would need to pass blinded controls before automated listening becomes useful; do not silently resume model downloads or reinterpret this diagnostic as a success. Owner feedback on the exact *39* passage remains useful for arrangement/vocal changes and LRC alignment.

If *Double Lariat* audio arrives, identify its version and retain the current evidence limits. No matching ordinary *MikuFiesta* file was found either; its official contest video is linked in the new journal for version-specific owner feedback. No additional download request was sent. Next follow AlexTrip Sands' peer recommendation of Hiyimi's *The Sound of Me*: verify the creator upload and context. Do not equate a peer recommendation with evidence of a small audience; exploration beyond prominent winners is still needed.

For the roadmap's outstanding listening gate, record timestamps for a change in address and the ending using validated audio-derived evidence or attributed owner listening feedback. Distinguish sound from captions/visuals. Do not close the musical-direction gate from text research, unvalidated note estimates, or the failed audio model. Keep the early-2027 sketch milestone.
