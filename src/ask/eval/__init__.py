"""LongMemEval-S evaluation surface.

The grader, evaluator driver, and report types are baseline-agnostic — they
operate on `BaselineAnswer` objects regardless of which baseline produced them.
"""

from .judge import JudgeBackendConfig, build_judge_backend
from .longmemeval import (
    EvalReport,
    GradeResult,
    LongMemEvalGrader,
    bootstrap_accuracy_ci,
    evaluate_baseline,
)
from .m4w15 import (
    build_main_table,
    compute_rc_at_c,
    threshold_dir_name,
    threshold_values,
    validate_prerequisites,
)
from .m4w16 import run_m4w16, validate_artifacts
from .mgp6 import MGP6Prediction, build_prediction, compute_report
from .mgp6_schema import (
    MGP6AdvisorAnnotation,
    MGP6AdvisorScenario,
    MGP6MemoryItem,
    MGP6Scenario,
    load_mgp6_jsonl,
    strip_for_advisor,
    validate_mgp6_coverage,
)
from .smrr import SMRRResult, compute_smrr, mgp6_stale_items

__all__ = [
    "EvalReport",
    "GradeResult",
    "LongMemEvalGrader",
    "MGP6MemoryItem",
    "MGP6Scenario",
    "MGP6Prediction",
    "MGP6AdvisorAnnotation",
    "MGP6AdvisorScenario",
    "SMRRResult",
    "bootstrap_accuracy_ci",
    "evaluate_baseline",
    "JudgeBackendConfig",
    "load_mgp6_jsonl",
    "strip_for_advisor",
    "validate_mgp6_coverage",
    "build_judge_backend",
    "build_prediction",
    "compute_report",
    "compute_smrr",
    "mgp6_stale_items",
    "build_main_table",
    "compute_rc_at_c",
    "threshold_dir_name",
    "threshold_values",
    "validate_prerequisites",
    "run_m4w16",
    "validate_artifacts",
]
