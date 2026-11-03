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
    "JudgeBackendConfig",
    "LongMemEvalGrader",
    "MGP6AdvisorAnnotation",
    "MGP6AdvisorScenario",
    "MGP6MemoryItem",
    "MGP6Prediction",
    "MGP6Scenario",
    "SMRRResult",
    "bootstrap_accuracy_ci",
    "build_judge_backend",
    "build_main_table",
    "build_prediction",
    "compute_rc_at_c",
    "compute_report",
    "compute_smrr",
    "evaluate_baseline",
    "load_mgp6_jsonl",
    "mgp6_stale_items",
    "run_m4w16",
    "strip_for_advisor",
    "threshold_dir_name",
    "threshold_values",
    "validate_artifacts",
    "validate_mgp6_coverage",
    "validate_prerequisites",
]
