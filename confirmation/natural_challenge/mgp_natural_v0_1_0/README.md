# MGP-Natural v0.1.0 parent audit

This directory records safe, aggregate evidence about an external parent
archive. The parent archive is not copied into the repository.

## Pinned inputs

- Parent filename: `MGP-Natural-v0.1.0-release.zip`
- Parent SHA-256:
  `0ffe92eba00bcec503e81589965c381857f4524fdd955902678d636eca7b7f26`
- Supplied delivery report SHA-256:
  `f49082f37f2fb4f7e920c585b84efcb42a2ee4945f4f3e9e50a642dce5cb4a90`
- Supplied landscape report SHA-256:
  `6459f07ed717624b0fbcf581ce78bf944e89353f37538ac5a60dfde84345c50d`

The parent manifest covers all 136 non-manifest files and its file hashes pass.
That integrity result does not validate scientific, privacy, licensing, or
annotation claims.

## Derived version

`mgpn-natural-annotation/0.1.1-derived` is a private annotation transformation,
not a replacement source dataset. It preserves parentage while correcting the
unsafe annotation packet. It does not revise or overwrite the historical parent
manifest.

Tracked outputs are limited to:

- `archive_audit.json`, an aggregate anomaly and claim-boundary audit; and
- `private_packet_verification.json`, a safe verification receipt for the local
  private draft.

The packet, answer form, blinding secret, reveal map, and bundle remain under
`.private/mgp_natural/v0.1.0/` and are excluded from Git.

## Claim boundary

Allowed: an internally coherent 36-item Wikipedia editorial-discussion
feasibility seed with provisional constructor labels.

Not allowed: independently annotated gold benchmark, public-release-cleared
dataset, representative personal-assistant chat benchmark, valid held-out test
split, leaderboard result, or evidence of population-level performance.

The source excerpts remain subject to source-specific attribution, share-alike,
privacy, and modification-notice review. Machine validation is not legal or
ethics approval.
