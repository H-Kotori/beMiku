"""Export one authored A/B phrase experiment; never accesses devices or the network."""

import argparse
from array import array
from copy import deepcopy
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import sys
import wave

import mido


ROOT = Path(__file__).resolve().parent
PPQN = 480
SAMPLE_RATE = 44100
ATTACK_SECONDS = 0.01
RELEASE_SECONDS = 0.08
# Fixed between A and B, with no normalization or dynamic processing.
GAINS = {"lead": 0.22, "backing": 0.08}
SECOND_HARMONIC = {"lead": 0.18, "backing": 0.10}


def validate(score):
    for name in ("lead", "backing"):
        for start, end, pitch, velocity in score[name]:
            if not 0 <= start < end <= score["total_beats"]:
                raise ValueError(f"Invalid {name} note bounds")
            if not (start * PPQN).is_integer() or not (end * PPQN).is_integer():
                raise ValueError("Note times must fall on the 480-tick grid")
            if not isinstance(pitch, int) or not 0 <= pitch <= 127:
                raise ValueError("MIDI pitch must be an integer from 0 to 127")
            if not isinstance(velocity, int) or not 1 <= velocity <= 127:
                raise ValueError("MIDI velocity must be an integer from 1 to 127")
    lead = sorted(score["lead"])
    if any(a[1] > b[0] for a, b in zip(lead, lead[1:])):
        raise ValueError("The lead must be monophonic")


def write_midi(score, path):
    midi = mido.MidiFile(type=1, ticks_per_beat=PPQN)
    end_tick = round(score["total_beats"] * PPQN)
    meta = mido.MidiTrack()
    midi.tracks.append(meta)
    meta.extend([
        mido.MetaMessage("track_name", name=score["title"]),
        mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(score["tempo_bpm"])),
        mido.MetaMessage("time_signature", numerator=score["time_signature"][0],
                         denominator=score["time_signature"][1]),
        mido.MetaMessage("key_signature", key=score["key"]),
    ])
    last = 0
    for beat, label in [(0, "Line 1"), (8, "Line 2"), (16, "Line 3"), (24, "Line 4")]:
        tick = beat * PPQN
        meta.append(mido.MetaMessage("marker", text=label, time=tick - last))
        last = tick
    meta.append(mido.MetaMessage("end_of_track", time=end_tick - last))
    for channel, name in enumerate(("lead", "backing")):
        track = mido.MidiTrack()
        midi.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=name))
        track.append(mido.Message("program_change", channel=channel, program=0))
        events = []
        for start, end, pitch, velocity in score[name]:
            events.extend([
                (round(start * PPQN), 1, mido.Message("note_on", channel=channel,
                                                    note=pitch, velocity=velocity)),
                (round(end * PPQN), 0, mido.Message("note_off", channel=channel,
                                                  note=pitch, velocity=0)),
            ])
        last = 0
        # End a repeated pitch before starting it again on the same tick.
        for tick, _, message in sorted(events, key=lambda event: event[:2]):
            track.append(message.copy(time=tick - last))
            last = tick
        track.append(mido.MetaMessage("end_of_track", time=end_tick - last))
    midi.save(path)


def render(score, path):
    seconds_per_beat = 60 / score["tempo_bpm"]
    frame_count = round(score["total_beats"] * seconds_per_beat * SAMPLE_RATE)
    samples = array("d", [0.0]) * frame_count
    attack = round(ATTACK_SECONDS * SAMPLE_RATE)
    release = round(RELEASE_SECONDS * SAMPLE_RATE)
    for name in ("lead", "backing"):
        second = SECOND_HARMONIC[name]
        for start, end, pitch, velocity in score[name]:
            on = round(start * seconds_per_beat * SAMPLE_RATE)
            off = round(end * seconds_per_beat * SAMPLE_RATE)
            if off + release > frame_count:
                raise ValueError("Leave room for the preview release before the end")
            amplitude = GAINS[name] * velocity / 127
            step = math.tau * 440 * 2 ** ((pitch - 69) / 12) / SAMPLE_RATE
            for frame in range(on, off + release):
                age = frame - on
                envelope = min(1.0, age / attack)
                if frame >= off:
                    envelope *= 1 - (frame - off) / release
                phase = age * step
                tone = (1 - second) * math.sin(phase) + second * math.sin(2 * phase)
                samples[frame] += amplitude * envelope * tone
    peak = max(abs(sample) for sample in samples)
    if peak >= 1:
        raise ValueError("Preview would clip; reduce the fixed gains for both versions")
    pcm = array("h", (round(sample * 32767) for sample in samples))
    if sys.byteorder != "little":
        pcm.byteswap()
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(pcm.tobytes())
    rms = math.sqrt(sum(sample * sample for sample in samples) / frame_count)
    return {"frames": frame_count, "seconds": frame_count / SAMPLE_RATE,
            "peak_linear_before_quantization": peak, "rms_linear_before_quantization": rms}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def build(output_dir):
    score = json.loads((ROOT / "score.json").read_text(encoding="utf-8"))
    # Convert only times to floats, retaining integer MIDI pitch and velocity.
    for name in ("lead", "backing"):
        score[name] = [[float(start), float(end), pitch, velocity]
                       for start, end, pitch, velocity in score[name]]
    variants = {"A": score, "B": deepcopy(score)}
    comparison = score["comparison"]
    target = score["lead"][comparison["lead_index"]]
    variants["B"]["lead"][comparison["lead_index"]][1] = float(comparison["earlier_end_beat"])
    for variant in variants.values():
        validate(variant)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = {}
    hashes = {}
    for label, variant in variants.items():
        midi_path = output_dir / f"{label}.mid"
        wav_path = output_dir / f"{label}.wav"
        write_midi(variant, midi_path)
        metrics[label] = render(variant, wav_path)
        for path in (midi_path, wav_path):
            hashes[path.name] = sha256(path.read_bytes())
    manifest = {
        "title": score["title"], "version": score["version"],
        "status": "Original instrumental guide; no Miku vocal or perceptual review",
        "python": platform.python_version(), "mido": importlib.metadata.version("mido"),
        "packaging": importlib.metadata.version("packaging"),
        "source_sha256_canonical_json": sha256(json.dumps(score, sort_keys=True,
                                                         separators=(",", ":")).encode()),
        "builder_sha256_lf": sha256(Path(__file__).read_text(encoding="utf-8").encode()),
        "tempo_bpm": score["tempo_bpm"], "total_beats": score["total_beats"],
        "ticks_per_beat": PPQN, "sample_rate_hz": SAMPLE_RATE,
        "channels": 1, "sample_width_bytes": 2,
        "attack_seconds": ATTACK_SECONDS, "release_seconds": RELEASE_SECONDS,
        "fixed_gains": GAINS, "second_harmonic_weights": SECOND_HARMONIC,
        "comparison": {
            "lead_note_index": comparison["lead_index"], "pitch": target[2],
            "on_beat": target[0],
            "off_beat": {label: variant["lead"][comparison["lead_index"]][1]
                         for label, variant in variants.items()},
            "next_phrase_beat": 16,
            "review_window_seconds": [7.5, 11.25],
        },
        "measurements": metrics, "sha256": hashes,
        "reproducibility_scope": "Same runtime; cross-platform math not guaranteed. Check with test_build.py.",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "generated")
    args = parser.parse_args()
    build(args.output_dir)
    print("Built A.mid, B.mid, A.wav, B.wav, and manifest.json.")
