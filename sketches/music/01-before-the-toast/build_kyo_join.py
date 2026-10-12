"""Export one vowel-join candidate based on A, leaving the original A/B pair intact."""

import argparse
from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import platform

import build as original


ROOT = Path(__file__).resolve().parent


def build(output_dir):
    baseline = json.loads((ROOT / "score.json").read_text(encoding="utf-8"))
    for name in ("lead", "backing"):
        baseline[name] = [[float(start), float(end), pitch, velocity]
                          for start, end, pitch, velocity in baseline[name]]
    # This experiment is tied to the published score, not an arbitrary note index.
    if baseline["lead"][8] != [8.0, 8.75, 72, 90] or baseline["lead"][9][0] != 9:
        raise ValueError("The source phrase changed; review the vowel-join experiment")
    candidate = deepcopy(baseline)
    candidate["lead"][8][1] = 9.0
    original.validate(candidate)
    output_dir = Path(output_dir)
    if output_dir.resolve() == (ROOT / "generated").resolve():
        raise ValueError("Use a separate output directory to preserve the A/B manifest")
    output_dir.mkdir(parents=True, exist_ok=True)
    midi_path = output_dir / "kyo-join-A.mid"
    wav_path = output_dir / "kyo-join-A.wav"
    original.write_midi(candidate, midi_path)
    measurements = original.render(candidate, wav_path)
    manifest = {
        "title": "Before the toast - kyo join based on A", "version": "0.1",
        "status": "Original instrumental guide; no Miku vocal or perceptual review",
        "python": platform.python_version(), "mido": importlib.metadata.version("mido"),
        "packaging": importlib.metadata.version("packaging"),
        "source_sha256_canonical_json": original.sha256(json.dumps(
            baseline, sort_keys=True, separators=(",", ":")).encode()),
        "original_builder_sha256_lf": original.sha256(
            (ROOT / "build.py").read_text(encoding="utf-8").encode()),
        "candidate_builder_sha256_lf": original.sha256(
            Path(__file__).read_text(encoding="utf-8").encode()),
        "comparison": {
            "baseline": "A", "lead_note_index": 8, "pitch": 72, "on_beat": 8,
            "off_beat": {"baseline": 8.75, "candidate": 9},
            "next_note_on_beat": 9, "review_window_seconds": [5.0, 6.40625],
        },
        "tempo_bpm": candidate["tempo_bpm"], "total_beats": candidate["total_beats"],
        "ticks_per_beat": original.PPQN, "sample_rate_hz": original.SAMPLE_RATE,
        "channels": 1, "sample_width_bytes": 2,
        "attack_seconds": original.ATTACK_SECONDS,
        "release_seconds": original.RELEASE_SECONDS,
        "fixed_gains": original.GAINS,
        "second_harmonic_weights": original.SECOND_HARMONIC,
        "measurements": measurements,
        "sha256": {path.name: original.sha256(path.read_bytes())
                   for path in (midi_path, wav_path)},
        "reproducibility_scope": "Same runtime; cross-platform math not guaranteed. Check with test_kyo_join.py.",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "generated" / "kyo-join")
    args = parser.parse_args()
    build(args.output_dir)
    print("Built kyo-join-A.mid, kyo-join-A.wav, and manifest.json.")
