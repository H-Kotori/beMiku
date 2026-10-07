"""Behavioral checks for the exported comparison, independent of its renderer."""

from array import array
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave

import mido

import build


OUTPUTS = {"A.mid", "B.mid", "A.wav", "B.wav", "manifest.json"}
PPQN = 480
RATE = 44100


def absolute_events(midi):
    events, spans = [], []
    for track_number, track in enumerate(midi.tracks):
        tick = 0
        for message in track:
            tick += message.time
            events.append((track_number, tick, message.copy(time=0)))
        spans.append(tick)
    return events, spans


def is_note_off(message):
    return message.type == "note_off" or (
        message.type == "note_on" and message.velocity == 0
    )


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.first = Path(temporary.name) / "first"
        cls.second = Path(temporary.name) / "second"
        cls.first.mkdir()
        cls.second.mkdir()
        build.build(cls.first)
        # A fresh CLI process also checks that the working directory is irrelevant.
        subprocess.run(
            [sys.executable, str(Path(__file__).with_name("build.py").resolve()),
             "--output-dir", str(cls.second)],
            cwd=temporary.name, check=True, capture_output=True, text=True,
            timeout=120,
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

    def test_midi_protocol_and_single_note_off_difference(self):
        unchanged = []
        for version, end_beat in (("A", 15.5), ("B", 14)):
            with self.subTest(version=version):
                midi = mido.MidiFile(self.first / f"{version}.mid")
                self.assertEqual(midi.type, 1)
                self.assertEqual(midi.ticks_per_beat, PPQN)
                self.assertAlmostEqual(midi.length, 20.0, places=9)
                events, spans = absolute_events(midi)
                self.assertEqual(max(spans), 32 * PPQN)
                self.assertTrue(all(0 <= tick <= 32 * PPQN for _, tick, _ in events))
                self.assertEqual(
                    [(tick, msg.tempo) for _, tick, msg in events
                     if msg.type == "set_tempo"], [(0, 625000)],
                )
                self.assertEqual(
                    [(tick, msg.numerator, msg.denominator) for _, tick, msg in events
                     if msg.type == "time_signature"], [(0, 4, 4)],
                )

                active, intervals = {}, []
                for _, tick, message in sorted(events, key=lambda event: event[1]):
                    if message.type not in ("note_on", "note_off"):
                        continue
                    key = (message.channel, message.note)
                    self.assertIn(message.channel, (0, 1))
                    if is_note_off(message):
                        self.assertIn(key, active, "Note-off without a live note")
                        start = active.pop(key)
                        self.assertLess(start, tick)
                        intervals.append((*key, start, tick))
                    else:
                        self.assertNotIn(key, active, "Overlapping attacks of one pitch")
                        if message.channel == 0:
                            self.assertFalse(
                                any(channel == 0 for channel, _ in active),
                                "Lead is not monophonic",
                            )
                        active[key] = tick
                self.assertFalse(active, "Stuck notes at the end of the MIDI")
                self.assertEqual({channel for channel, _, _, _ in intervals}, {0, 1})
                self.assertEqual(
                    [event for event in intervals if event[0] == 0 and event[2] == 13 * PPQN],
                    [(0, 74, 13 * PPQN, int(end_beat * PPQN))],
                )
                self.assertEqual(
                    min(start for channel, _, start, _ in intervals
                        if channel == 0 and start > 13 * PPQN), 16 * PPQN,
                )
                self.assertTrue(any(
                    channel == 1 and start <= 15.75 * PPQN < end
                    for channel, _, start, end in intervals
                ), "No backing note continues through the shared lead gap")

                target_off = [event for event in events if (
                    is_note_off(event[2]) and event[2].channel == 0
                    and event[2].note == 74 and event[1] == end_beat * PPQN
                )]
                self.assertEqual(len(target_off), 1)
                unchanged.append([event for event in events if event != target_off[0]])
        self.assertEqual(unchanged[0], unchanged[1], "An additional MIDI event differs")

    def test_pcm_format_difference_window_and_continuing_backing(self):
        audio = []
        for version in ("A", "B"):
            with self.subTest(version=version):
                with wave.open(str(self.first / f"{version}.wav"), "rb") as wav:
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
                self.assertGreater(min(samples), -32768, "Negative full-scale clipping")
                self.assertLess(max(samples), 32767, "Positive full-scale clipping")
                # Both lead releases have finished here; backing must remain audible.
                self.assertTrue(any(samples[int(9.8 * RATE):int(9.95 * RATE)]))
                audio.append(pcm)

        # Permit one sample of boundary rounding, not differences elsewhere.
        before = math.floor(8.75 * RATE) - 1
        after = math.ceil(9.7675 * RATE) + 1
        self.assertEqual(audio[0][:before * 2], audio[1][:before * 2])
        self.assertEqual(audio[0][after * 2:], audio[1][after * 2:])
        self.assertNotEqual(audio[0][before * 2:after * 2], audio[1][before * 2:after * 2])


if __name__ == "__main__":
    unittest.main()
