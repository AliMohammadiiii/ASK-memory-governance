# Artifact manifests

These manifests bind the Git repository to source archives and external run assets without committing large outputs. Historical run directories should be released separately only after privacy, licensing, and semantic-validity review.

`repository_files.json` hashes every file in the sanitized public snapshot except
itself; excluding the manifest avoids an impossible recursive self-hash. The
release builder regenerates it before creating either ZIP.
