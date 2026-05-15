# Monitoring

Broad production-style monitoring is not implemented in this repository.

Package 9 owns local batch scoring observability only. Its durable contract is
`docs/score_observability.md`.

Package 9 should remain local-first, synthetic-only, and artefact-based. It
must not be described as real production drift detection or automated model
governance unless a later package explicitly approves and documents broader
scope.
