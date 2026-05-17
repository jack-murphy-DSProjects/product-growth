# Docs Index

Use this page to choose a short path through the repository instead of reading
every contract in order.

## Start Here

- [`README.md`](../README.md) — project thesis, five-minute review paths, final
  output example, and local demo commands
- [`problem_framing.md`](problem_framing.md) — the GTM problem the workflow is
  meant to model
- [`architecture.md`](architecture.md) — the implemented local batch flow
- [`model_card.md`](model_card.md) — intended use, limits, evaluation stance,
  and human review boundary

## Business Context

- [`problem_framing.md`](problem_framing.md) — churn, expansion, capacity, and
  decision framing
- [`revops_playbook.md`](revops_playbook.md) — how a RevOps or GTM reviewer
  should read the final local policy table
- [`gtm_policy.md`](gtm_policy.md) — the locked deterministic `gtm_policy_v1`
  contract
- [`tradeoffs.md`](tradeoffs.md) — why the project stays local, batch-oriented,
  and policy-explicit

## Technical Proof

- [`feature_contract.md`](feature_contract.md) — point-in-time grain, labels,
  and leakage rules
- [`model_training.md`](model_training.md) — candidate model contract
- [`model_evaluation.md`](model_evaluation.md) — baseline-versus-ML evaluation
  and champion selection
- [`model_registry.md`](model_registry.md) — local MLflow promotion handoff
- [`batch_scoring.md`](batch_scoring.md) — raw score generation and rerun
  semantics
- [`score_observability.md`](score_observability.md) — local score checks and
  summaries
- `tests/` — executable evidence for the implemented contracts

## Demo And Reference Output

- [`demo_walkthrough.md`](demo_walkthrough.md) — runnable reviewer path and safe
  inspection SQL
- [`reference_demo_result.md`](reference_demo_result.md) — one hand-written
  successful local reference outcome without committing generated artefacts
- [`synthetic_data.md`](synthetic_data.md) — deterministic public-safe source
  generation

## Maintainer And Process Docs

- [`project_closeout.md`](project_closeout.md) — final closeout stance and
  public-safety checklist
- [`packages.md`](packages.md) — package history, boundaries, and acceptance
  criteria
- [`decisions.md`](decisions.md) — durable implementation decisions
- [`runbook.md`](runbook.md) — local execution and package-maintenance workflow
- [`security.md`](security.md) — public-repo safety rules
- [`out_of_scope.md`](out_of_scope.md) — explicit non-goals
- [`agentic_execution.md`](agentic_execution.md) and `.agent/*.example` — local
  agent workflow templates, not required for understanding the portfolio story
