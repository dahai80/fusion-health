from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GoldenCase:
    case_id: str
    text: str
    expected_codes: list[str] = field(default_factory=list)
    notes: str = ""


# Sample golden set — real deployment must expand with clinician-verified cases.
# These are simple, well-established mappings to validate the pipeline end-to-end.
GOLDEN_CASES: list[GoldenCase] = [
    GoldenCase(
        "gc-001",
        "Patient is a 65-year-old male with history of hypertension presenting with chest pain. BP 160/95.",
        ["I10"],
        "essential hypertension",
    ),
    GoldenCase(
        "gc-002",
        "Type 2 diabetes mellitus, poorly controlled, with HbA1c of 9.2%.",
        ["E11"],
        "type 2 diabetes",
    ),
    GoldenCase(
        "gc-003",
        "Acute appendicitis requiring appendectomy.",
        ["K35"],
        "acute appendicitis",
    ),
    GoldenCase(
        "gc-004",
        "Community-acquired pneumonia, right lower lobe.",
        ["J18"],
        "pneumonia",
    ),
    GoldenCase(
        "gc-005",
        "Asthma exacerbation with wheezing and shortness of breath.",
        ["J45"],
        "asthma",
    ),
]


@dataclass
class EvalResult:
    total: int
    with_any_code: int
    precision: float
    recall: float
    f1: float
    per_case: list[dict] = field(default_factory=list)


def _normalize(code: str) -> str:
    return code.strip().upper().replace(".", "").replace(" ", "")[:3]


def score_case(predicted: list[str], expected: list[str]) -> dict:
    """Score at the 3-char ICD category level (clinically meaningful grouping)."""
    pred_set = {_normalize(c) for c in predicted if c}
    exp_set = {_normalize(c) for c in expected if c}
    if not exp_set:
        return {"hit": False, "precision": 0.0, "recall": 0.0, "pred": list(pred_set), "exp": list(exp_set)}
    tp = len(pred_set & exp_set)
    precision = tp / len(pred_set) if pred_set else 0.0
    recall = tp / len(exp_set) if exp_set else 0.0
    hit = recall > 0
    return {"hit": hit, "precision": precision, "recall": recall, "pred": sorted(pred_set), "exp": sorted(exp_set)}


async def evaluate(coder, cases: list[GoldenCase] | None = None) -> EvalResult:
    cases = cases or GOLDEN_CASES
    per_case: list[dict] = []
    hits = 0
    with_code = 0
    total_tp = 0
    total_pred = 0
    total_exp = 0
    for gc in cases:
        try:
            codes = await coder.suggest_icd_codes(gc.text)
        except Exception as e:
            logger.error("eval case %s failed: %s", gc.case_id, e)
            codes = []
        if not isinstance(codes, list):
            codes = []
        # coder returns list[dict] with "code" key; normalize to code strings
        norm_codes: list[str] = []
        for c in codes:
            if isinstance(c, dict):
                v = c.get("code", "")
                if v:
                    norm_codes.append(str(v))
            elif isinstance(c, str):
                norm_codes.append(c)
        sc = score_case(norm_codes, gc.expected_codes)
        if sc["hit"]:
            hits += 1
        if norm_codes:
            with_code += 1
        total_tp += int(sc["precision"] * len(sc["pred"])) if sc["pred"] else 0
        total_pred += len(sc["pred"])
        total_exp += len(sc["exp"])
        per_case.append({"case_id": gc.case_id, **sc})
    precision = total_tp / total_pred if total_pred else 0.0
    recall = total_tp / total_exp if total_exp else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return EvalResult(
        total=len(cases),
        with_any_code=with_code,
        precision=precision,
        recall=recall,
        f1=f1,
        per_case=per_case,
    )


def format_report(result: EvalResult) -> str:
    lines = [
        f"clinical eval: {result.total} cases, {result.with_any_code} returned codes, {sum(1 for c in result.per_case if c['hit'])}/{result.total} hit",
        f"precision={result.precision:.2f} recall={result.recall:.2f} f1={result.f1:.2f}",
    ]
    for c in result.per_case:
        mark = "✓" if c["hit"] else "✗"
        lines.append(f"  {mark} {c['case_id']} pred={c['pred']} exp={c['exp']}")
    return "\n".join(lines)
