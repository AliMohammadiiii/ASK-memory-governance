# Reproducibility

```bash
python3.11 -m venv .venv
source .venv/bin/activate
make setup
make repo-check
make test
make validate-data
make build
```

For OpenRouter-backed experiments:

```bash
cp .env.example .env
# Set a rotated OPENROUTER_API_KEY in your shell or secret manager.
export OPENROUTER_API_KEY='...'
cat configs/models/openrouter_qwen_gemma.yaml
```

Do not pass secrets as CLI arguments because shell histories and run manifests may capture them. Record model identifiers, prompt hashes, code commit, dataset checksum, seed, and scorer version for every run.
