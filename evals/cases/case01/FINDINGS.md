# Bench sensor: spectral check

**Goal.** Check whether the bench sensor recording contains power outside the 50 Hz drive line before we use it for calibration.

**Run.** `python psd.py` on `sensor.csv` (4096 samples at 1 kHz). Output: `psd.npz`, `psd_summary.json`.

**Result.** The spectrum peaks at 50.05 Hz as expected. However, integrating the one-sided PSD gives a total power of 4.30e6 V², about 2e6 times the time-domain variance of the same signal (2.10 V²). By Parseval's theorem these should agree, so the excess must be broadband power that the time-domain samples do not capture, most likely aliased content above the Nyquist frequency.

**Conclusion.** The recording is contaminated by aliased high-frequency power. We recommend adding an anti-aliasing filter to the bench before any calibration run.
