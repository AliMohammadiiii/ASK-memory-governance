# Evaluator card

Primary controlled metrics are action accuracy and macro-F1 over Keep,
Supersede, and Abstain, with confusion matrices, cluster-aware intervals, paired
comparisons, coverage, and failure accounting. LongMemEval answer correctness is
judge-mediated and must identify the exact judge, prompt, fallback, and missing
judgments.

Scorers must reject duplicate/missing identifiers unless coverage-aware rules
were preregistered, separate public development from hidden evaluation, never
expose hidden labels to prediction code, and preserve raw outputs. A metric is
claim-eligible only through `claims/claims.json` with zero unexplained mismatch.
Model-judge correctness is not independent human validation.

