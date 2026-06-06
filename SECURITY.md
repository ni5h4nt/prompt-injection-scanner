# Security Policy

This is a **defensive security tool**. We take vulnerability reports seriously, including reports that the *scanner itself* misclassifies, can be bypassed, or has bugs that affect its detection logic.

## Reporting a vulnerability

**Do not open public GitHub issues for security reports.**

Use GitHub's private vulnerability reporting:
1. Go to the [Security tab](https://github.com/ni5h4nt/prompt-injection-scanner/security) on this repository.
2. Click **"Report a vulnerability"**.
3. Provide a clear description, reproduction steps, and the affected version or commit SHA.

We aim to acknowledge reports within **3 business days** and provide a fix or remediation plan within **30 days** for high-severity issues.

## In-scope reports

- **Detection bypass** — a prompt-injection payload the scanner classifies as benign that should be flagged. Please include the payload and the stage scores from the API response.
- **False positives** — a benign prompt the scanner flags as malicious, especially if it follows a reproducible pattern.
- **Vulnerabilities in the scanner code** — code execution, denial of service, information disclosure, dependency CVEs not already tracked by Dependabot.
- **Guardian agent exploitation** — input that successfully manipulates the LLM-based Guardian stage into a malformed verdict or a structured-output schema violation.

## Out of scope

- **Findings only reachable via your own API keys / configuration.** Please secure your own credentials.
- **Vulnerabilities in dependencies that already have an open Dependabot alert** in this repo.
- **Theoretical attacks** without a working proof of concept.

## Coordinated disclosure

Once a fix lands, we will credit the reporter (unless anonymity is requested) in the release notes and in the relevant commit message.
