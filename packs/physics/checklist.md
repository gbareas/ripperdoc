# Physics checklist

For each item, the trace target is the line that implements the formula and the equation it should implement.

### physics.normalisation
**Normalisation of transforms and densities.** FFT and periodogram scaling (1/(fs·N), one-sided factor 2 except DC and Nyquist), window power correction, per-Hz vs per-bin, histogram density vs counts. Does the integrated quantity equal what it should (Parseval, total counts, unit area)?

### physics.units
**Units and dimensions.** Is every term in the same units? Are conversions (Hz/rad s⁻¹, nm/m, erg/J, natural units) applied once and in the right direction? Do constants carry the units the formula assumes?

### physics.jacobian
**Change of variables.** A density per unit frequency is not a density per unit wavelength, log-energy or solid angle without the Jacobian (e.g. B_ν vs B_λ, Wien's law in ν vs λ). Is the maximum, integral or comparison taken in the variable the claim is about?

### physics.signs-conventions
**Signs and conventions.** Sign of damping, driving, potential and coupling terms; Fourier sign and 2π convention; metric signature; phase conventions. A sign error often looks like a physical effect (instability, gain, attraction).

### physics.conservation
**Conservation and invariants.** Should energy, norm, probability, charge or momentum be conserved (or decay at a known rate)? Does the saved output do that? Is an apparent instability physical or numerical?

### physics.discretisation
**Discretisation and resolution.** Time step, grid spacing, integrator order, bin width, frequency resolution, aliasing and boundary conditions. Does the result survive halving the step or doubling the resolution? Is the effect smaller than one bin?

### physics.background
**Background and baseline subtraction.** Which array enters the integral or the fit: raw or background-subtracted, calibrated or uncalibrated? Is the background model fitted outside the signal region?

### physics.reference-formula
**The right formula.** Compare the implemented expression with the cited paper, the derivation in the write-up, or a textbook: factors of 2 and 2π, ħ and k_B, missing terms, approximations used outside their range of validity.
