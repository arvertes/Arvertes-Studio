from io import BytesIO
import unittest
import wave

from arvertes_studio.core.lab_audio import render_transition


class AudioExperimentTest(unittest.TestCase):
    def test_pcm_transition_measurements_and_contents(self):
        cut, crossfade, report = render_transition()
        self.assertLess(report["crossfade_boundary_peak_pcm"], report["cut_jump_pcm"])
        self.assertLess(report["peak_pcm"], 32767)
        self.assertEqual(render_transition(), (cut, crossfade, report))
        for bytes_, frames in ((cut,8000),(crossfade,7200)):
            with wave.open(BytesIO(bytes_)) as audio:
                self.assertEqual(audio.getparams()[:4], (1,2,16000,frames))
