# Spectral classifier: final test accuracy

**Goal.** Report the final test performance of the spectral-classification CNN (6 classes). Acceptance (fixed in the project plan): test accuracy ≥ 0.90 on the held-out test split, with balanced accuracy within 1 point of plain accuracy (no class carried by the others).

**Run.** `python train.py` (200 epochs, seed 0, about 10 h on one A100; log in `training_log.csv`), then `python eval.py` on checkpoint `epoch199`. `eval.py` saves per-example predictions (`test_predictions.npz`) and `metrics.json`. `model.py` and `data.py` live in the shared spectra package and are not copied here.

**Result.** Test accuracy 0.912 and balanced accuracy 0.912 on 3000 held-out spectra. Validation accuracy plateaus at about 0.92 from epoch ~120 onwards; validation loss flattens at the same point without rising, so the final checkpoint is not overfitted relative to the plateau.

**Conclusion.** Both acceptance criteria are met. The classifier is ready for the data-release pipeline.
