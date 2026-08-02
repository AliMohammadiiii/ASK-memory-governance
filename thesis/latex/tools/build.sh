#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
THESIS_DIR=$(cd -- "$SCRIPT_DIR/../.." && pwd)
REPO_ROOT=$(cd -- "$THESIS_DIR/.." && pwd)

cd "$REPO_ROOT"
python3 "$SCRIPT_DIR/build_sources.py"

cd "$THESIS_DIR/template"
xelatex -interaction=nonstopmode -halt-on-error -jobname=ask_thesis ../latex/main.tex
bibtex ask_thesis
xelatex -interaction=nonstopmode -halt-on-error -jobname=ask_thesis ../latex/main.tex
xelatex -interaction=nonstopmode -halt-on-error -jobname=ask_thesis ../latex/main.tex

OUTPUT_DIR="$THESIS_DIR/latex/compiled"
mkdir -p "$OUTPUT_DIR"
cp ask_thesis.pdf "$OUTPUT_DIR/ASK_Masters_Thesis_UT_Draft.pdf"
