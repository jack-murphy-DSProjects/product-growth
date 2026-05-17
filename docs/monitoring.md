# Monitoring

Broad production-style monitoring is not implemented in this repository.

Package 9 owns local batch scoring observability only. Its durable contract is
`docs/score_observability.md`.

Package 9 is local-first, synthetic-only, and artefact-based. It is not real
production drift detection or automated model governance.
