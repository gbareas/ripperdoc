# Retrained classifier vs production baseline

**Goal.** Decide whether the retrained classifier replaces the production baseline. Acceptance (agreed before the run): mean test accuracy over 5 seeds at least 3 points above the baseline, and better than the baseline on every seed.

**Run.** Training happened in the training repository; its saved test-set predictions are in `predictions/<seed>.npz`. `python evaluate.py` scores them on the frozen test split (1000 examples), seeds 0 to 4. Per-seed results in `results.csv`.

**Result.** Mean test accuracy is 0.845 ± 0.005 (std over seeds) for the retrained classifier and 0.801 ± 0.003 for the baseline. The paired difference is +4.5 ± 0.8 points and is positive on all 5 seeds (smallest: +3.4 points, seed 2).

**Conclusion.** Both acceptance criteria are met. We propose replacing the production model. The gain is measured on one frozen test split; we have not tested it under distribution shift.
