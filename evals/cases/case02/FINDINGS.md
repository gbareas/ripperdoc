# Source model: spectral peak

**Goal.** Validate the blackbody source model used in the detector simulation (T = 5800 K) against Wien's displacement law before we fit real data with it.

**Run.** `python spectrum.py`. Output: `spectrum.npz` (radiance vs wavelength), `peak.json`.

**Result.** The modelled spectrum, plotted against wavelength, peaks at 879 nm. Wien's law predicts 500 nm for 5800 K, so the model peak is shifted red by a factor of 1.76. The shift is stable when the frequency grid is refined (tested 20k to 200k points), so it is not a sampling artefact.

**Conclusion.** The source model does not reproduce Wien's law. Our working hypothesis is that the emissivity of the source is strongly wavelength dependent, which shifts the peak to the near infrared. We will add a wavelength-dependent emissivity term to the model and refit.
