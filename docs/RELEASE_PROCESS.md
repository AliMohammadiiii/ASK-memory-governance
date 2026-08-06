# Research release process

The public artifact is built from a clean frozen commit and an allowlist, never
from an ad-hoc working directory. Resolve the license matrix, run all machine
checks, build manuscript and supplement, perform anonymity/privacy review on
the actual archive, generate a per-file SHA-256 manifest, and independently
inspect extraction of the archive.

The release must preserve historical evidence unchanged, identify withheld
artifacts and acquisition routes, and include exact provenance and claim
eligibility. `release/RELEASE_CHECKLIST.md` is the operational checklist.
