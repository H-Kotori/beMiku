# Before the toast — first MIDI comparison

Created **2026-10-08**, version **0.1**, by Codex for beMiku. This is an original eight-bar instrumental experiment following the [birthday-host brief](../../2026-10-07-birthday-host-brief.md). **It contains no Miku vocal, and no perceptual listening review has been completed.**

## Play the pair

| Version | Play/download the 20-second guide | Editable MIDI |
| --- | --- | --- |
| A — later release | [A.wav](generated/A.wav) | [A.mid](generated/A.mid) |
| B — earlier release | [B.wav](generated/B.wav) | [B.mid](generated/B.mid) |

Compare **00:07.50–00:11.25** at the same playback volume. The next phrase begins at **00:10.00** in both. Does either version make that phrase feel more distinct while keeping forward motion? No clear preference and neither working are valid responses. These timestamps come from the authored score and exported files, not listening observations.

This pair is intended for owner feedback. No preferred version has been selected. Record the version, file hash from the [manifest](generated/manifest.json), passage, and listener's words when feedback arrives. A listener's impression should not become a claim about how all fans hear Miku.

## What was composed

The [editable score](score.json) contains 29 explicitly authored lead notes and 24 accompaniment notes: four two-bar phrases in C major, **4/4, 96 BPM**, spanning 32 quarter-note beats. The lead ranges from MIDI 65 to 76 (F4–E5); the chord sequence is C–F–Am–G–Am–F–Dm–C. These are provisional musical choices for this experiment, not observations about any reference song.

The four phrases correspond broadly to the first four lines of [Before the toast](../../lyrics/2026-10-05-before-the-toast.md). No syllable-level lyric underlay, pitch-accent review, or sung pronunciation has been verified. In particular, a written mora count does not tell us how to voice a small っ or place a long vowel on these notes.

Only the release of D5 at zero-based beat 13 changes:

| Measurement | A | B |
| --- | --- | --- |
| Target note starts | 8.125 s | 8.125 s |
| MIDI note-off | 9.6875 s (beat 15.5) | 8.75 s (beat 14) |
| Nominal rest before next lead phrase | 0.3125 s | 1.25 s |
| Programmed sound release | 80 ms | 80 ms |

Accompaniment continues. The comparison trades some held-note duration for more space in the melody; it does not isolate silence alone. A longer gap might suggest waiting, hesitation, or lost momentum. Instrumental feedback cannot establish the narrator's meaning or the eventual Miku delivery.

## Rebuild and check

Tested with **CPython 3.10.20**, Mido 1.3.3, and packaging 26.3. The two dependencies are pinned in [requirements.txt](requirements.txt). From the repository root, in PowerShell with Python installed:

```powershell
python -m venv local/composition-venv
local/composition-venv/Scripts/python.exe -m pip install -r sketches/music/01-before-the-toast/requirements.txt
local/composition-venv/Scripts/python.exe sketches/music/01-before-the-toast/build.py --output-dir local/toast-rebuild
local/composition-venv/Scripts/python.exe -m unittest discover -s sketches/music/01-before-the-toast -p test_build.py -v
```

[build.py](build.py) reads its sibling score, so it can be run from any working directory. Omitting `--output-dir` rebuilds the checked-in `generated/` files. Notes use `[start_beat, end_beat, MIDI_pitch, velocity]`; `comparison.lead_index` is zero-based and identifies the one earlier release in B. The score is deliberately specific to this eight-bar study, rather than a general composition framework.

MIDI export uses [Mido's file API](https://mido.readthedocs.io/en/stable/files/midi.html). Both files have type-1 tracks for timing, lead, and backing, 480 ticks per quarter note, and a common end-of-track at beat 32. Program 0 is a playback suggestion; a player's instrument will differ from the custom WAV sound. The WAVs are rendered from the same score with sine waves and a second harmonic, fixed gains, a 10 ms attack, and an 80 ms release. No samples, recordings, soundfonts, or voicebanks are used. There is no per-file normalization, device access, playback, or network access in the builder.

The [tests](test_build.py) passed all three behavioral checks: byte-identical repeated output through the API and a fresh CLI process, only the designated absolute MIDI note-off differing, and matched PCM data outside the expected change window. They also check note lifecycles, monophony, continuing backing, file duration, and full-scale clipping. Both WAVs are mono PCM16 at 44.1 kHz, 882,000 frames each. The manifest records versions, normalized source/builder hashes, output hashes, and numerical signal measurements. These checks establish export behavior, not musical quality. Byte identity was verified on the recorded runtime; cross-platform floating-point differences are not ruled out.

The melody and waveforms were newly authored for beMiku. The project's [reuse-license decision](../../../docs/RIGHTS.md) remains open. Keep the [roadmap's listening requirement](../../../docs/ROADMAP.md) open as well; an exported guide is neither a finished birthday song nor a licensed vocal experiment.
