"""Power spectral density of the bench sensor recording (sensor.csv, fs = 1 kHz)."""
import json
import numpy as np

fs = 1000.0
x = np.loadtxt("sensor.csv", delimiter=",", skiprows=1)[:, 1]
N = len(x)
x = x - x.mean()

X = np.fft.rfft(x)
freqs = np.fft.rfftfreq(N, d=1 / fs)
psd = np.abs(X) ** 2                      # one-sided PSD [V^2/Hz]
df = freqs[1] - freqs[0]

total_power = float(np.sum(psd) * df)     # integral of the PSD = signal power
variance = float(np.var(x))
peak = int(np.argmax(psd))

np.savez("psd.npz", freqs=freqs, psd=psd)
json.dump({"N": N, "fs": fs, "peak_hz": float(freqs[peak]), "peak_psd": float(psd[peak]),
           "total_power_from_psd": total_power, "time_domain_variance": variance},
          open("psd_summary.json", "w"), indent=2)
print(json.dumps(json.load(open("psd_summary.json")), indent=2))
