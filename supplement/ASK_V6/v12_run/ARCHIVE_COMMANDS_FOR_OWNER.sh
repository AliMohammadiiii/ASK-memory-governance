#!/usr/bin/env bash
# ARCHIVE_COMMANDS_FOR_OWNER.sh
#
# STATUS: NOT EXECUTED by the auditor. Written for the repository owner to review and run.
#
# TARGET REPOSITORY (the only repository this script reads or writes):
#   /Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance
# This is the owner's backup clone (directory name "ksa-memory-governance"). The 10 blobs below exist ONLY in this
# object store (cruft pack, unreachable from every ref, branch, tag, stash, reflog and refs/codex checkpoint tree).
# They do not exist in the public repository AliMohammadiii/ASK-memory-governance or in its local clone, so this
# script must not be pointed at that clone.
#
# WHAT IT DOES
#   Part A  verifies each blob (type, size, SHA-256 against the value recorded in the V12 run manifest). Read-only.
#   Part B  writes the 10 blobs into a new read-only archive directory OUTSIDE the repository, with SHA256SUMS.
#   Part C  (optional, run only after Part B succeeds) makes the blobs reachable without touching any branch:
#           writes a tree object holding the 10 blobs, an orphan commit object (no parent) for that tree, and one new
#           annotated tag pointing at the commit. No existing ref is moved, no history is rewritten, nothing is deleted,
#           and nothing is pushed.
#   Part D  prints the verification commands.
#
# RISK THIS ADDRESSES (inference from observed pack metadata, not a measured gc outcome): the 10 blobs sit in a cruft pack
# with recorded object mtime 2026-08-05T16:59:03Z. A later `git gc` with default settings may delete cruft objects older than
# gc.cruftExpiration (default 2 weeks). Do not run `git gc`, `git prune` or `git repack -d` on this clone before Part B.
set -euo pipefail

REPO="/Users/alimohammadi/Documents/Documents_Backup_2026-09-26/20_Academics/Master/Master/ksa-memory-governance"
ARCHIVE_DIR="$HOME/Documents/ASK_V12_EVALUATED_CODE_ARCHIVE_UNREFERENCED_BLOBS"
TAG_NAME="evidence/v12-evaluated-code-unreferenced-blobs"
export GIT_CONFIG_GLOBAL=/dev/null   # not needed on a normal workstation; remove this line if your global git config is required

G=(git -c safe.directory='*' -C "$REPO")

# blob_id  sha256_recorded_in_run_manifest  flat_file_name
ENTRIES=(
  "43937b07863aa1b7d3b5b5e750adefd8061fd445 690b54b269425f0744c78bf3ab99a46060629eac268f14614a7ecb97ef8ad988 FINAL_ANALYSIS_PLAN.md"
  "140c68726bd3039b8a0822c61dd97b6afdda9e0d 744a40279ad9016ca1285073ba1c20561534197a30dea827bea88d153cfdce77 FINAL_EVALUATION_PROTOCOL.md"
  "5aa2245509ccd3fe00c8ca26ce5e64af67c44a07 54f02b87ef98e9f0a419a186eac14372a9583832d884588deaaf71f298c07abc FINAL_METRIC_DEFINITIONS.md"
  "e7a65e90736b5f3ea83bce60d311903fc0336418 0f18176757587e948a997a3e8b98058cf356d508012528a669d34ba534dcb390 FINAL_RUN_MATRIX.yaml"
  "819270176c5b57119c1be483757e891461cee42a 82ba1a001765516884a0029f4f52d16bda2be82e87fa00aa776e5054b28f6b05 scripts__evaluation__run_longmemeval_final.sh"
  "870b1556b72147d44946f4bc2753f3cc3def1dd2 bcd982a6086c9e40494df83382176320e4c3186f5c3c7bcfaf7615d0d3fe0b01 scripts__run_baseline.py"
  "dfc9530335591166997b38f1bebd6f9bfd0767d4 a9508ecd75ebef3e7609ffe9fb075a5fe2023eb63edead4c6d387f77ce13ecd7 scripts__run_vllm_cascade.py"
  "b729d7deb89f258116431d063c1e82ecfc0840bc c4eb6a4d47b04330c246ac2f689fec6e01685fcbac515bb67852b9ce6359c425 src__ask__baselines__embeddings.py"
  "168d63ae55f88e5869a4b316405a4f9132e1238c b30942b1cc7c534301a4c6e830d71313a4dca374b68faab28cf9c67b8a6cfa6a src__ask__eval__longmemeval.py"
  "9b316b1f4247f6060fbf9b5a57c6cb7f125489a9 e6ce596b041ebbddd8e092903443bf6993009b1a4849118162b2f665166b1143 src__ask__pipeline__orchestrator.py"
)

