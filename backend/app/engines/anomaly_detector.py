"""
Anomaly Detection Engine
Flags unusual year-over-year changes in KPIs using statistical trend analysis.
"""
from typing import List, Dict, Optional
from dataclasses import dataclass

import numpy as np
from loguru import logger


@dataclass
class AnomalyFlag:
    kpi_name: str
    current_value: float
    prior_value: float
    pct_change: float
    z_score: Optional[float]
    description: str
    severity: str   # low / medium / high / critical


def _pct_change(current: float, prior: float) -> float:
    if abs(prior) < 1e-9:
        return 0.0
    return (current - prior) / abs(prior) * 100.0


def _compute_z_score(value: float, history: List[float]) -> Optional[float]:
    if len(history) < 3:
        return None
    arr = np.array(history, dtype=float)
    mean, std = arr.mean(), arr.std()
    if std < 1e-9:
        return None
    return float((value - mean) / std)


def _severity_from_pct(pct: float) -> str:
    abs_pct = abs(pct)
    if abs_pct > 100:
        return "critical"
    elif abs_pct > 50:
        return "high"
    elif abs_pct > 25:
        return "medium"
    return "low"


def detect_anomalies(
    current_kpis: Dict[str, float],
    prior_year_kpis: Dict[str, float],
    historical_kpis: Optional[List[Dict[str, float]]] = None,
) -> List[AnomalyFlag]:
    """
    Compare current KPIs against prior year (and optional multi-year history).

    Args:
        current_kpis:    {kpi_name: value} for current year
        prior_year_kpis: {kpi_name: value} for prior year
        historical_kpis: list of {kpi_name: value} dicts (oldest first)

    Returns:
        List of AnomalyFlag sorted by severity
    """
    flags: List[AnomalyFlag] = []
    THRESHOLDS = {
        "default": 20.0,
        "revenue": 15.0,
        "profit": 25.0,
        "debt": 20.0,
        "cash": 30.0,
    }

    for kpi_name, current_val in current_kpis.items():
        prior_val = prior_year_kpis.get(kpi_name)
        if prior_val is None or abs(prior_val) < 1e-9:
            continue

        pct = _pct_change(current_val, prior_val)

        # Determine applicable threshold
        threshold = THRESHOLDS["default"]
        name_lower = kpi_name.lower()
        for key in THRESHOLDS:
            if key in name_lower:
                threshold = THRESHOLDS[key]
                break

        if abs(pct) < threshold:
            continue

        # Z-score from multi-year history if available
        z_score = None
        if historical_kpis:
            history = [h.get(kpi_name) for h in historical_kpis if h.get(kpi_name) is not None]
            if history:
                z_score = _compute_z_score(current_val, history + [prior_val])

        direction = "increased" if pct > 0 else "decreased"
        severity = _severity_from_pct(pct)

        description = (
            f"{kpi_name} {direction} by {abs(pct):.1f}% "
            f"({prior_val:,.2f} → {current_val:,.2f})."
        )
        if z_score is not None:
            description += f" Z-score: {z_score:.2f} (vs. multi-year trend)."

        flags.append(AnomalyFlag(
            kpi_name=kpi_name,
            current_value=current_val,
            prior_value=prior_val,
            pct_change=round(pct, 2),
            z_score=round(z_score, 2) if z_score is not None else None,
            description=description,
            severity=severity,
        ))

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    flags.sort(key=lambda f: severity_order.get(f.severity, 99))

    logger.info(f"Anomaly detection: {len(flags)} flags")
    return flags
