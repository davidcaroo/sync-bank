# Security Audit Skill

Purpose:
- Provide an automated security audit checklist and recommendations focused on backend, API, secrets management, and deployment configuration for the Sync-bank project.

When to use:
- Run during pull-request review or before production rollout.
- Use for scanning code changes that touch authentication, external integrations (Alegra, Supabase), scheduler jobs, and CI/CD.

Checks and guidance included:
- Secrets and credentials: ensure all keys (ALEGRA_TOKEN, SUPABASE_KEY, OLLAMA_URL, etc.) are only read from env vars and never committed.
- HTTP clients: enforce timeouts, retry/backoff, and follow_redirects constraints.
- Least privilege: verify Supabase service role usage and narrow API keys.
- Input validation: ensure all external inputs (XML, email attachments, Alegra payloads) are sanitized and size-limited.
- Rate limiting and backoff for external APIs (Alegra, Ollama).
- Scheduler job safety: idempotency and error handling in `scheduler.py` jobs.
- Audit logging: ensure `config_cuentas_audit` and causation logs are written and cannot leak secrets.
- Dependency review: flag CPEs, outdated libs, and large language model integrations that require careful runtime isolation.
- Container security: minimal base images, non-root user, and runtime CAP_DROP recommendations.

Outputs:
- Human-readable checklist and prioritized remediation steps.
- Suggested CI checks and pre-commit hooks to enforce secrets scanning and basic linting.

Notes:
- This skill is advisory: it provides recommendations and concrete code pointers but does not autonomously change runtime secrets.
