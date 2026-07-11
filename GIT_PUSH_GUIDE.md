# Git push guide

The downloadable `READY_TO_PUSH` archive already contains an initialized `.git` directory and an initial commit on `main`.

```bash
unzip ksa-memory-governance_READY_TO_PUSH.zip
cd ksa-memory-governance
git status
git remote add origin <YOUR_GITHUB_REPOSITORY_URL>
git push -u origin main
```

Before publishing, replace `OWNER` in `pyproject.toml` and `CITATION.cff`, rotate the API credential previously shared in chat, and confirm the MGP-6 data license.
