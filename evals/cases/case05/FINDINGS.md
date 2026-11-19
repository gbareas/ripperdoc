# Mixup augmentation

**Goal.** Test whether mixup augmentation improves test accuracy over the current pipeline (no augmentation).

**Run.** `run_all.sh` (mixup, 5 seeds, 40 epochs each); log in `train_log.txt`. Baseline from last month's run in `baseline.json`.

**Result.** With mixup the model reaches 0.881 test accuracy (run `mixup_s3`), against 0.781 for the baseline: +10 points.

**Conclusion.** Mixup gives a large improvement and should become the default augmentation. A figure for the paper (Fig. 4) shows the `mixup_s3` learning curve against the baseline.
