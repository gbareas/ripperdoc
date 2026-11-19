# Suspension model: stability at low damping

**Goal.** Determine whether the suspension model, x'' + γx' + ω0²x = 0 with ω0 = 2π rad/s, is stable at the planned damping γ = 0.1 s⁻¹.

**Run.** `python oscillator.py` (RK4, dt = 1 ms, 60 s). Output: `energy.npz`, `energy_summary.json`.

**Result.** The mechanical energy grows from 19.7 J to 7945 J over 60 s. A fit of log E against time gives a growth rate of +0.100 s⁻¹, equal to γ. Halving dt changes the rate by less than 1e-4, so this is not an integrator artefact.

**Conclusion.** The suspension is dynamically unstable at γ = 0.1 s⁻¹: energy grows at a rate set by the damping coefficient, which points to a negative-damping (self-excitation) mechanism in the model. We recommend not building the γ = 0.1 configuration and investigating the self-excitation term.
