"""Fontes PCM sintéticas para comparação de transições em bancada."""
from array import array
from io import BytesIO
from math import sin, tau
import sys
import wave

RATE = 16000
FRAMES = 4000
OVERLAP = 800


def _osc(frequency, phase):
    return [round(4200*sin(tau*frequency*i/RATE+phase) +
                  950*sin(tau*frequency*1.7*i/RATE+phase)) for i in range(FRAMES)]


def _wav(samples):
    pcm = array("h", samples)
    if sys.byteorder != "little":
        pcm.byteswap()
    stream = BytesIO()
    with wave.open(stream, "wb") as output:
        output.setparams((1,2,RATE,0,"NONE","not compressed"))
        output.writeframes(pcm.tobytes())
    return stream.getvalue()


def render_transition():
    a, b = _osc(83,.8), _osc(137,-1.4)
    abrupt = a + b
    overlap = [round(x*(1-i/(OVERLAP-1)) + y*i/(OVERLAP-1))
               for i,(x,y) in enumerate(zip(a[-OVERLAP:],b[:OVERLAP]))]
    blended = a[:-OVERLAP] + overlap + b[OVERLAP:]
    report = {"sample_rate": RATE, "channels": 1, "overlap_frames": OVERLAP,
              "cut_jump_pcm": abs(b[0]-a[-1]),
              "crossfade_boundary_peak_pcm": max(abs(blended[i]-blended[i-1])
                  for i in (FRAMES-OVERLAP,FRAMES)),
              "peak_pcm":max(map(abs,blended)), "frames":len(blended),
              "review":"listening_and_spatial_integration_pending"}
    return _wav(abrupt), _wav(blended), report
