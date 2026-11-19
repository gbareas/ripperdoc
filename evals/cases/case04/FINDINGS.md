# Retrained classifier vs production baseline

**Goal.** Decide whether the retrained classifier replaces the production baseline. Acceptance (agreed before the run): mean test accuracy over 5 seeds at least 5 points above the baseline.

**Run.** Training happened in the training repository; its saved test-set predictions are in `predictions/<seed>.npz`. `python evaluate.py` scores them on the frozen test split (1000 examples), seeds 0 to 4. Per-seed results in `results.csv`.

**Result.** The retrained classifier reaches 0.86 mean test accuracy against 0.79 for the baseline, a gain of 7 points, with a spread across seeds below 0.01.

**Conclusion.** The acceptance criterion is met. We propose replacing the production model.
