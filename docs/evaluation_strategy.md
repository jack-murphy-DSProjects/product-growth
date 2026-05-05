# Evaluation Strategy

Evaluation is implemented in Package 6 according to
`docs/model_evaluation.md`.

Package 6 compares local Package 5 candidate models against Package 4 rule
baselines using fixed holdout evaluation, holdout-month temporal robustness
slices, GTM capacity metrics, calibration checks, segment robustness, and
illustrative utility sensitivity.

Package 6 does not implement a full rolling retraining backtest in the MVP.
Evaluation outputs are generated artefacts and must remain out of git unless
explicitly added as safe examples in a later package.
