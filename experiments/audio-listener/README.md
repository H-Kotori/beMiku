# Local audio listener

An experimental route from an actual recording to audio-grounded observations for beMiku. The local Qwen2-Audio model receives waveform samples. Codex receives the model's text estimates and reasons from them; this is not a direct audio input to the Codex conversation.

**Status, 2026-09-29: diagnostic prototype; model usefulness gate failed.** Local inference works, but two blinded trials produced invented sounds and missed substantial silence. Browser playback integration is deferred. Generated descriptions must not be used as established musical evidence. See the [trial assessment](../../journal/2026-09-29-local-listener-diagnostic.md) and [recorded validation](validation.json).

The owner selected **local inference** and **speaker-output mix capture**. Recordings and derivatives stay under ignored `local/`. Capturing an output mix includes other applications using that output. Keep those recordings private. No microphone or voicebank is needed.

## Model and evidence

- Model: [Qwen/Qwen2-Audio-7B-Instruct](https://huggingface.co/Qwen/Qwen2-Audio-7B-Instruct), Apache 2.0; revision `0a095220c30b7b31434169c3086508ef3ea5bf0a`.
- Runtime: a separate Python 3.11 environment, CUDA PyTorch, Transformers, and Accelerate. BF16, SDPA, batch size one, deterministic generation, maximum 384 generated tokens.
- Analysis: 25-second windows with five seconds of overlap, converted to 16 kHz mono. The original channels and rate are preserved in the source file. Mono cancellation and reduced frequency range can affect what the model receives.
- Scope: vocal texture/delivery, accompaniment, rhythm, and changes. No exact singer identification, lyric transcription, BPM/key accuracy, or emotional intention is established by this experiment.
- Provenance: model files are hash-verified; inference uses `local_files_only=True` and disables Hub network resolution. Titles, lyrics, filenames, and previous interpretations are withheld from the model prompt.

The analysis report separates measured signal statistics from generated observations. Clip bounds come from frames; timing inside generated prose is unverified. Overlapping clips do not add to the recording's duration. Source identity information is report-only. A completed inference is not a claim that its descriptions are correct.

Every new report includes `model_validation.status = "failed_controls"`. The probe deliberately retains the model's bad answers for evaluation: a measured all-zero signal must not be relabeled as evidence that the model understands silence.

## Setup

The working environment is already installed locally. To reproduce on Windows with [uv](https://docs.astral.sh/uv/) available, run from the repository root:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) 'local/audio-listener-cache'
uv python install 3.11.15 --install-dir local/audio-listener-python --no-bin --no-registry
uv venv --python local/audio-listener-python/cpython-3.11.15-windows-x86_64-none/python.exe local/audio-listener-venv
uv pip install --python local/audio-listener-venv/Scripts/python.exe torch==2.12.1+cu126 --index-url https://download.pytorch.org/whl/cu126
uv pip install --python local/audio-listener-venv/Scripts/python.exe -r experiments/audio-listener/requirements-lock.txt
& ./local/audio-listener-venv/Scripts/python.exe experiments/audio-listener/download_model.py
```

The official model download is about 16.8 GB. Setup checks Hugging Face's pinned revision and verifies Git blob/LFS hashes before writing a local SHA-256 manifest. The inference loader verifies that manifest and all model files again. `download_model.py --verify-only` checks the existing download without network access. HF Xet completed the download on the tested machine; the lock includes it. The existing Basic Pitch environment is separate and unchanged.

This configuration was exercised on an RTX 3090 with 24 GiB VRAM and Windows CUDA 12.6 wheels. It requires a compatible NVIDIA driver and BF16 support; no CPU/cloud fallback is selected. Model initialization and CUDA checks fail explicitly if these requirements are unavailable.

## Analyze an existing recording

After installing the isolated runtime and verified model, run from the repository root:

```powershell
& ./local/audio-listener-venv/Scripts/python.exe experiments/audio-listener/listen.py analyze --file ./local/audio-analysis/39-first-passage/passage.wav --source-offset 40
```

This uses the existing private 32-second crop of the owner's *39* recording. Its two model windows refer to source times 00:40–01:05 and 01:00–01:12. It does not identify the master or establish correspondence with an online video. The [earlier passage study](../../journal/2026-09-29-39-first-audio-passage.md) documents the source limitations.

For another local file, use `--start` and `--end` in file seconds. `--source-offset` adds a known crop offset when reporting positions in the original recording. Optional `--metadata` accepts a private JSON identity record that is never sent to the model. Outputs receive a fresh private session directory; `--output` can name a new directory under `local/`.

Each session stores `report.json` and derived clip WAVs. Reports include source hash/format, measured passage duration and energy, actual model input energy, model/revision/prompt, clip bounds, generated estimates, execution time, and CUDA memory. Failures preserve a partial report and private diagnostic text when inference has started. CLI output contains progress and a repository-relative report location, not raw model prose or source paths.

## Standalone recorder

The recorder is available for mechanical tests independently of the failed model gate. It does not operate a browser. Run it in a terminal that keeps stdin open:

```powershell
& ./local/audio-listener-venv/Scripts/python.exe experiments/audio-listener/listen.py devices
& ./local/audio-listener-venv/Scripts/python.exe experiments/audio-listener/listen.py capture --output ./local/audio-listener-sessions/example
```

After `capture_ready`, send one JSON object per line. `{"type":"finish"}` finalizes the WAV. `{"type":"cancel"}` cancels. For a future authorized playback controller, an observation has this shape; supply the real current observation time, not the placeholder:

```json
{"type":"observe","source_id":"https://www.youtube.com/watch?v=VIDEO_ID","media_time_seconds":15.2,"duration_seconds":230,"state":"playing","rate":1,"ad":false,"seeking":false,"observed_at_unix":0}
```

Only valid fresh observations renew the 60-second timeout. A separate 600-second cap remains in force. EOF, cancellation, stream faults, default-output changes, and overflows produce a partial recording. The default output is fixed at session start. Optional `--device-index`, `--max-seconds`, and `--lease-seconds` support explicit device selection and shorter diagnostic runs; the hard bounds cannot be increased.

`original.wav` retains received PCM16 frames. `capture.json` keeps sample positions, device-clock packet times, observation times, errors, and mapped source intervals. Missing packets are not filled with invented silence. Source coverage requires adjacent playing observations no more than 20 seconds apart, unchanged source/rate, consistent media time, and contiguous device-timed packets. Device clocks allow 5 ms of timestamp jitter; smaller gaps cannot be resolved. Pauses, seeks, advertisements, device changes, invalid observations, and unreliable clocks exclude affected intervals. Unbracketed beginning/end audio remains private but is not assigned a verified source position.

`analyze --session CAPTURE_DIRECTORY` analyzes only those mapped intervals. It returns `no_verified_coverage` without loading the model if none exist. Capture and analysis status are separate; `complete` means the operation completed, not that a full song was heard. Sparse observations cannot exclude every interruption between observations, and the output mix cannot isolate a song from other applications.

Codex can keep stdin open with a terminal execution session and send commands through `write_stdin`. Browser observation/play/pause orchestration remains deferred until an audio model passes the controlled usefulness tests.

## Verification

Unit tests exercise frame-derived timing, overlap coverage, silence, stereo cancellation, source immutability, private output boundaries, model integrity, and offline model input. They use authored signals and a fake inference backend rather than pretending to measure real-model quality.

```powershell
& ./local/audio-listener-venv/Scripts/python.exe -m unittest discover -s experiments/audio-listener -p 'test_*.py'
```

The Windows hardware trial captured 590,848 stereo PCM16 frames at 48 kHz (12.309333 seconds). It recovered the authored 440 Hz and 880 Hz left-channel tones and 660 Hz right-channel tone, with the expected pauses and about 3.22 seconds of trailing low signal. Explicit finish reached the final report in 32 ms. One startup packet lacked a reliable clock and one startup gap remained, so the report correctly stayed `partial`; five mapped intervals totaled about 10.033 seconds. This verifies the tone sequence and channels, not bit-perfect fidelity or exact absolute synchronization.

With stdin left open, no observations, and no audio packets, the default lease stopped at 60.000 seconds internally and reported completion after 60.016 seconds. Its WAV contains zero frames, rather than fabricated silence. Hardware results vary with the endpoint, mixer, system volume, and other playback; these measurements are in [validation.json](validation.json).

To repeat the hardware checks, use fresh output directories. The first command plays a 12-second authored tone sequence at the existing system volume; the second leaves the recorder unattended until its lease expires. Neither command changes the output device or volume. Detailed results stay in each private directory.

```powershell
& ./local/audio-listener-venv/Scripts/python.exe experiments/audio-listener/verify_capture.py --mode tones --output ./local/audio-listener-hardware-tones-new
& ./local/audio-listener-venv/Scripts/python.exe experiments/audio-listener/verify_capture.py --mode lease --output ./local/audio-listener-hardware-lease-new
```

The helper checks frequencies, channels, relative onset timing, trailing low signal, recording format/frame consistency, and shutdown bounds. Its synthetic observations use the playback process clock, not browser state or exact speaker timing. Passing these mechanical checks does not override a partial capture status or validate the audio model. Unit tests and helper checks do not replace the separate real-model probe.

The real-model probe generates silence, separated tones, and reversed tones, then optionally analyzes the existing *39* crop, its reversed derivative, and a partly zeroed copy. Control identities are recorded outside the prompt. Raw responses stay private for review.

```powershell
& ./local/audio-listener-venv/Scripts/python.exe experiments/audio-listener/probe.py --output ./local/audio-listener-probe --passage ./local/audio-analysis/39-first-passage/passage.wav
```

Do not mark the roadmap's musical-direction listening gate complete solely because these programs produce text. Check concrete musical claims against the exact recording or attributed listener feedback. The existing [whale-listen experiment](../whale-listen/README.md) remains a separate optional source of pitch estimates.

## Sources

Technical documentation accessed 2026-09-29: [Qwen2-Audio project](https://github.com/QwenLM/Qwen2-Audio), [Transformers implementation guide](https://huggingface.co/docs/transformers/model_doc/qwen2_audio), [Microsoft WASAPI loopback](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording), and [PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch). Runtime validation and listening results must be recorded separately from these sources' capability descriptions.
