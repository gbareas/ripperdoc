"""Power spectral density of the bench sensor recording (sensor.csv, fs = 1 kHz)."""
import json
import numpy as np

fs = 1000.0
x = np.loadtxt("sensor.csv", delimiter=",", skiprows=1)[:, 1]
N = len(x)
x = x - x.mean()

X = np.fft.rfft(x)
freqs = np.fft.rfftfreq(N, d=1 / fs)
psd = np.abs(X) ** 2 / (fs * N)           # periodogram [V^2/Hz]
psd[1:-1] *= 2                            # one-sided: fold negative frequencies (not DC, not Nyquist; N even)
df = freqs[1] - freqs[0]

total_power = float(np.sum(psd) * df)     # Parseval: should equal the variance
variance = float(np.var(x))
peak = int(np.argmax(psd))
# amplitude of the line from the power in the peak bin and its two neighbours
line_power = float(np.sum(psd[peak - 1:peak + 2]) * df)
amplitude = float(np.sqrt(2 * line_power))

np.savez("psd.npz", freqs=freqs, psd=psd)
json.dump({"N": N, "fs": fs, "peak_hz": float(freqs[peak]), "total_power_from_psd": total_power,
           "time_domain_variance": variance, "line_amplitude_v": amplitude},
          open("psd_summary.json", "w"), indent=2)
print(json.dumps(json.load(open("psd_summary.json")), indent=2))
