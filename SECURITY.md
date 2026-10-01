# Security Policy

## Supported versions

Only the latest `main` branch is supported with security fixes.

## Reporting a vulnerability

Do **not** open a public issue for security vulnerabilities.

Use GitHub's private vulnerability reporting (**Security → Report a vulnerability**)
or contact the maintainer directly. Include:

- A description of the issue and its impact
- Steps to reproduce or a proof of concept
- Affected components (e.g. `capture/handler.py`, webhook verification)

You can expect an initial response within 7 days.

## Security-relevant notes for this repo

- **Webhook verification is fail-closed.** `capture/pipeline.py::verify_signature`
  returns `False` when the secret is unset, the header is missing, or the HMAC
  does not match. There is no "skip verification" fallback path.
- Secrets are supplied via environment variables only (`GITHUB_WEBHOOK_SECRET`,
  `DATABASE_URL`, `S3_BUCKET`). Never commit them; see `.env.example` for the
  expected variable names.
- The S3 archive bucket is created with public access blocked and SSE enabled
  (`capture/s3-bucket.sh`).
- The IAM policy in `capture/iam-policy.json` is scoped to Bedrock
  `InvokeModel` and a single S3 bucket.
