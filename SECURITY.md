# Security policy

## Supported versions

Security fixes are applied to the current `main` branch and the latest published
package release. Historical experiment snapshots are not maintained runtime
branches.

## Reporting

Do not open a public issue containing credentials, private conversations,
participant data, or exploitable deployment details. Report suspected exposure
privately to the repository owner with the affected path, revision, and minimal
reproduction information.

Rotate any credential that appeared in chat, logs, commits, CI output, or shared
artifacts. Removing the text from the latest revision does not make an exposed
credential safe.

## Release safety

- Keep credentials in the environment or a secret manager, never in configs or
  CLI arguments.
- Keep external and private data outside the repository.
- Run `make repo-check` before review and `make release-check` before publishing.
- Build releases from a clean worktree. The release builder intentionally
  ignores untracked files and scans the staged public copy.
- Treat generated model rationales and participant-level annotations as
  potentially sensitive even when direct identifiers are absent.

This repository is a research reference implementation, not a hardened
multi-tenant service. Deployment-specific authentication, authorization,
encryption, retention, deletion, isolation, and abuse controls remain the
operator's responsibility.
