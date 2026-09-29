"""Windows hardware checks: play authored tones or test the unattended 60-second lease.

The existing output device and volume are used unchanged. All recordings and
detailed diagnostics stay under a fresh ignored local/ output directory.
"""

import argparse
import json
import math
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from analysis import ROOT, private_output, sha256, write_json


TONE_SECONDS = 12
TONES = [(1, 3, 440, 0), (4, 6, 660, 1), (7, 9, 880, 0)]


def make_fixture(path):
    rate = 44100
    samples = np.zeros((TONE_SECONDS * rate, 2), dtype=np.float32)
    for start, end, frequency, channel in TONES:
        position = np.arange((end - start) * rate) / rate
        envelope = np.minimum(1, position / 0.02) * np.minimum(1, (end - start - position) / 0.02)
        samples[start * rate:end * rate, channel] = 0.2 * np.sin(2 * np.pi * frequency * position) * envelope
    sf.write(path, samples, rate, subtype="PCM_16")


def measure_tones(path):
    samples, rate = sf.read(path, dtype="float64", always_2d=True)
    regions = []
    hop = max(1, round(rate * 0.01))
    if len(samples):
        rms = np.array([np.sqrt(np.mean(samples[index:index + hop] ** 2, axis=0))
                        for index in range(0, len(samples), hop)])
        for channel in range(samples.shape[1]):
            active = rms[:, channel] > max(1e-5, rms[:, channel].max() * 0.15)
            edges = np.diff(np.r_[False, active, False].astype(int))
            for first, last in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
                if (last - first) * hop / rate < 0.2:
                    continue
                chunk = samples[first * hop:min(last * hop, len(samples)), channel]
                spectrum = np.abs(np.fft.rfft(chunk * np.hanning(len(chunk))))
                frequency = np.fft.rfftfreq(len(chunk), 1 / rate)[int(np.argmax(spectrum))]
                regions.append({"channel": channel, "start_seconds": first * hop / rate,
                                "end_seconds": min(last * hop, len(samples)) / rate,
                                "peak_frequency_hz": float(frequency),
                                "rms": float(np.sqrt(np.mean(chunk ** 2)))})
    regions.sort(key=lambda item: item["start_seconds"])
    trailing = len(samples) / rate - max((item["end_seconds"] for item in regions), default=0)
    matches = len(regions) == len(TONES) and all(
        region["channel"] == channel and abs(region["peak_frequency_hz"] - frequency) <= 2
        and abs(region["end_seconds"] - region["start_seconds"] - (end - start)) <= 0.12
        for region, (start, end, frequency, channel) in zip(regions, TONES)
    )
    offsets = [region["start_seconds"] - tone[0] for region, tone in zip(regions, TONES)]
    return {"tone_regions": regions, "trailing_low_signal_seconds": trailing,
            "checks": {"stereo": samples.shape[1] == 2, "frequencies_channels_and_durations": matches,
                       "relative_onsets": len(offsets) == 3 and max(offsets) - min(offsets) <= 0.1,
                       "trailing_low_signal": trailing >= 2.8},
            "limitations": ["Relative signal thresholds cannot distinguish all unrelated output sounds.",
                            "These checks do not establish bit-perfect fidelity or exact absolute synchronization."]}


def _send(child, message):
    child.stdin.write(json.dumps(message) + "\n")
    child.stdin.flush()


