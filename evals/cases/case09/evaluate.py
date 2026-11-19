"""Evaluate the retrained classifier and the production baseline on the frozen test split, 5 seeds.
Writes results.csv (one row per seed). Predictions come from predictions/<seed>.npz, produced by train.py."""
import csv
import numpy as np

rows = []
for seed in range(5):
    p = np.load(f"predictions/{seed}.npz")
    rows.append((seed, float(np.mean(p["model"] == p["y"])), float(np.mean(p["baseline"] == p["y"]))))
with open("results.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["seed", "model_acc", "baseline_acc"])
    w.writerows(rows)
