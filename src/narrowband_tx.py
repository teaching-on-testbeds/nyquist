#!/usr/bin/env python3
"""
Lab: Nyquist formula - narrowband PSK/QAM transmitter for SB5.

Modern port of GNU Radio's benchmark_tx.py to the UHD 4.x / GR 3.10 API used
on the SB5 lab image. Transmits random PSK/QAM data with RRC pulse shaping.

Example (original nyquist CLI):
  time python3 narrowband_tx.py -f 2400e6 -r 0.5e6 -M 5 -p 2 --excess-bw=0.05
"""
import argparse
import sys
import time

import numpy as np
from gnuradio import blocks, digital, gr, uhd

MODS = {2: "bpsk", 4: "qpsk", 8: "8psk", 16: "16qam"}  # 16-PSK absent in GR 3.10; 16-QAM used


def get_constellation(mod):
    if mod == "bpsk":
        c = digital.constellation_bpsk()
    elif mod == "qpsk":
        c = digital.constellation_qpsk()
    elif mod == "8psk":
        c = digital.constellation_8psk()
    elif mod == "16qam":
        c = digital.constellation_16qam()
    elif mod == "64qam":
        c = digital.constellation_64qam()
    else:
        sys.exit("unsupported modulation: " + mod)
    c.normalize(digital.constellation.POWER_NORMALIZATION)
    return c


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-f", "--freq", type=float, required=True, help="center frequency (Hz)")
    p.add_argument("-r", "--rate", "--bitrate", dest="rate", type=float, default=0.5e6,
                   help="bit rate (bits/s)")
    p.add_argument("-M", "--megabytes", type=float, default=0.0,
                   help="total data to transmit, in megabytes (0 = run continuously)")
    p.add_argument("-p", "--constellation-points", type=int, default=2,
                   choices=[2, 4, 8, 16],
                   help="number of constellation points (signal levels), power of 2")
    p.add_argument("--mod", default=None,
                   choices=["bpsk", "qpsk", "8psk", "16qam", "64qam"],
                   help="explicit modulation (overrides -p)")
    p.add_argument("--excess-bw", type=float, default=0.05, help="RRC excess bandwidth")
    p.add_argument("--sps", "-S", type=int, default=4, help="samples per symbol")
    p.add_argument("--tx-gain", type=float, default=89.0, help="TX gain (dB)")
    p.add_argument("--tx-amplitude", "--amp", type=float, default=0.2, help="TX amplitude")
    p.add_argument("--antenna", "-A", default="TX/RX")
    p.add_argument("--subdev", default="A:A", help="subdevice spec (A:A for B200/B210, A:0 for N2xx)")
    p.add_argument("--args", "-a", default="type=b200", help="UHD device args (e.g. addr=192.168.10.2 for N210)")
    p.add_argument("--seconds", type=float, default=0, help="stop after this many s (0 = never)")
    a = p.parse_args()

    if a.mod:
        mod = a.mod
    else:
        mod = MODS.get(a.constellation_points, None)

    tb = gr.top_block("Nyquist narrowband TX")
    const = get_constellation(mod)
    bps = const.bits_per_symbol()
    sym_rate = a.rate / bps
    sps = max(a.sps, 2)
    samp_rate = sym_rate * sps

    if a.megabytes > 0:
        n_bytes = int(a.megabytes * 1e6)
        data = np.random.RandomState(42).randint(0, 256, n_bytes).tolist()
        repeat = False
    else:
        n_bytes = max(int(sym_rate * 4), 1)
        data = np.random.RandomState(42).randint(0, 256, n_bytes).tolist()
        repeat = True

    src = blocks.vector_source_b(data, repeat)
    modb = digital.generic_mod(
        constellation=const, differential=False, samples_per_symbol=sps,
        pre_diff_code=True, excess_bw=a.excess_bw, verbose=False, log=False)
    amp = blocks.multiply_const_cc(a.tx_amplitude)
    usrp = uhd.usrp_sink(a.args, uhd.stream_args(cpu_format="fc32", channels=[0]))
    usrp.set_subdev_spec(a.subdev, 0)
    usrp.set_samp_rate(samp_rate)
    usrp.set_center_freq(a.freq, 0)
    usrp.set_gain(a.tx_gain, 0)
    usrp.set_antenna(a.antenna, 0)
    rate = usrp.get_samp_rate()

    tb.connect(src, modb, amp, usrp)
    print("TX %s at %.3f Mbps  sym_rate=%.0f  sample_rate=%.0f  sps=%d  excess_bw=%.2f"
          % (mod.upper(), a.rate / 1e6, sym_rate, rate, int(rate / sym_rate), a.excess_bw),
          flush=True)

    if a.megabytes > 0:
        t0 = time.time()
        tb.run()
        elapsed = time.time() - t0
        tb.stop()
        tb.wait()
        print("transmitted %.1f MB (%d bits) in %.2f s" % (a.megabytes, n_bytes * 8, elapsed),
              flush=True)
    else:
        if a.seconds > 0:
            tb.start()
            time.sleep(a.seconds)
            tb.stop()
            tb.wait()
            print("sent %d bits in %.0f s" % (int(sym_rate * a.seconds * bps), a.seconds),
                  flush=True)
        else:
            try:
                tb.run()
            except KeyboardInterrupt:
                tb.stop()
                tb.wait()


if __name__ == "__main__":
    main()
