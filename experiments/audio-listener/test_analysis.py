"""Behavioral checks with authored audio and a fake model; no weights or GPU needed."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf

import analysis
import listen


class FakeModel:
    load_seconds = 0

    def __init__(self):
        self.inputs = []

    def describe(self, audio):
        if not isinstance(audio, np.ndarray) or audio.ndim != 1:
            raise AssertionError("The model must receive only a mono sample array.")
        self.inputs.append(audio.copy())
        return {"text": "Synthetic test observation."}


class WindowTests(unittest.TestCase):
    def test_short_boundary_and_overlapping_windows(self):
        cases = {
            1: [(0, 1)],
            25: [(0, 25)],
            26: [(0, 25), (20, 26)],
            32: [(0, 25), (20, 32)],
            45: [(0, 25), (20, 45)],
            46: [(0, 25), (20, 45), (40, 46)],
        }
        for duration, expected in cases.items():
            with self.subTest(duration=duration):
                spans = list(analysis.windows(duration * 10, 10))
                self.assertEqual(spans, [(a * 10, b * 10) for a, b in expected])
                covered = set().union(*(set(range(a, b)) for a, b in spans))
                self.assertEqual(covered, set(range(duration * 10)))
                self.assertTrue(all(0 < b - a <= 250 for a, b in spans))

    def test_empty_audio_and_invalid_rate_are_rejected(self):
        for frames, rate in [(0, 16000), (-1, 16000), (1, 0), (1, -1)]:
            with self.subTest(frames=frames, rate=rate):
                with self.assertRaises(ValueError):
                    list(analysis.windows(frames, rate))


class SignalTests(unittest.TestCase):
    def test_silence_has_json_safe_statistics(self):
        stats = analysis.signal_stats(np.zeros((160, 2), dtype=np.float32))
        self.assertEqual(stats["rms"], 0)
        self.assertIsNone(stats["rms_dbfs"])
        self.assertEqual(stats["peak"], 0)
        self.assertTrue(stats["all_zero"])
        json.dumps(stats, allow_nan=False)

    def test_full_scale_uses_both_polarities(self):
        stats = analysis.signal_stats(np.array([-1.0, 1.0]))
        self.assertEqual(stats["rms_dbfs"], 0)
        self.assertEqual(stats["full_scale_sample_fraction"], 1)
        self.assertFalse(stats["all_zero"])

    def test_nonfinite_or_empty_signal_is_rejected(self):
        for samples in [[], [float("nan")], [float("inf")], [-float("inf")]]:
            with self.subTest(samples=samples):
                with self.assertRaises(ValueError):
                    analysis.signal_stats(np.array(samples))

    def test_resampling_keeps_duration_and_mono_contract(self):
        rate = 44100
        t = np.arange(rate) / rate
        stereo = np.column_stack([0.2 * np.sin(2 * np.pi * 440 * t)] * 2)
        audio = analysis.model_audio(stereo, rate)
        self.assertEqual(len(audio), 16000)
        self.assertEqual(audio.ndim, 1)
        self.assertEqual(audio.dtype, np.float32)
        self.assertTrue(audio.flags.c_contiguous)
        self.assertGreater(analysis.signal_stats(audio)["rms"], 0.1)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        local = analysis.ROOT / "local"
        local.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="listener-tests-", dir=local)
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.model = FakeModel()
        versions = patch.object(analysis.importlib.metadata, "version", return_value="test")
        versions.start()
        self.addCleanup(versions.stop)

    def write_audio(self, samples, rate=16000, name="authored.wav"):
        path = self.work / name
        sf.write(path, samples, rate, subtype="FLOAT")
        return path

    def capture_fixture(self, observations, blocks, seconds=40, **changes):
        session = self.work / "capture"
        session.mkdir()
        capture = {
            "status": "complete", "stop_reason": "finish", "error_flags": [],
            "sample_rate": 16000, "observations": observations, "blocks": blocks,
            "channels": 1, "frames": 0 if seconds is None else seconds * 16000,
            "observation_errors": [], "device_intervals": [], "limitations": [],
        }
        capture.update(changes)
        analysis.write_json(session / "capture.json", capture)
        if seconds is not None:
            samples = np.repeat(np.arange(1, seconds + 1, dtype=np.float32) / 100, 16000)
            sf.write(session / "original.wav", samples, 16000, subtype="FLOAT")
        return session

    @staticmethod
    def mark(capture_time, media_time=None, **changes):
        result = {"source_id": "https://example.test/authored-audio", "duration_seconds": 100,
                  "media_time_seconds": capture_time if media_time is None else media_time,
                  "capture_monotonic_seconds": capture_time, "state": "playing",
                  "rate": 1, "ad": False, "seeking": False}
        result.update(changes)
        return result

    @staticmethod
    def audio_block(start, end, first=None):
        first = start * 16000 if first is None else first
        return {"start_frame": first, "end_frame": first + (end - start) * 16000,
                "start_monotonic_seconds": start, "end_monotonic_seconds": end,
                "timing_quality": "device_clock"}

    def test_passage_windows_count_union_not_overlap_and_preserve_original(self):
        rate = 16000
        samples = np.zeros((75 * rate, 2), dtype=np.float32)
        samples[40 * rate:41 * rate] = 0.25
        source = self.write_audio(samples)
        original = source.read_bytes()
        metadata = {"title": "BLIND_TEST_TITLE", "lyrics": "BLIND_TEST_LYRICS"}
        report = analysis.analyze_file(
            source, self.work / "passage", start=40, end=72,
            metadata=metadata, model=self.model,
        )
        bounds = [(clip["source_start_seconds"], clip["source_end_seconds"])
                  for clip in report["clips"]]
        self.assertEqual(bounds, [(40, 65), (60, 72)])
        self.assertEqual(sum(b - a for a, b in bounds), 37)
        self.assertEqual(report["analyzed_seconds"], 32)
        self.assertEqual(report["passage"]["frames"], 32 * rate)
        self.assertEqual(report["source"]["duration_seconds"], 75)
        self.assertEqual([len(audio) for audio in self.model.inputs], [25 * rate, 12 * rate])
        self.assertEqual(report["source"]["metadata"], metadata)
        self.assertNotIn(metadata["title"], report["model"]["prompt"])
        self.assertNotIn(metadata["lyrics"], report["model"]["prompt"])
        self.assertEqual(source.read_bytes(), original)
        self.assertTrue(report["source"]["unchanged"])
        self.assertEqual(report["source"]["channels"], 2)
        saved = json.loads((self.work / "passage/report.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "complete")

    def test_trailing_silence_and_offset_do_not_shorten_recording(self):
        samples = np.zeros((32000, 2), dtype=np.float32)
        samples[:1600] = 0.1
        source = self.write_audio(samples)
        report = analysis.analyze_file(source, self.work / "trailing", source_offset=40, model=self.model)
        self.assertEqual(report["analyzed_seconds"], 2)
        self.assertEqual(report["clips"][0]["source_start_seconds"], 40)
        self.assertEqual(report["clips"][0]["source_end_seconds"], 42)
        clip = sf.info(self.work / "trailing/clip-001.wav")
        self.assertEqual(clip.frames, 32000)
        self.assertEqual(clip.channels, 1)
        self.assertEqual(clip.samplerate, 16000)
        self.assertTrue(np.all(self.model.inputs[0][-16000:] == 0))

    def test_stereo_cancellation_is_reported_separately_from_source_energy(self):
        t = np.arange(16000) / 16000
        tone = 0.5 * np.sin(2 * np.pi * 440 * t)
        source = self.write_audio(np.column_stack([tone, -tone]))
        report = analysis.analyze_file(source, self.work / "antiphase", model=self.model)
        clip = report["clips"][0]
        self.assertFalse(clip["source_signal"]["all_zero"])
        self.assertGreater(clip["source_signal"]["rms"], 0.3)
        self.assertTrue(clip["analysis_signal"]["all_zero"])
        self.assertIsNone(clip["analysis_signal"]["rms_dbfs"])

    def test_invalid_passages_are_rejected_before_model_calls(self):
        source = self.write_audio(np.zeros(16000))
        cases = [
            {"start": -1}, {"start": float("nan")}, {"start": float("inf")},
            {"end": float("nan")}, {"end": float("inf")}, {"end": 2},
            {"start": 1}, {"start": 0.5, "end": 0.5}, {"end": 0},
            {"source_offset": -1}, {"source_offset": float("nan")},
        ]
        for index, offsets in enumerate(cases):
            with self.subTest(offsets=offsets):
                with self.assertRaises(ValueError):
                    analysis.analyze_file(source, self.work / f"bad-{index}", model=self.model, **offsets)
                self.assertFalse((self.work / f"bad-{index}").exists())
        self.assertEqual(self.model.inputs, [])

    def test_nonfinite_file_is_rejected_without_orphan_output(self):
        for index, value in enumerate([float("nan"), float("inf"), -float("inf")]):
            with self.subTest(value=value):
                samples = np.zeros(16000, dtype=np.float32)
                samples[100] = value
                source = self.write_audio(samples, name=f"invalid-{index}.wav")
                original_hash = analysis.sha256(source)
                output = self.work / f"invalid-result-{index}"
                with self.assertRaises(ValueError):
                    analysis.analyze_file(source, output, model=self.model)
                self.assertFalse(output.exists())
                self.assertEqual(analysis.sha256(source), original_hash)
        self.assertEqual(self.model.inputs, [])

    def test_output_must_stay_under_local_and_cannot_overwrite_existing_session(self):
        with self.assertRaises(ValueError):
            analysis.private_output(analysis.ROOT / "public-listener-test-output")
        with self.assertRaises(ValueError):
            analysis.private_output(analysis.ROOT / "local/../public-listener-test-output")
        with self.assertRaises(FileExistsError):
            analysis.private_output(self.work)

    def test_inference_failure_is_saved_without_completing_coverage(self):
        source = self.write_audio(np.zeros(16000))
        broken = Mock()
        broken.load_seconds = 0
        broken.describe.side_effect = RuntimeError("Synthetic model failure")
        with self.assertRaises(RuntimeError):
            analysis.analyze_file(source, self.work / "failed", model=broken)
        report = json.loads((self.work / "failed/report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["error_type"], "RuntimeError")
        self.assertNotIn("analyzed_seconds", report)
        self.assertEqual(report["clips"], [])

    def test_cli_failure_does_not_echo_private_diagnostics(self):
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["listen.py", "analyze", "--file", "test.wav"]), \
                patch.object(listen, "analyze_file", side_effect=ValueError("DO_NOT_ECHO_PRIVATE_DETAIL")), \
                contextlib.redirect_stdout(stdout):
            result = listen.main()
        self.assertEqual(result, 1)
        event = json.loads(stdout.getvalue())
        self.assertEqual(event["event"], "failed")
        self.assertNotIn("DO_NOT_ECHO_PRIVATE_DETAIL", stdout.getvalue())

    def test_session_excludes_intervals_neighboring_uncertain_playback(self):
        marks = [self.mark(0), self.mark(10), self.mark(20, state="paused"), self.mark(30), self.mark(40)]
        session = self.capture_fixture(marks, [self.audio_block(0, 40)])
        output = self.work / "session-analysis"
        report = analysis.analyze_session(session, output, model=self.model)
        self.assertEqual(report["analyzed_seconds"], 20)
        self.assertEqual([(clip["source_start_seconds"], clip["source_end_seconds"])
                          for clip in report["clips"]], [(0, 10), (30, 40)])
        self.assertEqual(len(report["rejected_intervals"]), 2)
        self.assertEqual(len(self.model.inputs), 2)
        self.assertAlmostEqual(float(self.model.inputs[0][0]), 0.01)
        self.assertAlmostEqual(float(self.model.inputs[1][0]), 0.31)
        self.assertFalse(report["whole_song_verified"])
        for clip in report["clips"]:
            self.assertTrue((output / clip["analysis_file"]).is_file())

    def test_session_packet_gap_is_excluded_without_compressing_media_time(self):
        marks = [self.mark(position, position + 40) for position in (0, 10, 20, 30)]
        blocks = [self.audio_block(0, 10), self.audio_block(20, 30, first=160000)]
        session = self.capture_fixture(marks, blocks, seconds=20, status="partial",
                                       error_flags=["missing_audio_packets"])
        report = analysis.analyze_session(session, self.work / "gapped-analysis", model=self.model)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["analyzed_seconds"], 20)
        self.assertEqual([(clip["source_start_seconds"], clip["source_end_seconds"])
                          for clip in report["clips"]], [(40, 50), (60, 70)])
        self.assertEqual(report["rejected_intervals"][0]["reason"], "missing_or_unreliable_audio")

    def test_session_without_audio_does_not_load_model_or_require_recording(self):
        session = self.capture_fixture([self.mark(0), self.mark(10)], [], seconds=None,
                                       status="partial", error_flags=["no_audio_packets"])
        with patch.object(analysis, "LocalAudioModel", side_effect=AssertionError("Unexpected model load")) as load:
            report = analysis.analyze_session(session, self.work / "no-audio-analysis")
        load.assert_not_called()
        self.assertEqual(report["status"], "no_verified_coverage")
        self.assertEqual(report["analyzed_seconds"], 0)
        self.assertEqual(report["clips"], [])

    def test_setup_failed_session_without_format_does_not_load_model(self):
        session = self.capture_fixture([], [], seconds=None, status="partial", stop_reason="setup_failed")
        path = session / "capture.json"
        capture = json.loads(path.read_text(encoding="utf-8"))
        del capture["sample_rate"]
        analysis.write_json(path, capture)
        with patch.object(analysis, "LocalAudioModel", side_effect=AssertionError("Unexpected model load")) as load:
            report = analysis.analyze_session(session, self.work / "setup-failed-analysis")
        load.assert_not_called()
        self.assertEqual(report["status"], "no_verified_coverage")
        self.assertEqual(report["capture_stop_reason"], "setup_failed")

    def test_clean_interval_from_partial_capture_retains_partial_status(self):
        session = self.capture_fixture([self.mark(0), self.mark(10)], [self.audio_block(0, 10)],
                                       seconds=10, status="partial", stop_reason="lease_expired")
        report = analysis.analyze_session(session, self.work / "partial-analysis", model=self.model)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["capture_status"], "partial")
        self.assertEqual(report["capture_stop_reason"], "lease_expired")
        self.assertEqual(report["analyzed_seconds"], 10)
        self.assertFalse(report["whole_song_verified"])

    def test_negative_offset_is_valid_when_source_interval_starts_at_zero(self):
        session = self.capture_fixture([self.mark(5, 0), self.mark(15, 10)], [self.audio_block(0, 20)], seconds=20)
        report = analysis.analyze_session(session, self.work / "offset-analysis", model=self.model)
        self.assertEqual(report["analyzed_seconds"], 10)
        self.assertEqual(report["clips"][0]["source_start_seconds"], 0)
        self.assertEqual(report["clips"][0]["source_end_seconds"], 10)

    def test_adjacent_session_intervals_have_no_duplicated_duration(self):
        session = self.capture_fixture([self.mark(position) for position in (0, 10, 20, 30)],
                                       [self.audio_block(0, 30)], seconds=30)
        report = analysis.analyze_session(session, self.work / "adjacent-analysis", model=self.model)
        self.assertEqual(report["analyzed_seconds"], 30)
        self.assertEqual(sum(len(samples) for samples in self.model.inputs), 30 * 16000)
        spans = [(clip["source_start_seconds"], clip["source_end_seconds"]) for clip in report["clips"]]
        self.assertEqual(spans, [(0, 10), (10, 20), (20, 30)])
        self.assertEqual(report["model_validation"]["status"], "failed_controls")

    def test_capture_format_mismatch_is_rejected_before_loading_model(self):
        session = self.capture_fixture([self.mark(0), self.mark(10)], [self.audio_block(0, 10)], seconds=10)
        path = session / "capture.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for field, wrong in [("frames", 160001), ("channels", 2), ("sample_rate", 8000)]:
            with self.subTest(field=field):
                capture = dict(original)
                capture[field] = wrong
                analysis.write_json(path, capture)
                output = self.work / f"mismatch-{field}"
                with patch.object(analysis, "LocalAudioModel", side_effect=AssertionError("Unexpected model load")) as load:
                    with self.assertRaises(ValueError):
                        analysis.analyze_session(session, output)
                load.assert_not_called()
                report = json.loads((output / "report.json").read_text(encoding="utf-8"))
                self.assertEqual(report["status"], "failed")
                self.assertEqual(report["analyzed_seconds"], 0)


class LocalModelContractTests(unittest.TestCase):
    def setUp(self):
        local = analysis.ROOT / "local"
        local.mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix="listener-model-test-", dir=local)
        self.addCleanup(temp.cleanup)
        self.model_dir = Path(temp.name)
        for name in ["config.json", "preprocessor_config.json", "tokenizer_config.json", "tokenizer.json"]:
            analysis.write_json(self.model_dir / name, {})
        analysis.write_json(self.model_dir / "model.safetensors.index.json", {
            "weight_map": {"fake_tensor": "model-00001.safetensors"},
        })
        (self.model_dir / "model-00001.safetensors").write_bytes(b"original test fixture")
        self.manifest = {
            "model_id": analysis.MODEL_ID, "revision": analysis.REVISION, "verified": True,
            "files": {path.name: analysis.sha256(path) for path in self.model_dir.iterdir()},
        }
        self.write_manifest()

    def write_manifest(self):
        analysis.write_json(self.model_dir / "model-manifest.json", self.manifest)

    def test_missing_required_configuration_tokenizer_or_shard_is_rejected(self):
        original_files = self.manifest["files"].copy()
        for name in ["config.json", "tokenizer.json", "model-00001.safetensors"]:
            with self.subTest(name=name):
                self.manifest["files"] = {key: value for key, value in original_files.items() if key != name}
                self.write_manifest()
                with self.assertRaises(ValueError):
                    analysis.verify_model(self.model_dir)

    def test_additional_unverified_loadable_file_is_rejected(self):
        analysis.write_json(self.model_dir / "generation_config.json", {})
        with self.assertRaises(ValueError):
            analysis.verify_model(self.model_dir)

    def test_changed_weight_bytes_are_rejected(self):
        (self.model_dir / "model-00001.safetensors").write_bytes(b"modified test fixture")
        with self.assertRaises(ValueError):
            analysis.verify_model(self.model_dir)

    def test_wrong_checkpoint_or_unverified_manifest_is_rejected(self):
        for key, bad_value in [("model_id", "test/other-model"), ("revision", "wrong-revision"), ("verified", False)]:
            with self.subTest(key=key):
                original = self.manifest[key]
                self.manifest[key] = bad_value
                self.write_manifest()
                with self.assertRaises(ValueError):
                    analysis.verify_model(self.model_dir)
                self.manifest[key] = original

    def test_manifest_cannot_reference_parent_directory(self):
        self.manifest["files"]["../outside.safetensors"] = "unused"
        self.write_manifest()
        with self.assertRaises(ValueError):
            analysis.verify_model(self.model_dir)

    def test_offline_model_and_processor_share_pin_and_audio_only_prompt(self):
        processor = Mock()
        processor.feature_extractor.sampling_rate = 16000
        features = Mock()

        class Inputs(dict):
            def to(self, device):
                self.device = device
                return self

        inputs = Inputs(input_ids=np.zeros((1, 3), dtype=int), input_features=features,
                        feature_attention_mask=np.ones((1, 10), dtype=int))
        # Match the installed Qwen2AudioProcessor's singular `audio` argument.
        def process(text, audio, sampling_rate, return_tensors, padding):
            return inputs
        processor.side_effect = process
        processor.apply_chat_template.return_value = "fixed audio prompt"
        processor.batch_decode.return_value = ["Synthetic model answer."]
        model = Mock()
        model.eval.return_value = model
        model.generate.return_value = np.zeros((1, 6), dtype=int)
        torch = SimpleNamespace(
            bfloat16=object(), inference_mode=contextlib.nullcontext,
            cuda=SimpleNamespace(
                is_available=lambda: True, is_bf16_supported=lambda: True,
                reset_peak_memory_stats=Mock(), synchronize=Mock(),
                max_memory_allocated=lambda: 100, max_memory_reserved=lambda: 200,
            ),
        )
        processor_loader = Mock(return_value=processor)
        model_loader = Mock(return_value=model)
        transformers = SimpleNamespace(
            AutoProcessor=SimpleNamespace(from_pretrained=processor_loader),
            Qwen2AudioForConditionalGeneration=SimpleNamespace(from_pretrained=model_loader),
        )
        with patch.dict(sys.modules, {"torch": torch, "transformers": transformers}), \
                patch.dict(analysis.os.environ):
            local_model = analysis.LocalAudioModel(self.model_dir)
            audio = np.zeros(16000, dtype=np.float32)
            answer = local_model.describe(audio)
            self.assertEqual(analysis.os.environ["HF_HUB_OFFLINE"], "1")
            self.assertEqual(analysis.os.environ["TRANSFORMERS_OFFLINE"], "1")

        for loader in [processor_loader, model_loader]:
            self.assertEqual(loader.call_args.kwargs["revision"], analysis.REVISION)
            self.assertTrue(loader.call_args.kwargs["local_files_only"])
            self.assertFalse(loader.call_args.kwargs["trust_remote_code"])
        self.assertIs(model_loader.call_args.kwargs["torch_dtype"], torch.bfloat16)
        self.assertEqual(model_loader.call_args.kwargs["attn_implementation"], "sdpa")
        self.assertTrue(model_loader.call_args.kwargs["use_safetensors"])
        content = processor.apply_chat_template.call_args.args[0][0]["content"]
        self.assertEqual(content, [{"type": "audio", "audio_url": "local-audio"},
                                  {"type": "text", "text": analysis.PROMPT}])
        self.assertIs(processor.call_args.kwargs["audio"][0], audio)
        self.assertEqual(processor.call_args.kwargs["sampling_rate"], 16000)
        self.assertEqual(inputs.device, "cuda")
        self.assertFalse(model.generate.call_args.kwargs["do_sample"])
        self.assertEqual(model.generate.call_args.kwargs["max_new_tokens"], 384)
        self.assertEqual(answer["generated_tokens"], 3)
        self.assertFalse(answer["hit_token_limit"])


if __name__ == "__main__":
    unittest.main()