def _play_fixture(fixture, child, times):
    import pyaudiowpatch as pa

    samples, fixture_rate = sf.read(fixture, dtype="float32", always_2d=True)
    done = threading.Event()
    errors = []
    with pa.PyAudio() as manager:
        device = manager.get_host_api_info_by_type(pa.paWASAPI)["defaultOutputDevice"]
        output_rate = int(manager.get_device_info_by_index(device)["defaultSampleRate"])
        factor = math.gcd(output_rate, fixture_rate)
        converted = resample_poly(samples, output_rate // factor, fixture_rate // factor)
        pcm = np.clip(np.round(converted * 32767), -32768, 32767).astype("<i2")

        def play():
            try:
                with manager.open(format=pa.paInt16, channels=2, rate=output_rate, output=True,
                                  output_device_index=device, frames_per_buffer=1024) as stream:
                    times["play_started"] = time.monotonic()
                    for first in range(0, len(pcm), 1024):
                        stream.write(pcm[first:first + 1024].tobytes())
                times["play_finished"] = time.monotonic()
            except Exception as error:
                errors.append(type(error).__name__)
            finally:
                done.set()

        time.sleep(0.4)
        started = time.monotonic()
        threading.Thread(target=play, daemon=True).start()
        next_observation = 0.5
        while not done.wait(0.05):
            now = time.monotonic()
            if now - started > 20:
                raise RuntimeError("Authored playback exceeded its test bound.")
            position = now - times.get("play_started", now)
            if next_observation <= position < TONE_SECONDS:
                _send(child, {"type": "observe", "source_id": "https://example.invalid/beMiku/authored-stereo-control",
                              "media_time_seconds": position, "duration_seconds": TONE_SECONDS,
                              "state": "playing", "rate": 1, "ad": False, "seeking": False,
                              "observed_at_unix": time.time()})
                next_observation += 2
        if errors:
            raise RuntimeError("Authored playback failed: " + errors[0])
    return output_rate


def verify(mode, output):
    if mode not in {"tones", "lease"}:
        raise ValueError("Choose tones or lease.")
    output = private_output(output)
    child = None
    lines, reader_errors = [], []
    ready, finished = threading.Event(), threading.Event()
    times = {}
    try:
        if sys.platform != "win32":
            raise RuntimeError("The hardware checks require Windows.")
        fixture = output / "authored-stereo-tones.wav"
        if mode == "tones":
            make_fixture(fixture)
        destination = output / "capture"
        with (output / "capture-stderr.txt").open("w", encoding="utf-8") as stderr_file:
            child = subprocess.Popen([sys.executable, str(Path(__file__).with_name("listen.py")), "capture",
                                      "--output", str(destination)], cwd=ROOT, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=stderr_file, text=True, encoding="utf-8", bufsize=1,
                                     creationflags=subprocess.CREATE_NO_WINDOW)

            def read_output():
                try:
                    for line in child.stdout:
                        lines.append(line)
                        message = json.loads(line)
                        if message.get("event") == "capture_ready":
                            times["ready"] = time.monotonic()
                            ready.set()
                        elif message.get("event") == "capture_finished":
                            times["finished"] = time.monotonic()
                            finished.set()
                except Exception as error:
                    reader_errors.append(type(error).__name__)

            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()
            start_deadline = time.monotonic() + 20
            while not ready.wait(0.05):
                if child.poll() is not None or reader_errors or time.monotonic() >= start_deadline:
                    raise RuntimeError("Capture did not become ready.")
            if mode == "tones":
                output_rate = _play_fixture(fixture, child, times)
                time.sleep(0.25)
                times["finish_sent"] = time.monotonic()
                _send(child, {"type": "finish"})
                deadline = times["finish_sent"] + 3
            else:
                # Keep stdin open and send no observations or lease renewals.
                deadline = times["ready"] + 61
            if not finished.wait(max(0, deadline - time.monotonic())):
                raise RuntimeError("Capture exceeded its shutdown bound.")
            child.wait(timeout=max(0.001, deadline - time.monotonic()))
            times["exited"] = time.monotonic()
            reader.join(timeout=0.2)
        report = json.loads((destination / "capture.json").read_text(encoding="utf-8"))
        recording_info = sf.info(destination / "original.wav")
        result = {"mode": mode, "capture_status": report["status"], "stop_reason": report["stop_reason"],
                  "sample_rate": recording_info.samplerate, "channels": recording_info.channels,
                  "frames": recording_info.frames, "duration_seconds": recording_info.duration,
                  "capture_elapsed_seconds": report["elapsed_seconds"], "error_flags": report["error_flags"],
                  "coverage_intervals": len(report["coverage"]),
                  "covered_file_seconds": sum(span["file_end_seconds"] - span["file_start_seconds"] for span in report["coverage"]),
                  "block_count": len(report["blocks"]),
                  "native_clock_blocks": sum(block["timing_quality"] == "device_clock" for block in report["blocks"]),
                  "gap_count": len(report["audio_gaps"]), "rejected_observations": report["rejected_observations"],
                  "ready_to_report_seconds": times["finished"] - times["ready"],
                  "ready_to_exit_seconds": times["exited"] - times["ready"], "capture_exit_code": child.returncode}
        if mode == "tones":
            result.update(measure_tones(destination / "original.wav"))
            result.update(source_fixture_seconds=TONE_SECONDS, source_fixture_sha256=sha256(fixture),
                          playback_wall_seconds=times["play_finished"] - times["play_started"], playback_output_rate=output_rate,
                          finish_to_report_seconds=times["finished"] - times["finish_sent"],
                          finish_to_exit_seconds=times["exited"] - times["finish_sent"],
                          observation_basis="Synthetic supervisor-clock playback observations; not browser state or hardware DAC timing.")
            result["checks"]["explicit_finish"] = report["stop_reason"] == "finish"
        else:
            result["checks"] = {"lease_expired": report["stop_reason"] == "lease_expired",
                                "sixty_second_lease": 59.9 <= report["elapsed_seconds"] <= 61,
                                "exit_within_61_seconds": result["ready_to_exit_seconds"] <= 61,
                                "no_observations": not report["observations"]}
        result["checks"]["recording_matches_report"] = (
            recording_info.frames == report["frames"] and recording_info.samplerate == report.get("sample_rate")
            and recording_info.channels == report.get("channels") and recording_info.subtype == "PCM_16")
        result["hardware_checks_passed"] = all(result["checks"].values())
        write_json(output / "results.json", result)
        return result
    except (Exception, KeyboardInterrupt) as error:
        (output / "error.txt").write_text(str(error), encoding="utf-8")
        write_json(output / "results.json", {"mode": mode, "hardware_checks_passed": False,
                                            "error_type": type(error).__name__})
        raise
    finally:
        if child is not None:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
            child.stdin.close()
        (output / "capture-events.ndjson").write_text("".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("tones", "lease"))
    parser.add_argument("--output", required=True, type=Path, help="Fresh directory under ignored local/.")
    args = parser.parse_args()
    try:
        result = verify(args.mode, args.output)
        print(json.dumps({"event": "hardware_check_finished", "mode": args.mode,
                          "hardware_checks_passed": result["hardware_checks_passed"],
                          "capture_status": result["capture_status"], "reason": result["stop_reason"]}), flush=True)
        return 0 if result["hardware_checks_passed"] else 2
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({"event": "hardware_check_failed", "error_type": type(error).__name__,
                          "message": "Inspect diagnostics in the private output directory if it was created."}), flush=True)
        return 130 if isinstance(error, KeyboardInterrupt) else 1


if __name__ == "__main__":
    sys.exit(main())
