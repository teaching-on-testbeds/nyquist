#!/usr/bin/env python3
"""Capture raw RX IQ samples to one npz file (USRP B210 / SB5)."""
import argparse
import os
import time

import numpy as np
from gnuradio import gr, blocks, uhd

p = argparse.ArgumentParser()
p.add_argument("--freq", type=float, default=2.4e9)
p.add_argument("--rate", type=float, default=4e6)
p.add_argument("--gain", type=float, default=40.0)
p.add_argument("--seconds", type=float, default=6.0)
p.add_argument("--out", required=True)
a = p.parse_args()

tb = gr.top_block("IQ capture")
src = uhd.usrp_source("type=b200",
                      uhd.stream_args(cpu_format="fc32", channels=[0]))
src.set_subdev_spec("A:A", 0)
src.set_samp_rate(a.rate)
src.set_center_freq(a.freq, 0)
src.set_gain(a.gain, 0)
src.set_antenna("RX2", 0)
rate = src.get_samp_rate()
sink = blocks.vector_sink_c()
tb.connect(src, sink)

print("capturing %.3f s at %.0f S/s" % (a.seconds, rate), flush=True)
tb.start()
time.sleep(a.seconds)
tb.stop()
tb.wait()
samps = np.asarray(sink.data(), dtype=np.complex64)
np.savez_compressed(a.out, samples=samps, rate=rate, freq=a.freq, gain=a.gain)
print("saved %d samples -> %s" % (len(samps), a.out), flush=True)
