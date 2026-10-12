"""Compare the separate vowel-join export with a freshly built original A."""

from array import array
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

import mido

import build as original
import build_kyo_join
from test_build import PPQN, RATE, absolute_events, is_note_off


OUTPUTS = {"kyo-join-A.mid", "kyo-join-A.wav", "manifest.json"}


class KyoJoinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        cls.baseline = cls.root / "baseline"
        cls.first = cls.root / "first"
        cls.second = cls.root / "second"
        original.build(cls.baseline)
        build_kyo_join.build(cls.first)
        subprocess.run(
            [sys.executable, str(Path(__file__).with_name("build_kyo_join.py").resolve()),
             "--output-dir", str(cls.second)],
            cwd=cls.root, check=True, capture_output=True, text=True, timeout=120,
        )

    def test_complete_repeat_build_is_byte_identical(self):
        for directory in (self.first, self.second):
            self.assertEqual({path.name for path in directory.iterdir()}, OUTPUTS)
        for name in sorted(OUTPUTS):
            with self.subTest(file=name):
                self.assertEqual(
                    (self.first / name).read_bytes(),
                    (self.second / name).read_bytes(),
                )

    def test_only_target_note_off_changes_and_join_has_no_midi_gap(self):
        unchanged = []
        candidate_events = None
        for path, end_beat in (
            (self.baseline / "A.mid", 8.75),
            (self.first / "kyo-join-A.mid", 9),
        ):
            with self.subTest(file=path.name):
                midi = mido.MidiFile(path)
                self.assertEqual(midi.type, 1)
                self.assertEqual(midi.ticks_per_beat, PPQN)
                self.assertAlmostEqual(midi.length, 20.0, places=9)
                events, spans = absolute_events(midi)
                self.assertTrue(spans)
                self.assertTrue(all(span == 32 * PPQN for span in spans))
                self.assertEqual(
                    [(tick, msg.tempo) for _, tick, msg in events
                     if msg.type == "set_tempo"], [(0, 625000)],
                )
                self.assertEqual(
                    [(tick, msg.numerator, msg.denominator) for _, tick, msg in events
                     if msg.type == "time_signature"], [(0, 4, 4)],
                )
                target_off = [event for event in events if (
                    is_note_off(event[2]) and event[2].channel == 0
                    and event[2].note == 72 and event[1] == end_beat * PPQN
                )]
                self.assertEqual(len(target_off), 1)
                unchanged.append([event for event in events if event != target_off[0]])
                candidate_events = events
        self.assertEqual(unchanged[0], unchanged[1], "An additional MIDI event differs")

        # Check actual event order at the join, not merely equal end/start numbers.
        active = None
        intervals = []
        for _, tick, message in sorted(candidate_events, key=lambda event: event[1]):
            if message.type not in ("note_on", "note_off") or message.channel != 0:
                continue
            if is_note_off(message):
                self.assertIsNotNone(active, "Lead note-off without an active note")
                self.assertEqual(message.note, active[0])
                self.assertLess(active[1], tick)
                intervals.append((*active, tick))
                active = None
            else:
                self.assertIsNone(active, "Overlapping lead notes")
                active = (message.note, tick)
        self.assertIsNone(active, "Stuck lead note")
        self.assertEqual(
            [note for note in intervals if 8 * PPQN <= note[1] <= 9 * PPQN],
            [(72, 8 * PPQN, 9 * PPQN), (74, 9 * PPQN, int(9.5 * PPQN))],
        )
        self.assertIn((74, 13 * PPQN, int(15.5 * PPQN)), intervals,
                      "The candidate must preserve A's later line-two release")

    def test_pcm_differs_only_around_the_changed_release(self):
        audio = []
        for path in (self.baseline / "A.wav", self.first / "kyo-join-A.wav"):
            with self.subTest(file=path.name):
                with wave.open(str(path), "rb") as wav:
                    self.assertEqual(wav.getnchannels(), 1)
                    self.assertEqual(wav.getsampwidth(), 2)
                    self.assertEqual(wav.getframerate(), RATE)
                    self.assertEqual(wav.getnframes(), 882000)
                    self.assertEqual(wav.getcomptype(), "NONE")
                    pcm = wav.readframes(wav.getnframes())
                self.assertEqual(len(pcm), 882000 * 2)
                samples = array("h", pcm)
                if sys.byteorder != "little":
                    samples.byteswap()
                self.assertGreater(min(samples), -32768)
                self.assertLess(max(samples), 32767)
                audio.append(pcm)
        # Old note-off is 8.75 * 0.625 s; new release ends at 9 * 0.625 + 0.08 s.
        # Allow one sample of rounding at each boundary, but no other changes.
        before = math.floor(5.46875 * RATE) - 1
        after = math.ceil(5.705 * RATE) + 1
        self.assertEqual(audio[0][:before * 2], audio[1][:before * 2])
        self.assertEqual(audio[0][after * 2:], audio[1][after * 2:])
        self.assertNotEqual(audio[0][before * 2:after * 2], audio[1][before * 2:after * 2])

    def test_original_generated_directory_is_rejected_without_writes(self):
        # Exercise the real path guard against a disposable stand-in, never the repo.
        sandbox = self.root / "guard"
        protected = sandbox / "generated"
        protected.mkdir(parents=True)
        for name in ("score.json", "build.py"):
            (sandbox / name).write_bytes((original.ROOT / name).read_bytes())
        sentinel = b"Original A/B manifest must survive unchanged."
        (protected / "manifest.json").write_bytes(sentinel)
        with patch.object(build_kyo_join, "ROOT", sandbox):
            with self.assertRaises(ValueError):
                build_kyo_join.build(protected)
        self.assertEqual({path.name for path in protected.iterdir()}, {"manifest.json"})
        self.assertEqual((protected / "manifest.json").read_bytes(), sentinel)


if __name__ == "__main__":
    unittest.main()
