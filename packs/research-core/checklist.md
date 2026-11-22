# Research core checklist

Experiment design items. Use them when there is a design or a run. Tag an issue with the item id in `checklist_item` when the item raised it.

### research-core.controls
**Controls.** Is there a no-intervention, shuffled-label, random, or ablated condition that isolates the effect?

### research-core.baselines
**Baselines.** Are baselines strong, current and tuned with comparable effort? Is a trivial baseline (majority class, mean predictor, previous version) included?

### research-core.confounds
**Confounds.** Could something else explain the difference: data leakage, train/test overlap, different preprocessing, compute budget, random seed, ordering, selection of reported runs?

### research-core.power
**Statistical power.** Enough runs, seeds or samples to detect the claimed effect? Is variance reported?

### research-core.reproducibility
**Reproducibility.** Seeds, versions, configs, data splits and commands recorded? Could someone rerun it from the log alone?

### research-core.pre-specification
**Pre-specification.** Were metrics and comparisons chosen before seeing results? If a frozen protocol exists, does its hash match the spec actually used, and is a failed criterion reported as "criterion not met" rather than reinterpreted?
