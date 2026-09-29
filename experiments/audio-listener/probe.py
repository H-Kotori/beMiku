"""Blinded audio controls and the existing private 39 passage; no audio downloads."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from analysis import LocalAudioModel, ROOT, analyze_file, private_output, write_json


def fixtures(output):
    rate = 44100
    silence = np.zeros((12 * rate, 2), dtype=np.float32)
    tones = silence.copy()
    for start, end, frequency, channel in [(1, 3, 440, 0), (4, 6, 660, 1), (7, 9, 880, 0)]:
        t = np.arange((end - start) * rate) / rate
        envelope = np.minimum(1, t / 0.02) * np.minimum(1, (end - start - t) / 0.02)
        tones[start * rate:end * rate, channel] = 0.2 * np.sin(2 * np.pi * frequency * t) * envelope
    sf.write(output / "control-a.wav", silence, rate, subtype="PCM_16")
    sf.write(output / "control-b.wav", tones, rate, subtype="PCM_16")
    sf.write(output / "control-c.wav", tones[::-1], rate, subtype="PCM_16")
    sparse = np.zeros((25 * rate, 2), dtype=np.float32)
    for start, frequency in [(0, 440), (10, 660), (20, 880)]:
        t = np.arange(2 * rate) / rate
        sparse[start * rate:(start + 2) * rate, :] = (0.05 * np.sin(2 * np.pi * frequency * t))[:, None]
    sf.write(output / "control-e.wav", sparse, rate, subtype="PCM_16")
    sf.write(output / "control-f.wav", sparse[::-1], rate, subtype="PCM_16")
    return [
        (output / "control-a.wav", 0, "Digital silence, 12 seconds; no voice or instruments."),
        (output / "control-b.wav", 0, "Three separated rising sine tones, alternating channels; final three seconds silent."),
        (output / "control-c.wav", 0, "Same signal reversed in time: three descending tones; initial three seconds silent."),
        (output / "control-e.wav", 0, "Three quiet sine tones at 0–2, 10–12, 20–22s; long silent gaps; no vocals or instruments."),
        (output / "control-f.wav", 0, "Previous sparse signal reversed; same long silent gaps, descending tones."),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--passage", type=Path, help="The existing 32-second crop; not its title or lyrics.")
    args = parser.parse_args()
    output = private_output(args.output)
    trials = fixtures(output)
    if args.passage:
        info = sf.info(args.passage)
        if abs(info.duration - 32) > 1 / info.samplerate:
            raise ValueError("The supplied reference crop must be 32 seconds long.")
        trials.append((args.passage, 40, "Owner-supplied 39 crop, source 40–72s; exact master unverified."))
        samples, rate = sf.read(args.passage, dtype="float32", always_2d=True)
        sf.write(output / "control-d.wav", samples[::-1], rate, subtype="FLOAT")
        trials.append((output / "control-d.wav", 0, "Previous crop reversed in time; source-time mapping does not apply."))
        masked = samples[:25 * rate].copy()
        masked[12 * rate:] = 0
        sf.write(output / "control-g.wav", masked, rate, subtype="FLOAT")
        trials.append((output / "control-g.wav", 0, "Music through 12s followed by 13s of digital silence."))
    try:
        model = LocalAudioModel()
        summary = []
        for index, (path, offset, truth) in enumerate(trials):
            report = analyze_file(path, output / f"trial-{index + 1}", source_offset=offset, model=model)
            summary.append({"trial": index + 1, "control_truth_not_given_to_model": truth,
                            "status": report["status"], "report": f"trial-{index + 1}/report.json"})
            write_json(output / "probe.json", summary)
            print(json.dumps({"event": "trial_complete", "trial": index + 1, "clips": len(report["clips"])}), flush=True)
    except (Exception, KeyboardInterrupt) as error:
        (output / "error.txt").write_text(str(error), encoding="utf-8")
        write_json(output / "probe-status.json", {"status": "failed", "error_type": type(error).__name__})
        raise


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({"event": "probe_failed", "error_type": type(error).__name__}), file=sys.stderr)
        sys.exit(1)
