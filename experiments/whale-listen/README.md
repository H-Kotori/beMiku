# whale-listen evaluation

Evaluated **2026-09-29** on Windows, CPython 3.10.20, with the ONNX model bundled in Basic Pitch 0.4.0. This is a diagnostic experiment, not a composition program or a Miku performance.

**Decision:** keep [whale-listen](https://github.com/migratorywhale/whale-listen) available as an experimental source of estimated pitch events. Do not use its summary labels as established musical facts. It is a Python utility, not a packaged Codex skill.

## Reviewed source and execution

- Reviewed commit: [`7b3e2c70209367b0194f1feab217cd4c2d5f34a4`](https://github.com/migratorywhale/whale-listen/tree/7b3e2c70209367b0194f1feab217cd4c2d5f34a4).
- Read the complete Python script, package metadata, README and MIT license. The script reads local files, invokes Basic Pitch, and writes MIDI/JSON. It contains no explicit network requests, credential reads, or subprocess launches. This review does not audit every transitive dependency.
- Dependencies and source are isolated under ignored `local/` directories. The upstream source was not modified; no global skill was installed. Installation downloaded packages and a Python runtime; inference used the bundled local ONNX model.
- The first run failed because `resampy` imports `pkg_resources`. Adding `setuptools==80.9.0` fixed that import. The [environment snapshot](requirements-lock.txt) includes that dependency. Unavailable CoreML/TensorFlow/TFLite warnings do not prevent this ONNX run.
- The probe checks the reviewed script's SHA-256 after normalizing CRLF to LF, before importing it. Both raw and normalized hashes are recorded. Re-review changed source before updating that check.

## Measured results

The [probe](probe.py) generates a 12-second WAV with four original, isolated harmonic tones and known rests. It then runs the real audio conversion. A separate test supplies exact overlapping MIDI notes in place of model inference to isolate summary errors. These two kinds of evidence must not be conflated.

| Check | Result |
| --- | --- |
| Known pitches | C4, E4, G4, C5 all recovered; four predictions, no extra notes. |
| Start times | Largest absolute error: 0.007 seconds. The matching criterion was the same pitch and a start within 0.15 seconds. |
| End times | Predictions ended 0.030–0.044 seconds after the authored tones. |
| Audio duration | WAV is 12.0 seconds; upstream JSON says 7.0. Trailing time without detected notes disappears. |
| Overlapping-note duration | Exact notes C4 `[0,10]`, E4 `[1,2]`, G4 `[3,4]` produce a reported duration of 4.0 seconds, although a note continues to 10. |
| False silence | The same exact-note test reports silence at 2–3 seconds while C4 continues. This is a summary bug independent of model accuracy. |

The [recorded report](report.json) contains package versions, source/model hashes, individual matches and the counterexample output. The WAV, MIDI, raw predictions, and cloned source remain local. The test uses no third-party recording or lyrics. No full-song, mixed-accompaniment, voice-identification, or lyric-recognition accuracy was measured.

## Limits that matter for beMiku

In the [reviewed implementation](https://github.com/migratorywhale/whale-listen/blob/7b3e2c70209367b0194f1feab217cd4c2d5f34a4/whale_listen.py), duration comes from the last-starting note rather than the latest ending note or the audio file. Its gap calculation checks only adjacent notes instead of merging all overlapping intervals. Even a correctly computed gap means no *detected pitched notes*, not necessarily acoustic silence.

The density display counts note starts; the pitch map averages detected MIDI pitches. Its “chords” are onset clusters within 50 milliseconds. JSON omits pitch bends present in MIDI. These outputs cannot alone establish melody ownership, harmonic function, vocal expression, loudness, emotional meaning, or words being sung.

[Basic Pitch's documentation](https://github.com/spotify/basic-pitch) says it works best on one instrument at a time. Its [note-creation code](https://github.com/spotify/basic-pitch/blob/v0.4.0/basic_pitch/note_creation.py) derives MIDI velocity from model activation, so velocity is not a calibrated loudness measurement. A full Miku mix may contain estimated notes from accompaniment as well as singing. Lyric study still needs creator-provided text or separately checked transcription.

For a song trial, use a local recording supplied by the owner or a creator-provided download, retain the exact version, and keep recordings and full transcriptions out of Git. Label findings **machine-estimated audio evidence**, with timestamps and uncertainty. Confirm a short passage with listening feedback before using it to justify composition choices. The screenshot's claims about another recording were not verified here.

## Reproduce

From the repository root, with Git and Python 3.10 installed, create an isolated environment and check out the reviewed source. The following commands are for PowerShell:

```powershell
git clone https://github.com/migratorywhale/whale-listen.git local/whale-listen-source
git -C local/whale-listen-source checkout 7b3e2c70209367b0194f1feab217cd4c2d5f34a4
py -3.10 -m venv local/whale-listen-venv
& ./local/whale-listen-venv/Scripts/python.exe -m pip install -r experiments/whale-listen/requirements-lock.txt
$env:PYTHONUTF8 = '1'
& ./local/whale-listen-venv/Scripts/python.exe experiments/whale-listen/probe.py
```

On this workspace the source and environment already exist; rerun only the last two lines. Output goes to `local/whale-listen-trial/`. The lock is a snapshot of the successful Windows environment, not a promise of compatibility with every Python version or operating system. No Miku voicebank is required for this test.
