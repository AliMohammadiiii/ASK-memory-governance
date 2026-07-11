# Environment record — M1-W1 (tag `v0.1.0-m1w1`)

This is the build under which the **49 M1-W1 tests pass** (20 Month-0 +
11 longmemeval + 11 llm-harness + 5 ollama + 2 e2e-smoke). The acceptance
benchmark in `NOTES/inference_bench.md` records the GPU-side numbers
separately.

## Sandbox dev environment (where the tests above were run)

| Component | Value |
|-----------|-------|
| OS                   | Ubuntu 22.04.5 LTS (jammy) |
| Kernel               | Linux 6.8.0-106-generic, aarch64 |
| Python               | 3.10.12 (system) — note: `pyproject` floor is 3.11; tests still pass on 3.10 |
| pip                  | 25.3 |
| Test result          | `49 passed in 0.44s` |
| GPU                  | none (CPU only) |

The sandbox uses Python 3.10.12; the project's `requires-python` is
`>=3.11`. All 49 tests pass on 3.10 because no 3.11-only syntax is in
use, but the acceptance run **must** be on Python ≥ 3.11 per the
`pyproject` declaration.

## Acceptance environment (target — to be filled by the GPU runner)

| Component | Expected | Recorded |
|-----------|----------|----------|
| OS                   | Ubuntu 22.04 / 24.04 | _record at bench time_ |
| Python               | 3.11.x or 3.12.x     | _record_ |
| GPU                  | NVIDIA A100 80GB     | _record_ |
| CUDA                 | 12.1 or 12.4         | _record (`nvidia-smi`)_ |
| Driver               | ≥ 535                | _record_ |
| `torch.cuda.is_available()` | True          | _record_ |
| `torch` build        | `+cu121` or `+cu124` | _record_ |
| `transformers`       | 4.46.x – 4.49.x      | _record_ |
| `accelerate`         | 0.34.x – latest      | _record_ |
| flash-attn           | optional             | _record_ |
| bitsandbytes         | optional             | _record_ |

## Reproduction

```
git checkout v0.1.0-m1w1
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-lock.txt
PYTHONPATH=src pytest -q                         # 49 tests must pass
python scripts/bench_inference.py                # records tokens/sec
```

The bench overwrites `NOTES/inference_bench.md` with the measured
median tokens/sec; commit the update before tagging.

## Tooling versions (sandbox-confirmed `pip freeze` excerpt)

```
PyYAML==6.0.3
jsonschema==4.26.0
jsonschema-specifications==2025.9.1
referencing==0.37.0
rpds-py==0.30.0
attrs==26.1.0
pydantic==2.13.3
pydantic-core==2.46.3
annotated-types==0.7.0
typing-inspection==0.4.2
pytest==9.0.3
pluggy==1.6.0
iniconfig==2.3.0
exceptiongroup==1.3.1
tomli==2.4.1
```

The full `requirements-lock.txt` includes blanks for the ML stack — fill
those in once the bench has run on the A100.

## Why two lock surfaces

The core lock (`requirements-lock.txt`) is the artifact every later
week needs to reproduce: schema, controller, audit, harness contract.
The ML lock is environment-specific (CUDA build, GPU class) and lives
in the same file but commented out until the GPU runner records its
versions. This separation lets us bisect controller regressions
independently of CUDA upgrades.
