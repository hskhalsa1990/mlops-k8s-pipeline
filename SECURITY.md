# Security Policy

## Reporting a vulnerability
Please do **not** open a public issue for security problems. Use GitHub's private vulnerability
reporting (the repository's *Security* tab, then *Report a vulnerability*) or contact the maintainer
through the profile linked on the repository. Include the affected version or commit, reproduction
steps and the impact you observed.

We aim to acknowledge reports within 3 working days and to provide a fix or mitigation plan
within 30 days.

## Supported versions
Only the latest release and the `main` branch receive security fixes.

## Built-in safeguards
`bandit` (SAST), `gitleaks` (secrets), `pip-audit` (dependencies), Trivy (image scan) and an
SBOM per release run in CI. See the README for details.
