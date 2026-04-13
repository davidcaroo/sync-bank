# Clean Architecture & Scalability Skill

Purpose:
- Provide guidance and automated checks to prioritize scalability, separation of concerns, clean code, and established design patterns across the Sync-bank codebase.

When to use:
- During code reviews, refactoring sprints, or before merging significant backend/frontend changes.

Guidance and rules:
- Enforce single responsibility: modules/services should have one clear responsibility (e.g., `alegra_service`, `ingestion_service`, `provider_mapping_service`).
- Explicit interfaces: prefer small, typed function signatures and data models (`pydantic` or dataclasses) for boundaries.
- Dependency inversion: avoid direct global imports where possible; prefer passing dependencies or using lightweight factories.
- Avoid anemic models: keep domain logic close to domain models (e.g., invoice normalization belongs to `xml_parser`/`models.factura`).
- Error handling: centralize common HTTP/external API errors and avoid swallowing exceptions silently.
- Tests: require unit tests for service logic and integration tests for external interactions (mock Alegra/Supabase).
- Performance: highlight hot-paths (ingestion, bulk recompute) for batching and pagination; recommend async best practices and connection pooling.
- Code style: suggest linters and formatters (black/ruff/flake8/eslint + Prettier) and minimal cyclomatic complexity.

Outputs:
- Concrete refactor suggestions with file references and code snippets.
- A checklist for reviewers and a minimal CI job to run static analysis and linters.

Notes:
- This skill focuses on maintainability and scale; it will not auto-apply changes but will generate suggested patches and tests when requested.
