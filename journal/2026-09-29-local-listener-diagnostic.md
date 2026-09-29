# Local audio inference: a failed listening gate

Date and source access: **2026-09-29**. Evidence: actual local inference on authored controls and the owner's existing *39* crop, measured waveform statistics, and runtime checks. **The audio-input path works; the tested model's descriptions failed our controls. Browser integration is deferred.**

## What was tested

The [diagnostic prototype](../experiments/audio-listener/README.md) feeds actual waveform samples to [Qwen2-Audio-7B-Instruct](https://huggingface.co/Qwen/Qwen2-Audio-7B-Instruct), pinned to revision `0a095220c30b7b31434169c3086508ef3ea5bf0a`. Its model card documents audio analysis and an Apache-2.0 license. The checkpoint's 14 downloaded files were verified against the pinned source hashes. Inference ran locally with BF16, SDPA, and deterministic decoding; no recording was sent to an audio API.

The existing [*39* passage](2026-09-29-39-first-audio-passage.md) was analyzed as two overlapping windows, **00:40–01:05** and **01:00–01:12** in the owner's local version. The union is 32 seconds, not 37. The exact master is still unverified. Titles, producer names, lyrics, and previous interpretations were withheld from the model. The model received 16 kHz mono copies; the original stereo crop was unchanged.

The first trial contained digital silence, three authored sine tones, their reversed sequence, the original crop, and a reversed copy of the crop. After inspecting failures, we froze a shorter prompt and repeated the test with additional controls: quiet tones separated by long silent gaps, their reversed sequence, and 12 seconds of music followed by 13 seconds of digital silence. Both prompts and all raw results are retained privately.

Across the two trials, 17 clip inferences completed. The highest measured CUDA tensor allocation was **16.259 GiB**. Median per-clip generation time was about 3.0 seconds in the first trial and 2.0 seconds in the retest; these are measurements from this machine, not general speed guarantees. The real processor also produced different feature tensors for silence and a tone, confirming that waveform content reached the audio frontend.

## What failed

| Known control | Observed failure |
| --- | --- |
| Twelve seconds of all-zero samples | The initial response invented tones, music, and detailed time ranges. The shorter prompt still produced a sound-effect description. |
| Separated sine tones with substantial rests | Descriptions missed obvious rests and supplied unsupported source labels and timing. |
| Quiet tones separated by long silent gaps | The retest described telephone-like signals with invented durations instead of identifying the large gaps. |
| Twelve seconds of music followed by thirteen seconds of zeros | The retest claimed music throughout and added an unsupported speaking voice. |

The model also supplied varying instrument and vocal descriptions for *39* and its reversed derivative. Those outputs do not establish what instruments are present or how Miku's delivery changes. They are preserved as failed or unverified estimates, not new musical observations.

An all-zero detector can protect a software pipeline from captioning complete digital silence. That is a waveform measurement, not a successful test of the model's understanding. It would not fix the missed long silent intervals in partly audible recordings. We therefore did not turn a numerical silence check into a claimed model pass.

## What this changes

We now have a reproducible way to give a local model real audio and inspect its answers. That resolves acquisition-to-model delivery for local files, while exposing a separate weakness in interpretation. Codex received the model's text; this session does not claim direct perceptual listening by Codex.

The owner chose to finish the diagnostic prototype and document this result. Browser playback integration and trials of additional models are deferred. The standalone recorder and its mechanical checks are described separately in the experiment documentation; they do not change the failed interpretation result.

The recorder captured an authored stereo tone sequence at 48 kHz with the expected frequencies, channel order, pauses, and trailing low signal. It reported startup timing uncertainty instead of claiming complete coverage. Explicit finish took about 32 ms; leaving stdin open without observations stopped the recorder at its 60-second lease. No browser song playback was performed in this implementation session.

Every new analysis report marks the model validation as failed. The birthday-song direction gate remains open, and the earlier text interpretations of *39* are unchanged. A future local model must pass the same blinded controls before we connect automated browser listening. Concrete musical claims still need corroboration against the exact recording or attributed listener feedback.
