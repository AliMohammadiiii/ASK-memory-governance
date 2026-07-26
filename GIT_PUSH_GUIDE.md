# Git publication guide

The generated public archive intentionally contains no `.git` directory and no
fabricated remote. Validate the extracted repository before publishing:

```bash
unzip ask-memory-governance-final.zip
cd ask-memory-governance
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
make release-check
```

Then initialize the public history and attach a repository you control:

```bash
git init -b main
git add .
git commit -m "Initial public ASK memory governance release"
export ASK_REPOSITORY_URL='https://your-host.example/owner/repository.git'
git remote add origin "$ASK_REPOSITORY_URL"
git push -u origin main
```

Before publication, review `LICENSE-DATA.md`, confirm all required
redistribution consent, and rotate any credential that has appeared outside a
secret manager. Add repository and issue URLs to metadata only after the real
public host exists.
