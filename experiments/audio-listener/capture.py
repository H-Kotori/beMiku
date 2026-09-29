"""Bounded WASAPI loopback capture with conservative source-time coverage."""

import json
import math
import queue
import sys
import threading
import time
import wave
from urllib.parse import urlsplit

from analysis import private_output, write_json


STATES = {"playing", "paused", "buffering", "ended", "unknown"}
MAX_OBSERVATION_GAP = 20.0
MAX_OBSERVATION_AGE = 15.0
CLOCK_TOLERANCE_SECONDS = 0.005


def _number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def validate_observation(data, received_unix, received_monotonic, started_monotonic):
    """Normalize observed data; never use a caller-supplied capture clock."""
    if not isinstance(data, dict) or data.get("type") != "observe":
        raise ValueError("Expected an observe command.")
    source = data.get("source_id")
    if not isinstance(source, str) or len(source) > 2048:
        raise ValueError("Expected a canonical source URL.")
    parsed = urlsplit(source)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Expected a canonical source URL without credentials or fragments.")
    for field in ("media_time_seconds", "duration_seconds", "rate", "observed_at_unix"):
        if not _number(data.get(field)):
            raise ValueError("Observation numeric fields must be finite.")
    if not 0 <= data["media_time_seconds"] <= data["duration_seconds"] or data["duration_seconds"] <= 0 or data["rate"] <= 0:
        raise ValueError("Invalid media position, duration, or rate.")
    age = received_unix - data["observed_at_unix"]
    if not 0 <= age <= MAX_OBSERVATION_AGE:
        raise ValueError("Observation timestamp is stale or in the future.")
    if data.get("state") not in STATES or type(data.get("ad")) is not bool or type(data.get("seeking")) is not bool:
        raise ValueError("Playback state, ad, and seeking must be explicit.")
    result = {key: data[key] for key in (
        "source_id", "media_time_seconds", "duration_seconds", "state", "rate", "ad", "seeking", "observed_at_unix"
    )}
    result["capture_monotonic_seconds"] = received_monotonic - started_monotonic - age
    return result


def _audio_runs(blocks, sample_rate):
    """Group only sample-contiguous blocks whose device clocks also agree."""
    runs = []
    tolerance = max(2 / sample_rate, CLOCK_TOLERANCE_SECONDS)
    for block in blocks:
        if block.get("timing_quality") != "device_clock":
            continue
        if (runs and runs[-1][-1]["end_frame"] == block["start_frame"]
                and abs(runs[-1][-1]["end_monotonic_seconds"] - block["start_monotonic_seconds"]) <= tolerance):
            runs[-1].append(block)
        else:
            runs.append([block])
    return runs


