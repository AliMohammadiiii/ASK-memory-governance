# Git push guide

The release archive deliberately contains no `.git` directory and no fabricated
remote. After extracting the canonical repository package, initialize or attach
the public repository that you control.

```bash
unzip ask-memory-governance-final.zip
cd ask-memory-governance
git init
git add .
git commit -m "Initial public release"
git status
git remote add origin <YOUR_GITHUB_REPOSITORY_URL>
git push -u origin main
```

Before publishing, rotate the API credential previously shared in chat, confirm
the MGP-6 data-release consent/license, and review `LICENSE-DATA.md`. No repository
or issue URL is advertised until you supply a real remote.
