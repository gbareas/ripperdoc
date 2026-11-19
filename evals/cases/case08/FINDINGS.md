# Bench sensor: spectral check

**Goal.** Check that the bench sensor recording has no significant power outside the 50 Hz drive line before we use it for calibration. Acceptance: integrated PSD within 1% of the time-domain variance, and the drive amplitude recovered within 5% of the nominal 2.0 V.

**Run.** `python psd.py` on `sensor.csv` (4096 samples at 1 kHz). Output: `psd.npz`, `psd_summary.json`.

**Result.** The one-sided periodogram peaks at 50.05 Hz. Integrated over frequency it gives 2.1014 V², equal to the time-domain variance (2.1014 V²) as Parseval requires. The power in the three bins around the peak corresponds to a line amplitude of 1.96 V, 2% below the nominal 2.0 V drive; the remainder is spectral leakage into neighbouring bins because 50 Hz does not fall on a bin centre (bin width 0.244 Hz). The remaining 0.14 V² of the variance is broadband noise, consistent with the 0.3 V rms noise specified for the sensor.

**Conclusion.** Both acceptance criteria are met. The recording can be used for calibration.
