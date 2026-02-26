from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class StatisticalSummary:
    count: int
    mean: float | None
    std: float | None
    confidence: float
    ci_low: float | None
    ci_high: float | None
    outliers: int


@dataclass(frozen=True)
class HypothesisTestResult:
    test: str
    statistic: float | None
    p_value: float | None
    reject_null: bool
    alpha: float


@dataclass
class ValidationResult:
    """Minimal normalized output for compatibility with engine validators."""

    passed: bool
    issues: List[Dict[str, Any]]
    summary: Dict[str, Any]


class StatisticalValidator:
    """
    Production-safe statistical validator.

    Capabilities:
    - Compute mean/std and a normal-approx confidence interval
    - MAD-based outlier detection (robust)
    - Optional z-test against a target mean (two-sided)

    Normalized output:
      ValidationResult(passed: bool, issues: list[dict], summary: dict)
      issues item: {"severity": "info"|"warning"|"error", "message": str, ...}
      summary: {
        "count", "mean", "std", "confidence", "ci_low", "ci_high", "outliers",
        "hypothesis_test": optional dict
      }
    """

    def __init__(
        self, confidence: float = 0.95, mad_k: float = 5.0, alpha: float = 0.05
    ) -> None:
        if not (0.0 < confidence < 1.0):
            raise ValueError("confidence must be in (0, 1)")
        if not (0.0 < alpha < 1.0):
            raise ValueError("alpha must be in (0, 1)")
        self.confidence = confidence
        self.mad_k = mad_k
        self.alpha = alpha

    def _basic_stats(
        self, data: Sequence[float]
    ) -> Tuple[int, float | None, float | None]:
        n = len(data)
        if n == 0:
            return 0, None, None
        mean = sum(data) / n
        var = sum((x - mean) ** 2 for x in data) / max(n - 1, 1)
        std = math.sqrt(var)
        return n, mean, std

    def _ci_normal(
        self, n: int, mean: float | None, std: float | None
    ) -> Tuple[float | None, float | None]:
        if n <= 1 or mean is None or std is None:
            return None, None
        # Normal approx: 1.96 ~ 95%; generalize for other confidences with z from standard normal
        # For simplicity and determinism, use 1.96 for 0.95, else a close approximation via inverse error function
        if abs(self.confidence - 0.95) < 1e-9:
            z = 1.96
        else:
            # Abramowitz-Stegun approximation via math.erfcinv if available; fallback to 1.96
            try:
                # erfcinv(x) not in stdlib; approximate with numpy when available is avoided for hard deps.
                # Use a rational approximation for z from p (two-sided)
                # For robustness, clamp to [1e-9, 1-1e-9]
                p = max(min(self.confidence, 1 - 1e-9), 1e-9)
                # Beasley-Springer/Moro approximation constants
                a = [2.50662823884, -18.61500062529, 41.39119773534, -25.44106049637]  # noqa: F841
                b = [-8.47351093090, 23.08336743743, -21.06224101826, 3.13082909833]  # noqa: F841
                c = [
                    0.3374754822726147,
                    0.9761690190917186,
                    0.1607979714918209,
                    0.0276438810333863,
                    0.0038405729373609,
                    0.0003951896511919,
                    0.0000321767881768,
                    0.0000002888167364,
                    0.0000003960315187,
                ]
                # Convert confidence to tail prob
                t = math.sqrt(-2.0 * math.log(1 - p))
                z = c[0] + t * (
                    c[1]
                    + t
                    * (
                        c[2]
                        + t
                        * (
                            c[3]
                            + t
                            * (c[4] + t * (c[5] + t * (c[6] + t * (c[7] + t * c[8]))))
                        )
                    )
                )
            except Exception:
                z = 1.96
        half = z * (std / math.sqrt(n))
        return (mean - half), (mean + half)

    def _mad_outliers(self, data: Sequence[float]) -> List[float]:
        n = len(data)
        if n == 0:
            return []
        med = sorted(data)[n // 2]
        deviations = [abs(x - med) for x in data]
        mad = sorted(deviations)[n // 2]
        if mad <= 0:
            return []
        threshold = self.mad_k * mad
        return [x for x in data if abs(x - med) > threshold]

    def _z_test(
        self, mean: float | None, std: float | None, n: int, target: float
    ) -> HypothesisTestResult:
        if mean is None or std is None or n <= 0 or std == 0:
            return HypothesisTestResult(
                test="z_test_mean",
                statistic=None,
                p_value=None,
                reject_null=False,
                alpha=self.alpha,
            )
        z = (mean - target) / (std / math.sqrt(n))
        # Two-sided normal p-value approximation
        # p = 2*(1 - Phi(|z|)) ; approximate with error function erf
        p = 2.0 * (1.0 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
        return HypothesisTestResult(
            test="z_test_mean",
            statistic=z,
            p_value=p,
            reject_null=(p < self.alpha),
            alpha=self.alpha,
        )

    def validate(
        self, series: Sequence[float], target_mean: float | None = None
    ) -> ValidationResult:
        data = [float(x) for x in series if isinstance(x, (int, float))]
        issues: List[Dict[str, Any]] = []

        n, mean, std = self._basic_stats(data)
        if n == 0:
            issues.append({"severity": "warning", "message": "no_data"})
            return ValidationResult(passed=False, issues=issues, summary={"count": 0})

        ci_low, ci_high = self._ci_normal(n, mean, std)
        outliers = self._mad_outliers(data)

        if outliers:
            issues.append(
                {
                    "severity": "warning",
                    "message": "outliers_detected",
                    "count": len(outliers),
                    "examples": outliers[:3],
                }
            )

        summary = StatisticalSummary(
            count=n,
            mean=mean,
            std=std,
            confidence=self.confidence,
            ci_low=ci_low,
            ci_high=ci_high,
            outliers=len(outliers),
        )

        htest: Dict[str, Any] | None = None
        if isinstance(target_mean, (int, float)):
            ht = self._z_test(mean, std, n, float(target_mean))
            htest = {
                "test": ht.test,
                "statistic": ht.statistic,
                "p_value": ht.p_value,
                "reject_null": ht.reject_null,
                "alpha": ht.alpha,
            }
            if ht.reject_null:
                issues.append(
                    {
                        "severity": "info",
                        "message": "mean_diff_significant",
                        "p_value": ht.p_value,
                    }
                )

        summary_dict = {
            "count": summary.count,
            "mean": summary.mean,
            "std": summary.std,
            "confidence": summary.confidence,
            "ci_low": summary.ci_low,
            "ci_high": summary.ci_high,
            "outliers": summary.outliers,
        }
        if htest is not None:
            summary_dict["hypothesis_test"] = htest  # type: ignore[assignment]

        # Statistical validation is informational by default; never fatal
        passed = True
        return ValidationResult(passed=passed, issues=issues, summary=summary_dict)
