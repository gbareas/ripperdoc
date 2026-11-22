# Machine learning checklist

Training runs are expensive: never rerun one without the caller's permission. Trace the config, the logs and the saved predictions instead.

### ml.split-leakage
**Leakage across the split.** Is any fitted step (feature selection, scaling, imputation, PCA, tokenizer, threshold, hyperparameter search) fitted on data that includes the test set? Are there duplicates or near-duplicates across splits, or the same subject/patient/source on both sides?

### ml.test-reuse
**Test set used for decisions.** Was the test set used for model selection, early stopping, threshold tuning or repeated comparisons? Then it is a validation set and the reported number is optimistic.

### ml.seed-selection
**Selected runs.** Is the reported number the best of several seeds or configs, compared against a single baseline run? Report the mean and spread over all runs, for both.

### ml.baseline-parity
**Baseline parity.** Same data, preprocessing, compute budget, tuning effort and seeds for the baseline as for the new model? Is the baseline what the write-up says it is (a fixed deployed model scores the same on every seed; one retrained per seed does not)?

### ml.metric-definition
**Metric as claimed.** Is the metric computed as the write-up defines it (macro vs micro, threshold, positive class, top-k, per-example vs per-batch average) and on the split it names? Does the number in the write-up match the one computed from saved predictions?

### ml.variance
**Variance and pairing.** Enough seeds? Is the gain larger than the seed-to-seed spread? Are comparisons paired per seed when the setup allows it?

### ml.data-provenance
**Data provenance.** Label quality, class balance, how the test set was built, and whether a claim of generalisation goes beyond the distribution that was tested.