def derive_coverage(observations, blocks, sample_rate, invalid_times=(), uncertain_intervals=()):
    """Return verified mapped spans and rejected pairs; sparse marks are not proof of all playback."""
    coverage, rejected = [], []
    runs = _audio_runs(blocks, sample_rate)
    tolerance = max(2 / sample_rate, CLOCK_TOLERANCE_SECONDS)
    for left, right in zip(observations, observations[1:]):
        start, end = left["capture_monotonic_seconds"], right["capture_monotonic_seconds"]
        elapsed = end - start
        media_delta = right["media_time_seconds"] - left["media_time_seconds"]
        reason = None
        if elapsed <= 0:
            reason = "non_increasing_observation_time"
        elif any(start <= position <= end for position in invalid_times):
            reason = "invalid_observation"
        elif any(start < interval["end_monotonic_seconds"] and end > interval["start_monotonic_seconds"]
                 for interval in uncertain_intervals):
            reason = "unverified_output_device"
        elif elapsed > MAX_OBSERVATION_GAP:
            reason = "observation_gap"
        elif left["source_id"] != right["source_id"] or abs(left["duration_seconds"] - right["duration_seconds"]) > 1:
            reason = "source_changed"
        elif any(mark["state"] != "playing" or mark["rate"] != 1 or mark["ad"] or mark["seeking"] for mark in (left, right)):
            reason = "uncertain_playback"
        elif media_delta <= 0 or abs(media_delta - elapsed) > 1:
            reason = "media_clock_discontinuity"
        run = next((run for run in runs if run[0]["start_monotonic_seconds"] <= start
                    and run[-1]["end_monotonic_seconds"] >= end), None)
        if reason is None and run is None:
            reason = "missing_or_unreliable_audio"
        if reason:
            rejected.append({"start_monotonic_seconds": start, "end_monotonic_seconds": end, "reason": reason})
            continue

        def frame_at(position):
            block = next(block for block in run if block["start_monotonic_seconds"] - tolerance <= position
                         <= block["end_monotonic_seconds"] + tolerance)
            return min(block["end_frame"], max(block["start_frame"],
                       block["start_frame"] + round((position - block["start_monotonic_seconds"]) * sample_rate)))

        first, last = frame_at(start), frame_at(end)
        if last > first:
            coverage.append({"source_id": left["source_id"], "source_start_seconds": left["media_time_seconds"],
                             "source_end_seconds": right["media_time_seconds"], "start_frame": first, "end_frame": last,
                             "file_start_seconds": first / sample_rate, "file_end_seconds": last / sample_rate})
    return coverage, rejected


class Deadlines:
    def __init__(self, started, max_seconds, lease_seconds):
        self.hard = started + max_seconds
        self.lease_seconds = lease_seconds
        self.lease = started + lease_seconds

    def renew(self, received):
        self.lease = max(self.lease, received + self.lease_seconds)

    def reason(self, now):
        if now >= self.hard:
            return "hard_cap"
        if now >= self.lease:
            return "lease_expired"
        return None


def _load_pyaudio():
    import pyaudiowpatch
    return pyaudiowpatch


def list_devices():
    backend = _load_pyaudio()
    with backend.PyAudio() as manager:
        default = manager.get_host_api_info_by_type(backend.paWASAPI)["defaultOutputDevice"]
        return {"default_output_index": default, "devices": [
            {"index": item["index"], "name": item["name"], "channels": item["maxInputChannels"],
             "default_sample_rate": item["defaultSampleRate"], "is_loopback": True}
            for item in manager.get_loopback_device_info_generator()
        ]}


def _default_endpoint_id():
    """Query live CoreAudio, rather than PortAudio's cached default-device list."""
    import ctypes
    import uuid

    ole = ctypes.OleDLL("ole32")
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    ole.CoInitializeEx.restype = ctypes.c_long
    try:
        initialized = ole.CoInitializeEx(None, 0)
    except OSError as error:
        # PortAudio may already have initialized this thread in another apartment.
        # That apartment can still query CoreAudio, but we must not uninitialize it.
        if getattr(error, "winerror", None) != -2147417850:  # RPC_E_CHANGED_MODE
            raise
        initialized = -2147417850
    if initialized < 0 and initialized != -2147417850:
        raise OSError("CoreAudio COM initialization failed.")
    enumerator, device = ctypes.c_void_p(), ctypes.c_void_p()

    def call(pointer, index, *args, argtypes=()):
        table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        method = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(table[index])
        result = method(pointer, *args)
        if result < 0:
            raise OSError("CoreAudio endpoint query failed.")
        return result

    try:
        guid = ctypes.c_ubyte * 16
        clsid = guid.from_buffer_copy(uuid.UUID("BCDE0395-E52F-467C-8E3D-C4579291692E").bytes_le)
        iid = guid.from_buffer_copy(uuid.UUID("A95664D2-9614-4F35-A746-DE8DB63617E6").bytes_le)
        ole.CoCreateInstance.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p]
        ole.CoCreateInstance.restype = ctypes.c_long
        if ole.CoCreateInstance(ctypes.byref(clsid), None, 23, ctypes.byref(iid), ctypes.byref(enumerator)) < 0:
            raise OSError("CoreAudio enumerator unavailable.")
        call(enumerator, 4, 0, 0, ctypes.byref(device), argtypes=(ctypes.c_int, ctypes.c_int, ctypes.c_void_p))
        identifier = ctypes.c_void_p()
        call(device, 5, ctypes.byref(identifier), argtypes=(ctypes.c_void_p,))
        try:
            return ctypes.wstring_at(identifier)
        finally:
            ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
            ole.CoTaskMemFree(identifier)
    finally:
        if device:
            call(device, 2)
        if enumerator:
            call(enumerator, 2)
        if initialized >= 0:
            ole.CoUninitialize()