echo "[A] verifying blobs in $REPO"
test "$("${G[@]}" rev-parse HEAD)" = "f6bf66e4766d769727edf6b42c76b9977b14978a" || echo "note: HEAD differs from the audit baseline commit; this does not affect the archive"
for e in "${ENTRIES[@]}"; do
  read -r blob sha name <<<"$e"
  test "$("${G[@]}" cat-file -t "$blob")" = "blob"
  actual="$("${G[@]}" cat-file blob "$blob" | shasum -a 256 | awk '{print $1}')"
  if [ "$actual" != "$sha" ]; then echo "SHA-256 MISMATCH for $name ($blob)"; exit 1; fi
  echo "  ok  $blob  $name"
done

echo "[B] writing immutable archive directory $ARCHIVE_DIR"
if [ -e "$ARCHIVE_DIR" ]; then echo "refusing to overwrite existing $ARCHIVE_DIR"; exit 1; fi
mkdir -p "$ARCHIVE_DIR"
for e in "${ENTRIES[@]}"; do
  read -r blob sha name <<<"$e"
  "${G[@]}" cat-file blob "$blob" > "$ARCHIVE_DIR/$name"
done
(
  cd "$ARCHIVE_DIR"
  : > SHA256SUMS
  for e in "${ENTRIES[@]}"; do read -r blob sha name <<<"$e"; echo "$sha  $name" >> SHA256SUMS; done
  shasum -a 256 -c SHA256SUMS
  { echo "git_blob_id,sha256,file"; for e in "${ENTRIES[@]}"; do read -r blob sha name <<<"$e"; echo "$blob,$sha,$name"; done; } > BLOB_IDS.csv
  printf 'Source repository: %s\nSource: unreferenced blobs hashed in the V12 controller run manifest (lme_final_controller_v12_qwen_180).\nCreated by ARCHIVE_COMMANDS_FOR_OWNER.sh; verify with: shasum -a 256 -c SHA256SUMS\n' "$REPO" > README.txt
  chmod a-w ./* 
)
chmod a-w "$ARCHIVE_DIR"
echo "  archive written and set read-only"

# ---- Part C (optional) ----------------------------------------------------------------------------------------------
# Uncomment to make the blobs reachable from a new annotated tag. This adds objects and one ref to the backup clone.
# It is additive; to undo it, delete only that tag with: git tag -d "$TAG_NAME"
#
# TREE="$(for e in "${ENTRIES[@]}"; do read -r blob sha name <<<"$e"; printf '100644 blob %s\t%s\n' "$blob" "$name"; done | "${G[@]}" mktree)"
# COMMIT="$(GIT_AUTHOR_NAME='ASK archive' GIT_AUTHOR_EMAIL='archive@invalid' GIT_COMMITTER_NAME='ASK archive' GIT_COMMITTER_EMAIL='archive@invalid' \
#            "${G[@]}" commit-tree "$TREE" -m 'Archive of 10 unreferenced evaluated code and protocol blobs for lme_final_controller_v12_qwen_180')"
# GIT_COMMITTER_NAME='ASK archive' GIT_COMMITTER_EMAIL='archive@invalid' \
#   "${G[@]}" tag -a "$TAG_NAME" -m 'Evidence archive: unreferenced evaluated blobs of the V12 controller run (hashes in the run manifest)' "$COMMIT"
# "${G[@]}" bundle create "$ARCHIVE_DIR/../ASK_V12_evaluated_blobs.bundle" "refs/tags/$TAG_NAME"   # optional offline copy

echo "[D] verification commands"
cat <<'EOF2'
  git -C "$REPO" rev-list --objects --all | grep -c -E '<blob id>'     # after Part C each blob id is listed
  shasum -a 256 -c "$ARCHIVE_DIR/SHA256SUMS"                           # archive integrity
EOF2
