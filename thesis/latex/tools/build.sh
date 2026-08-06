#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
THESIS_DIR=$(cd -- "$SCRIPT_DIR/../.." && pwd)
REPO_ROOT=$(cd -- "$THESIS_DIR/.." && pwd)
PYTHON_BIN=${PYTHON:-python3}
TEMPLATE_CLASS="$THESIS_DIR/template/tex/tehran-thesis.cls"

if [[ ! -f "$TEMPLATE_CLASS" ]]; then
  echo "missing pinned thesis template: $TEMPLATE_CLASS" >&2
  echo "run 'make setup' to initialize the thesis/template submodule" >&2
  exit 1
fi

if [[ "${1:-}" == "--refresh-sources" ]]; then
  cd "$REPO_ROOT"
  "$PYTHON_BIN" "$SCRIPT_DIR/build_sources.py"
elif [[ -n "${1:-}" ]]; then
  echo "usage: $0 [--refresh-sources]" >&2
  exit 2
fi

cd "$THESIS_DIR/template"
xelatex -interaction=nonstopmode -halt-on-error -jobname=ask_thesis ../latex/main.tex
bibtex ask_thesis
xelatex -interaction=nonstopmode -halt-on-error -jobname=ask_thesis ../latex/main.tex
xelatex -interaction=nonstopmode -halt-on-error -jobname=ask_thesis ../latex/main.tex

OUTPUT_DIR="$THESIS_DIR/latex/compiled"
mkdir -p "$OUTPUT_DIR"
cp ask_thesis.pdf "$OUTPUT_DIR/ASK_Masters_Thesis_UT_Draft.pdf"
