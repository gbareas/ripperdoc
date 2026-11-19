#!/usr/bin/env bash
# Train the new augmentation pipeline with 5 seeds; baseline run from last month is in baseline.json.
for s in 0 1 2 3 4; do
  python train.py --augment mixup --seed "$s" --out "runs/mixup_s$s" | tee -a train_log.txt
done