def _read_commands(source, commands, stopping, faults):
    while not stopping.is_set():
        try:
            line = source.readline(8193)
            if len(line) > 8192:
                faults.put("control_line_too_long")
                return
            data = {"type": "eof"} if not line else json.loads(line)
            commands.put_nowait((data, time.time(), time.monotonic()))
            if not line:
                return
        except json.JSONDecodeError:
            faults.put("invalid_control_json")
            return
        except queue.Full:
            faults.put("control_overflow")
            return
        except Exception:
            faults.put("control_read_failed")
            return


def capture_session(output, max_seconds=600, lease_seconds=60, device_index=None):
    """Capture until finish/EOF/cancellation/failure or a monotonic deadline.

    Stdin is NDJSON. Only a valid, fresh observe command renews the lease.
    Audio is retained locally even when source-time coverage cannot be verified.
    """
    if not _number(max_seconds) or not 0 < max_seconds <= 600 or not _number(lease_seconds) or not 0 < lease_seconds <= 60:
        raise ValueError("Capture cap must be in (0, 600] and lease in (0, 60].")
    output = private_output(output)
    report = {"schema_version": 1, "status": "partial", "stop_reason": "setup_failed", "audio_file": "original.wav",
              "sample_width_bytes": 2, "frames": 0, "blocks": [], "observations": [], "coverage": [],
              "invalid_intervals": [], "audio_gaps": [], "device_intervals": [], "error_flags": [],
              "rejected_observations": 0, "observation_errors": [],
              "limitations": ["WASAPI loopback contains all audio routed to the selected output device.",
                              "Source identity and playback observations are supplied by the supervisor, not proven by the samples.",
                              "Adjacent playback observations cannot rule out every event between them.",
                              "Only bracketed, consistent playback with gap-free device-timed audio has mapped coverage.",
                              "Device-clock adjacency tolerates 5 ms of timestamp jitter; smaller gaps cannot be resolved.",
                              "Complete capture means a clean finish, not complete song coverage."]}
    write_json(output / "capture.json", report)
    manager = stream = writer = None
    stopping = threading.Event()
    audio = queue.Queue(maxsize=128)
    commands = queue.Queue(maxsize=128)
    faults = queue.SimpleQueue()
    started = None
    initial_endpoint = None
    last_endpoint_verified = None
    try:
        backend = _load_pyaudio()
        manager = backend.PyAudio()
        default_index = manager.get_host_api_info_by_type(backend.paWASAPI)["defaultOutputDevice"]
        device = manager.get_default_wasapi_loopback() if device_index is None else manager.get_device_info_by_index(device_index)
        if not device.get("isLoopbackDevice") or device["maxInputChannels"] < 1:
            raise ValueError("Select a WASAPI loopback input device.")
        rate, channels = int(device["defaultSampleRate"]), int(device["maxInputChannels"])
        if not manager.is_format_supported(rate, input_device=device["index"], input_channels=channels, input_format=backend.paInt16):
            raise ValueError("Device does not support PCM16 at its default format.")
        report.update(sample_rate=rate, channels=channels,
                      device={"index": device["index"], "name": device["name"], "default_output_index": default_index})
        initial_endpoint = _default_endpoint_id()
        writer = wave.open(str(output / "original.wav"), "wb")
        writer.setparams((channels, 2, rate, 0, "NONE", "not compressed"))
        clock_origin = 0.0

        def callback(data, count, timing, status):
            received = time.monotonic()
            if stopping.is_set():
                return None, backend.paAbort
            if status:
                faults.put("audio_overflow" if status & backend.paInputOverflow else "audio_callback_status")
                return None, backend.paAbort
            if not data or len(data) != count * channels * 2:
                faults.put("invalid_audio_packet")
                return None, backend.paAbort
            adc, current = timing.get("input_buffer_adc_time"), timing.get("current_time")
            usable_clock = _number(adc) and _number(current) and adc > 0 and current >= adc
            start = adc - clock_origin if usable_clock else received - started - count / rate
            item = (data, count, start, start + count / rate, received - started,
                    "device_clock" if usable_clock else "callback_clock_estimate")
            try:
                audio.put_nowait(item)
            except queue.Full:
                faults.put("audio_queue_overflow")
                return None, backend.paAbort
            return None, backend.paContinue

        stream = manager.open(format=backend.paInt16, channels=channels, rate=rate, input=True,
                              input_device_index=device["index"], frames_per_buffer=1024,
                              stream_callback=callback, start=False)
        started = time.monotonic()
        last_endpoint_verified = started
        clock_origin = stream.get_time()
        report["capture_started_at_unix"] = time.time()
        deadlines = Deadlines(started, max_seconds, lease_seconds)
        stream.start_stream()
        report["stop_reason"] = "capture_failed"

        def watch_device():
            nonlocal last_endpoint_verified
            while not stopping.wait(1):
                try:
                    if _default_endpoint_id() != initial_endpoint:
                        report["device_intervals"].append({"start_monotonic_seconds": last_endpoint_verified - started,
                                                           "end_monotonic_seconds": time.monotonic() - started,
                                                           "reason": "default_output_changed"})
                        faults.put("default_output_changed")
                        return
                    last_endpoint_verified = time.monotonic()
                    if not stream.is_active():
                        faults.put("audio_device_stopped")
                        return
                except Exception:
                    report["device_intervals"].append({"start_monotonic_seconds": last_endpoint_verified - started,
                                                       "end_monotonic_seconds": time.monotonic() - started,
                                                       "reason": "audio_device_check_failed"})
                    faults.put("audio_device_check_failed")
                    return

        threading.Thread(target=watch_device, daemon=True).start()
        threading.Thread(target=_read_commands, args=(sys.stdin, commands, stopping, faults), daemon=True).start()
        print(json.dumps({"event": "capture_ready", "sample_rate": rate, "channels": channels,
                          "max_seconds": max_seconds, "lease_seconds": lease_seconds}), flush=True)
        reason = None
        while reason is None:
            reason = deadlines.reason(time.monotonic())
            if reason:
                break
            try:
                reason = faults.get_nowait()
                break
            except queue.Empty:
                pass
            for _ in range(32):
                try:
                    data, received_unix, received_monotonic = commands.get_nowait()
                except queue.Empty:
                    break
                command = data.get("type") if isinstance(data, dict) else None
                if command in {"finish", "cancel", "eof"}:
                    reason = command
                    break
                try:
                    observation = validate_observation(data, received_unix, received_monotonic, started)
                    if report["observations"] and observation["capture_monotonic_seconds"] <= report["observations"][-1]["capture_monotonic_seconds"]:
                        raise ValueError("Observation timestamps must increase.")
                    report["observations"].append(observation)
                    deadlines.renew(received_monotonic)
                except ValueError:
                    report["rejected_observations"] += 1
                    report["observation_errors"].append({"capture_monotonic_seconds": received_monotonic - started,
                                                         "reason": "invalid_observation"})
            if reason:
                break
            try:
                packet = audio.get(timeout=min(0.05, max(0.001, min(deadlines.hard, deadlines.lease) - time.monotonic())))
            except queue.Empty:
                continue
            _write_packet(writer, packet, report, max_seconds)
        report["stop_reason"] = reason
        if reason not in {"finish", "cancel", "eof", "lease_expired", "hard_cap"}:
            report["error_flags"].append(reason)
    except KeyboardInterrupt:
        report["stop_reason"] = "cancel"
    except Exception as error:
        report["error_flags"].append(type(error).__name__)
        (output / "error.txt").write_text(str(error), encoding="utf-8")
    finally:
        stopping.set()
        ended = time.monotonic()

        def close_audio():
            try:
                try:
                    if stream:
                        stream.close()
                finally:
                    if manager:
                        manager.terminate()
                if initial_endpoint is not None and _default_endpoint_id() != initial_endpoint:
                    if started is not None:
                        report["device_intervals"].append({"start_monotonic_seconds": last_endpoint_verified - started,
                                                           "end_monotonic_seconds": ended - started,
                                                           "reason": "default_output_changed"})
                    faults.put("default_output_changed")
            except Exception:
                faults.put("audio_close_failed")

        closer = threading.Thread(target=close_audio, daemon=True)
        closer.start()
        closer.join(timeout=0.5)
        if closer.is_alive():
            report["error_flags"].append("audio_close_timeout")
        if writer:
            try:
                while not audio.empty():
                    _write_packet(writer, audio.get_nowait(), report, max_seconds)
            except Exception:
                report["error_flags"].append("audio_write_failed")
            finally:
                try:
                    writer.close()
                except Exception:
                    report["error_flags"].append("audio_finalize_failed")
        while not faults.empty():
            report["error_flags"].append(faults.get_nowait())
        report["elapsed_seconds"] = ended - started if started is not None else 0
        if "sample_rate" in report:
            report["duration_seconds"] = report["frames"] / report["sample_rate"]
            report["coverage"], report["invalid_intervals"] = derive_coverage(
                report["observations"], report["blocks"], report["sample_rate"],
                [item["capture_monotonic_seconds"] for item in report["observation_errors"]], report["device_intervals"])
            report["invalid_intervals"].extend(report["audio_gaps"])
            report["invalid_intervals"].extend(report["device_intervals"])
        if not report["frames"]:
            report["error_flags"].append("no_audio_packets")
        report["error_flags"] = sorted(set(report["error_flags"]))
        report["status"] = "complete" if report["stop_reason"] == "finish" and not report["error_flags"] else "partial"
        write_json(output / "capture.json", report)
    return report


def _write_packet(writer, packet, report, max_seconds):
    data, count, start, end, received, quality = packet
    rate, channels = report["sample_rate"], report["channels"]
    count = min(count, max(0, math.floor(max_seconds * rate) - report["frames"]))
    if not count:
        return
    writer.writeframesraw(data[:count * channels * 2])
    if quality != "device_clock":
        report["error_flags"].append("audio_clock_unavailable")
    elif report["blocks"]:
        previous = report["blocks"][-1]
        previous_end = previous["end_monotonic_seconds"]
        if previous["timing_quality"] == "device_clock" and abs(start - previous_end) > max(2 / rate, CLOCK_TOLERANCE_SECONDS):
            reason = "missing_audio_packets" if start > previous_end else "audio_clock_discontinuity"
            report["error_flags"].append(reason)
            report["audio_gaps"].append({"start_monotonic_seconds": min(start, previous_end),
                                          "end_monotonic_seconds": max(start, previous_end), "reason": reason})
    report["blocks"].append({"start_frame": report["frames"], "end_frame": report["frames"] + count,
                             "start_monotonic_seconds": start, "end_monotonic_seconds": start + count / rate,
                             "received_monotonic_seconds": received, "timing_quality": quality})
    report["frames"] += count
