"""Capture policy tests use fake devices and input; no real audio is recorded."""

import io
import json
import tempfile
import sys
import threading
import time
import unittest
import wave
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import capture


URL = "https://www.youtube.com/watch?v=test"


def observation(position=0, offset=0, **changes):
    value = {"type": "observe", "source_id": URL, "media_time_seconds": position,
             "duration_seconds": 100, "state": "playing", "rate": 1, "ad": False,
             "seeking": False, "observed_at_unix": 1000 + offset,
             "capture_monotonic_seconds": offset}
    value.update(changes)
    return value


def block(start, end, first=None, rate=100, **changes):
    first = round(start * rate) if first is None else first
    value = {"start_frame": first, "end_frame": first + round((end - start) * rate),
             "start_monotonic_seconds": start, "end_monotonic_seconds": end,
             "timing_quality": "device_clock"}
    value.update(changes)
    return value


class ObservationTests(unittest.TestCase):
    def test_wall_time_converts_to_capture_clock(self):
        result = capture.validate_observation(observation(30, 5), 1007, 107, 100)
        self.assertEqual(result["capture_monotonic_seconds"], 5)
        self.assertNotIn("type", result)

    def test_stale_future_and_nonfinite_marks_fail(self):
        for timestamp in (980, 1001, float("nan"), float("inf"), True):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                capture.validate_observation(observation(observed_at_unix=timestamp), 1000, 100, 100)

    def test_playback_fields_must_be_explicit(self):
        for fields in ({"ad": None}, {"seeking": 0}, {"state": "unobserved"}, {"rate": 0},
                       {"duration_seconds": float("inf")}, {"media_time_seconds": -1}, {"source_id": "file:///private"},
                       {"source_id": "https://name:secret@example.test/music"}, {"source_id": URL + "#fragment"}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                capture.validate_observation(observation(**fields), 1000, 100, 100)


class CoverageTests(unittest.TestCase):
    def test_only_bracketed_audio_has_source_time(self):
        marks = [observation(40, 2), observation(50, 12)]
        result, invalid = capture.derive_coverage(marks, [block(0, 20)], 100)
        self.assertEqual(invalid, [])
        self.assertEqual(result, [{"source_id": URL, "source_start_seconds": 40, "source_end_seconds": 50,
                                  "start_frame": 200, "end_frame": 1200,
                                  "file_start_seconds": 2, "file_end_seconds": 12}])

    def test_known_callback_gap_is_not_silence(self):
        audio = [block(0, 5), block(6, 15, first=500)]
        result, invalid = capture.derive_coverage([observation(0, 0), observation(10, 10)], audio, 100)
        self.assertFalse(result)
        self.assertEqual(invalid[0]["reason"], "missing_or_unreliable_audio")

    def test_small_sample_rounding_is_tolerated_but_not_clock_jumps(self):
        marks = [observation(1, 1), observation(9, 9)]
        self.assertTrue(capture.derive_coverage(marks, [block(0, 5), block(5.01, 10.01, first=500)], 100)[0])
        self.assertFalse(capture.derive_coverage(marks, [block(0, 5), block(4.9, 9.9, first=500)], 100)[0])

    def test_measured_device_clock_jitter_is_bounded_not_silently_zero_filled(self):
        rate = 48000
        marks = [observation(1, 1), observation(9, 9)]
        audio = [block(0, 5, rate=rate), block(5.002, 10.002, first=5 * rate, rate=rate)]
        self.assertTrue(capture.derive_coverage(marks, audio, rate)[0])
        audio[1] = block(5.01, 10.01, first=5 * rate, rate=rate)
        self.assertFalse(capture.derive_coverage(marks, audio, rate)[0])

    def test_unreliable_device_clock_cannot_verify_coverage(self):
        marks = [observation(1, 1), observation(9, 9)]
        self.assertFalse(capture.derive_coverage(marks, [block(0, 10, timing_quality="callback_clock_estimate")], 100)[0])

    def test_source_pause_seek_ad_rate_and_sparse_marks_exclude_span(self):
        for fields in ({"source_id": "https://example.test/other"}, {"duration_seconds": 105}, {"state": "paused"},
                       {"state": "buffering"}, {"state": "ended"}, {"seeking": True}, {"ad": True}, {"rate": 1.5},
                       {"media_time_seconds": 40}, {"capture_monotonic_seconds": 30}, {"capture_monotonic_seconds": 0}):
            with self.subTest(fields=fields):
                marks = [observation(0, 0), observation(10, 10, **fields)]
                result, invalid = capture.derive_coverage(marks, [block(0, 40)], 100)
                self.assertFalse(result)
                self.assertEqual(len(invalid), 1)

    def test_invalid_observation_breaks_otherwise_consistent_pair(self):
        result, invalid = capture.derive_coverage([observation(0, 0), observation(10, 10)], [block(0, 10)], 100, [5])
        self.assertFalse(result)
        self.assertEqual(invalid[0]["reason"], "invalid_observation")

    def test_valid_later_pair_survives_prior_seek(self):
        marks = [observation(0, 0), observation(40, 10), observation(50, 20)]
        result, invalid = capture.derive_coverage(marks, [block(0, 25)], 100)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_start_seconds"], 40)
        self.assertEqual(invalid[0]["reason"], "media_clock_discontinuity")

    def test_device_change_uncertainty_excludes_overlapping_source_span(self):
        marks = [observation(0, 0), observation(10, 10), observation(20, 20)]
        uncertain = [{"start_monotonic_seconds": 12, "end_monotonic_seconds": 13}]
        result, invalid = capture.derive_coverage(marks, [block(0, 25)], 100, uncertain_intervals=uncertain)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_end_seconds"], 10)
        self.assertEqual(invalid[0]["reason"], "unverified_output_device")


class DeadlineTests(unittest.TestCase):
    def test_lease_and_hard_cap_are_independent_of_packets(self):
        deadlines = capture.Deadlines(100, 100, 10)
        self.assertIsNone(deadlines.reason(109.9))
        self.assertEqual(deadlines.reason(110), "lease_expired")
        deadlines.renew(108)
        self.assertIsNone(deadlines.reason(117))
        deadlines.renew(199)
        self.assertEqual(deadlines.reason(200), "hard_cap")


class CoreAudioTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows COM query")
    def test_existing_com_apartment_is_reused_without_uninitializing(self):
        ole = MagicMock()
        mismatch = OSError("existing apartment")
        mismatch.winerror = -2147417850
        ole.CoInitializeEx.side_effect = mismatch
        ole.CoCreateInstance.return_value = -1
        with patch("ctypes.OleDLL", return_value=ole), self.assertRaisesRegex(OSError, "enumerator unavailable"):
            capture._default_endpoint_id()
        ole.CoCreateInstance.assert_called_once()
        ole.CoUninitialize.assert_not_called()


class BlockingInput:
    def __init__(self):
        self.release = threading.Event()

    def readline(self, limit):
        self.release.wait(5)
        return ""


class FakeStream:
    def __init__(self, callback, packet=False, status=0):
        self.callback, self.packet, self.status = callback, packet, status
        self.closed = False

    def get_time(self):
        return 100

    def start_stream(self):
        if self.packet:
            self.callback(b"\x00\x00" * 10, 10, {"input_buffer_adc_time": 100, "current_time": 100.1}, self.status)

    def is_active(self):
        return not self.closed

    def close(self):
        self.closed = True


class FakeManager:
    def __init__(self, packet=False, status=0):
        self.packet, self.status = packet, status
        self.stream = None

    def get_host_api_info_by_type(self, api):
        return {"defaultOutputDevice": 1}

    def get_default_wasapi_loopback(self):
        return {"index": 2, "name": "Fake loopback", "isLoopbackDevice": True,
                "maxInputChannels": 1, "defaultSampleRate": 100}

    def is_format_supported(self, *args, **kwargs):
        return True

    def open(self, **kwargs):
        self.stream = FakeStream(kwargs["stream_callback"], self.packet, self.status)
        return self.stream

    def terminate(self):
        pass


class FakeBackend:
    paWASAPI, paInt16, paAbort, paContinue, paInputOverflow = 1, 2, 3, 4, 8

    def __init__(self, manager):
        self.manager = manager

    def PyAudio(self):
        return self.manager


class CaptureTests(unittest.TestCase):
    def run_capture(self, input_stream, manager=None, endpoints=None, **kwargs):
        manager = manager or FakeManager()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "capture"

            def private(path):
                path.mkdir()
                return path

            with patch.object(capture, "private_output", private), patch.object(capture, "_load_pyaudio", return_value=FakeBackend(manager)), \
                    patch.object(capture, "_default_endpoint_id", side_effect=endpoints, return_value="fake"), patch.object(capture.sys, "stdin", input_stream), \
                    redirect_stdout(io.StringIO()):
                report = capture.capture_session(output, **kwargs)
            self.assertEqual(json.loads((output / "capture.json").read_text()), report)
            with wave.open(str(output / "original.wav")) as recording:
                self.assertEqual(recording.getnframes(), report["frames"])
                self.assertEqual(recording.getsampwidth(), 2)
            self.assertTrue(manager.stream.closed)
            return report

    def test_blocked_input_and_absent_audio_do_not_disable_lease(self):
        source = BlockingInput()
        started = time.monotonic()
        try:
            report = self.run_capture(source, lease_seconds=0.04)
        finally:
            source.release.set()
        self.assertEqual(report["stop_reason"], "lease_expired")
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(report["status"], "partial")
        self.assertIn("no_audio_packets", report["error_flags"])

    def test_hard_cap_stops_without_input_or_audio(self):
        source = BlockingInput()
        try:
            report = self.run_capture(source, max_seconds=0.03, lease_seconds=0.5)
        finally:
            source.release.set()
        self.assertEqual(report["stop_reason"], "hard_cap")

    def test_finish_flushes_queued_pcm_but_never_invents_coverage(self):
        report = self.run_capture(io.StringIO('{"type":"finish"}\n'), FakeManager(packet=True))
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["frames"], 10)
        self.assertEqual(report["coverage"], [])

    def test_eof_and_cancel_keep_partial_audio(self):
        for text, reason in (("", "eof"), ('{"type":"cancel"}\n', "cancel")):
            with self.subTest(reason=reason):
                report = self.run_capture(io.StringIO(text), FakeManager(packet=True))
                self.assertEqual(report["stop_reason"], reason)
                self.assertEqual(report["status"], "partial")
                self.assertEqual(report["frames"], 10)

    def test_overflow_aborts_capture_and_is_not_recorded_as_silence(self):
        report = self.run_capture(io.StringIO('{"type":"finish"}\n'), FakeManager(packet=True, status=8))
        self.assertEqual(report["stop_reason"], "audio_overflow")
        self.assertIn("audio_overflow", report["error_flags"])
        self.assertEqual(report["frames"], 0)

    def test_bad_json_stops_bounded_capture(self):
        report = self.run_capture(io.StringIO("invalid json\n"))
        self.assertEqual(report["stop_reason"], "invalid_control_json")

    def test_live_endpoint_change_marks_even_clean_finish_partial(self):
        report = self.run_capture(io.StringIO('{"type":"finish"}\n'), FakeManager(packet=True), endpoints=["before", "after"])
        self.assertEqual(report["status"], "partial")
        self.assertIn("default_output_changed", report["error_flags"])

    def test_packet_queue_overflow_stops_capture(self):
        class FullQueueStream(FakeStream):
            def start_stream(self):
                for index in range(129):
                    self.callback(b"\x00\x00" * 10, 10,
                                  {"input_buffer_adc_time": 100 + index / 10, "current_time": 100.1 + index / 10}, 0)

        class FullQueueManager(FakeManager):
            def open(self, **kwargs):
                self.stream = FullQueueStream(kwargs["stream_callback"])
                return self.stream

        report = self.run_capture(io.StringIO('{"type":"finish"}\n'), FullQueueManager())
        self.assertEqual(report["stop_reason"], "audio_queue_overflow")
        self.assertEqual(report["status"], "partial")

    def test_writer_keeps_missing_packet_gap_explicit(self):
        report = {"sample_rate": 100, "channels": 1, "frames": 0, "blocks": [], "error_flags": [], "audio_gaps": []}
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as writer:
                writer.setparams((1, 2, 100, 0, "NONE", "not compressed"))
                capture._write_packet(writer, (b"\0\0" * 100, 100, 0, 1, 1, "device_clock"), report, 10)
                capture._write_packet(writer, (b"\0\0" * 100, 100, 2, 3, 3, "device_clock"), report, 10)
        self.assertEqual(report["frames"], 200)
        self.assertIn("missing_audio_packets", report["error_flags"])
        self.assertEqual(report["audio_gaps"], [{"start_monotonic_seconds": 1, "end_monotonic_seconds": 2,
                                                "reason": "missing_audio_packets"}])


if __name__ == "__main__":
    unittest.main()
