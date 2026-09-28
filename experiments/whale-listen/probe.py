"""Exercise reviewed whale-listen on original tones and a polyphony counterexample.

This is a diagnostic experiment, not a Miku recording or a listening review.
Run from the repository root in the isolated environment described in README.md.
"""

import contextlib
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import platform
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pretty_midi
import soundfile as sf


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "local/whale-listen-source/whale_listen.py"
OUTPUT = ROOT / "local/whale-listen-trial"
SOURCE_LF_SHA256 = "e5de3dc6c604ae345ab5b3b3a5a08c8af5a700b9ea781931dcc4980ec945b697"


def main():
    source_bytes = SOURCE.read_bytes()
    normalized_source_hash = hashlib.sha256(source_bytes.replace(b"\r\n", b"\n")).hexdigest()
    if normalized_source_hash != SOURCE_LF_SHA256:
        raise RuntimeError("Upstream source changed; review it before updating this probe.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("whale_listen", SOURCE)
    whale = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(whale)

    # Four authored pitches with harmonics, short fades, and known rests.
    sample_rate = 22050
    audio = np.zeros(12 * sample_rate)
    expected = [(60, 0.5, 1.5), (64, 2.0, 3.0), (67, 3.5, 4.5), (72, 6.0, 7.0)]
    for pitch, start, end in expected:
        first, last = round(start * sample_rate), round(end * sample_rate)
        t = np.arange(last - first) / sample_rate
        frequency = 440 * 2 ** ((pitch - 69) / 12)
        tone = sum(
            amplitude * np.sin(2 * np.pi * harmonic * frequency * t)
            for harmonic, amplitude in [(1, 1.0), (2, 0.2), (3, 0.1)]
        )
        envelope = np.minimum(1, t / 0.01) * np.minimum(1, (end - start - t) / 0.03)
        audio[first:last] += 0.35 * tone * envelope
    audio_path = OUTPUT / "four-original-tones.wav"
    sf.write(audio_path, audio, sample_rate, subtype="PCM_16")

    # Actual audio-to-MIDI-to-JSON prediction using unmodified upstream code.
    prediction = whale.convert(
        str(audio_path), str(OUTPUT / "predicted.json"), str(OUTPUT / "predicted.mid")
    )
    unmatched = list(range(len(prediction["notes"])))
    matches = []
    for pitch, start, end in expected:
        candidates = [
            i for i in unmatched
            if prediction["notes"][i]["pitch"] == pitch
            and abs(prediction["notes"][i]["start"] - start) <= 0.15
        ]
        match = {"expected_pitch": pitch, "expected_start": start, "expected_end": end}
        if candidates:
            i = min(candidates, key=lambda n: abs(prediction["notes"][n]["start"] - start))
            unmatched.remove(i)
            note = prediction["notes"][i]
            match.update(detected=True, predicted_start=note["start"], predicted_end=note["end"])
        else:
            match["detected"] = False
        matches.append(match)

    # Separate deterministic adapter test: replace inference with exact notes.
    # This tests summary logic only; it does not measure the model's accuracy.
    midi = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(0)
    for pitch, start, end in [(60, 0, 10), (64, 1, 2), (67, 3, 4)]:
        instrument.notes.append(pretty_midi.Note(80, pitch, start, end))
    midi.instruments.append(instrument)
    with patch.object(whale, "predict", return_value=({}, midi, [None] * 3)):
        counterexample = whale.convert(
            str(audio_path), str(OUTPUT / "overlap.json"), str(OUTPUT / "overlap.mid")
        )
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        whale.analyze(counterexample)

    report = {
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_lf_normalized_sha256": normalized_source_hash,
        "python": platform.python_version(),
        "platform": platform.system(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ["basic-pitch", "onnxruntime", "pretty-midi", "scipy", "librosa", "numpy"]
        },
        "model_file": Path(whale.find_model()).name,
        "model_sha256": hashlib.sha256(Path(whale.find_model()).read_bytes()).hexdigest(),
        "audio_trial": {
            "audio_file": audio_path.name,
            "sample_rate": sample_rate,
            "actual_duration_sec": sf.info(audio_path).duration,
            "reported_duration_sec": prediction["duration_sec"],
            "predicted_note_count": prediction["total_notes"],
            "matches_with_same_pitch_and_onset_within_150ms": matches,
            "unmatched_predictions": [prediction["notes"][i] for i in unmatched],
        },
        "mocked_inference_counterexample": {
            "known_latest_note_end_sec": 10,
            "reported_duration_sec": counterexample["duration_sec"],
            "false_silence_2_to_3_sec_reported": "2.0s — 3.0s  (1.0s)" in captured.getvalue(),
            "analysis_stdout": captured.getvalue(),
        },
        "limitations": "Synthetic tones only. No lyrics, Miku recording, or full-mix accuracy assessed.",
    }
    (OUTPUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
