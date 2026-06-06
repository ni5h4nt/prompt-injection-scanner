# Contributing

Thanks for your interest in improving the Prompt Injection Scanner. This is a defensive security tool; contributions are welcome from anyone, but we ask that you keep the project's purpose in mind: **detection and prevention, not exploitation.**

## What we accept

- **New detection patterns** — heuristic rules, attack examples for the training data, refinements to the threat taxonomy.
- **Performance work** — faster heuristic matching, smarter early-exit logic, embedding-cache improvements.
- **Bug fixes** — including detection-logic bugs (these are tracked under `SECURITY.md`'s "false positive / detection bypass" categories).
- **Documentation** — clearer explanations, more usage examples, threat-model refinements.
- **Tests** — the project has a thin test suite; pull requests that add unit or integration tests for existing behaviour are especially welcome.

## What we will not accept

- New attack payloads with no defensive value (i.e. anything that looks like a how-to rather than a detection sample).
- Features that exfiltrate user prompts to third-party services without explicit opt-in.
- Changes that weaken the structured-output validation on the Guardian agent.

## Development workflow

1. Fork the repository and create a feature branch:
   ```bash
   git checkout -b feat/<short-description>
   ```
2. Install with development dependencies:
   ```bash
   poetry install --with dev --extras "ml"
   ```
3. Make your change. Keep PRs small and focused — one logical change per PR.
4. Run the checks locally:
   ```bash
   poetry run pytest tests/unit/
   poetry run black --check .
   poetry run ruff check .
   ```
5. Write a clear commit message. We follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` new feature
   - `fix:` bug fix
   - `docs:` documentation
   - `test:` tests only
   - `build(deps):` dependency changes
   - `refactor:` no behaviour change
6. Open a pull request against `main` with:
   - A summary of what changed and why
   - Reproduction or test steps
   - For new detection rules: at least one positive and one negative example

## Adding training examples

Training data lives in `src/prompt_injection_scanner/data/training/` as YAML, organised by threat category. To add an example:

1. Edit the relevant category file (e.g. `system_override_examples.yaml`).
2. Add a `text` / `label` / `severity` / `confidence` / `source` entry.
3. Regenerate the combined dataset if you maintain `all_training_examples.yaml` separately.
4. Note the source in your PR — if the example comes from a public research paper or dataset, link to it.

## Code of Conduct

Participation is governed by `CODE_OF_CONDUCT.md`. Treat other contributors with respect.

## Reporting security issues

Do **not** open public issues for security reports. See `SECURITY.md` for the private disclosure process.
