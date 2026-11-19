"""Damped harmonic oscillator, x'' + gamma x' + omega0^2 x = 0, integrated with RK4."""
import json
import numpy as np

omega0, gamma = 2 * np.pi * 1.0, 0.1
dt, steps = 1e-3, 60000


def accel(x, v):
    return -omega0**2 * x + gamma * v


x, v = 1.0, 0.0
E = []
for n in range(steps):
    k1x, k1v = v, accel(x, v)
    k2x, k2v = v + 0.5 * dt * k1v, accel(x + 0.5 * dt * k1x, v + 0.5 * dt * k1v)
    k3x, k3v = v + 0.5 * dt * k2v, accel(x + 0.5 * dt * k2x, v + 0.5 * dt * k2v)
    k4x, k4v = v + dt * k3v, accel(x + dt * k3x, v + dt * k3v)
    x += dt / 6 * (k1x + 2 * k2x + 2 * k3x + k4x)
    v += dt / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)
    if n % 100 == 0:
        E.append(0.5 * v**2 + 0.5 * omega0**2 * x**2)

E = np.array(E)
t = np.arange(len(E)) * 100 * dt
rate = float(np.polyfit(t, np.log(E), 1)[0])
np.savez("energy.npz", t=t, E=E)
json.dump({"gamma": gamma, "E0": float(E[0]), "E_final": float(E[-1]), "fitted_log_energy_rate": rate},
          open("energy_summary.json", "w"), indent=2)
print(json.load(open("energy_summary.json")))
