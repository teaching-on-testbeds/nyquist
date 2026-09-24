#!/usr/bin/env python3
"""Final lab1 bandwidth analysis: PSD overlay + 3 waterfalls + metrics."""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "/tmp/opencode"
FFT = 2048
HOP = FFT // 2
DF = 1e4 / 64 / 1e3  # placeholder
CARRIERS = 52
DS = 1e6 / 64  # 15.625 kHz
MODS = ["bpsk", "qpsk", "16qam"]
CMAP = plt.get_cmap("viridis")


def psd(samps, rate):
    win = np.hanning(FFT)
    nseg = (len(samps) - FFT) // HOP + 1
    idx = np.arange(FFT)[None, :] + HOP * np.arange(nseg)[:, None]
    x = np.take(samps, idx) * win
    X = np.fft.fftshift(np.fft.fft(x, axis=1), axes=1)
    p = np.mean(np.abs(X) ** 2, axis=0) / (np.sum(win ** 2) * rate)
    freqs = (np.arange(FFT) - FFT // 2) * rate / FFT
    return freqs, 10 * np.log10(p + 1e-30)


def percentile_bw(freqs, db, pct=0.99):
    lin = 10 ** (db / 10)
    tot = np.trapz(lin, freqs)
    cdf = np.cumsum(lin) * (freqs[1] - freqs[0])
    lo = freqs[np.searchsorted(cdf, (1 - pct) / 2 * tot)]
    hi = freqs[np.searchsorted(cdf, (1 + pct) / 2 * tot)]
    return hi - lo, lo, hi


def down_bw(freqs, db, rel=20):
    mx = float(np.max(db))
    on = np.where(db >= mx - rel)[0]
    return freqs[on[-1]] - freqs[on[0]], freqs[on[0]], freqs[on[-1]]


fig = plt.figure(figsize=(14, 9), dpi=150)
gs = fig.add_gridspec(4, 2, height_ratios=[1.5, 1, 1, 1], hspace=0.55, wspace=0.25)
axp = fig.add_subplot(gs[0, :])
axw = {m: fig.add_subplot(gs[i + 1, j]) for i, m in enumerate(MODS) for j in range(2)}
# simpler: one waterfall per row
fig.clf()
fig, axes = plt.subplots(4, 1, figsize=(12, 11), dpi=150,
                         gridspec_kw={"height_ratios": [1.4, 1, 1, 1], "hspace": 0.65})

noise = np.load(os.path.join(OUT, "iq-noise.npz"))
nrate = float(noise["rate"])
nf, nd = psd(noise["samples"], nrate)
floor = float(np.median(nd))

axpsd = axes[0]
axpsd.plot(nf / 1e6, nd, "k", lw=0.9, alpha=0.6, label="noise floor (TX off)")
print("%-8s %10s %12s %12s %12s %10s" % ("mod", "pk(dB)", "bw99(kHz)", "bw-20(kHz)", "f99_lo(MHz)", "f99_hi(MHz)"))
for m, colr in zip(MODS, ("C0", "C1", "C2")):
    d = np.load(os.path.join(OUT, "iq-%s.npz" % m))
    rate = float(d["rate"])
    freqs, db = psd(d["samples"], rate)
    b99, lo, hi = percentile_bw(freqs, db)
    b20, l20, h20 = down_bw(freqs, db)
    print("%-8s %10.1f %12.1f %12.1f %12.3f %10.3f" % (m, float(np.max(db)), b99 / 1e3, b20 / 1e3, lo / 1e6, hi / 1e6))
    axpsd.plot(freqs / 1e6, db, lw=1.5, color=colr, label="%s" % m.upper())
    for aa, mm, xx in ((axes[1 + MODS.index(m)], m, x) for x in [0]):
        pass

axpsd.axvline(-CARRIERS / 2 * DS / 1e3, color="gray", ls="--", lw=0.8)
axpsd.axvline(CARRIERS / 2 * DS / 1e3, color="gray", ls="--", lw=0.8)
axpsd.text(-0.42, floor + 20, "expected grid edges\n+/- %.3f MHz" % (CARRIERS / 2 * DS / 1e3),
           fontsize=8, color="gray")
axpsd.set_xlim(-0.55, 0.55)
axpsd.set_ylim(floor - 12, None)
axpsd.set_xlabel("Frequency offset from 2.4 GHz (MHz)")
axpsd.set_ylabel("Power (dB)")
axpsd.set_title("Received PSD: occupied bandwidth identical for BPSK, QPSK, 16-QAM")
axpsd.legend(fontsize=9)
axpsd.grid(alpha=0.3)

for i, m in enumerate(MODS):
    d = np.load(os.path.join(OUT, "iq-%s.npz" % m))
    rate = float(d["rate"])
    x = d["samples"]
    fft = 256
    win = np.hanning(fft)
    hop = fft // 2
    nseg = (len(x) - fft) // hop + 1
    idx = np.arange(fft)[None, :] + hop * np.arange(nseg)[:, None]
    X = np.fft.fftshift(np.fft.fft(np.take(x, idx) * win, axis=1), axes=1)
    dbm = 10 * np.log10(np.abs(X) ** 2 + 1e-30)
    freqs = (np.arange(fft) - fft // 2) * rate / fft
    sel = np.abs(freqs) <= 0.55e6
    mat = dbm[:, sel].T
    axw = axes[i + 1]
    im = axw.imshow(mat, aspect="auto", origin="lower", cmap="viridis",
                    extent=[freqs[sel][0] / 1e6, freqs[sel][-1] / 1e6, 0, nseg * hop / rate],
                    vmin=np.percentile(mat, 5), vmax=np.percentile(mat, 99.9))
    axw.axvline(-CARRIERS / 2 * DS / 1e3, color="w", ls="--", lw=0.8)
    axw.axvline(CARRIERS / 2 * DS / 1e3, color="w", ls="--", lw=0.8)
    axw.set_title("Waterfall: %s (%.0f kS/s, TX gain 89 dB)" % (m.upper(), rate / 1e3), fontsize=10)
    axw.set_xlabel("Frequency offset (MHz)", fontsize=8)
    axw.set_ylabel("Time (s)", fontsize=8)
    axw.tick_params(labelsize=8)
    fig.colorbar(im, ax=axw, label="dB", fraction=0.046, pad=0.02)

fig.savefig(os.path.join(OUT, "bandwidth-vs-modulation.png"), bbox_inches="tight")
print("\nSaved:", os.path.join(OUT, "bandwidth-vs-modulation.png"))
