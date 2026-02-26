"""
Statistical validation tools for benchmarking results.

This module provides tools for statistical validation including confidence intervals,
significance testing, and other statistical methods to ensure reliable benchmark results.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime  # compat: used in validate_results; ensure import exists
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats
from scipy.stats import norm, t

logger = logging.getLogger(__name__)


@dataclass
class StatisticalSummary:
    """Statistical summary of benchmark results."""

    mean: float
    median: float
    std_dev: float
    variance: float
    min_value: float
    max_value: float
    sample_size: int
    confidence_interval: Tuple[float, float] = None  # type: ignore[assignment]
    confidence_level: float = 0.95

    def __post_init__(self):
        """Calculate confidence interval if not provided."""
        if self.confidence_interval is None:
            self.confidence_interval = self._calculate_confidence_interval()

    def _calculate_confidence_interval(self) -> Tuple[float, float]:
        """Calculate confidence interval for the mean."""
        if self.sample_size < 2:
            return (self.mean, self.mean)

        # Calculate standard error
        std_error = self.std_dev / math.sqrt(self.sample_size)

        # Calculate margin of error
        alpha = 1 - self.confidence_level
        if self.sample_size < 30:
            # Use t-distribution for small samples
            t_value = t.ppf(1 - alpha / 2, self.sample_size - 1)
        else:
            # Use normal distribution for large samples
            t_value = norm.ppf(1 - alpha / 2)

        margin_of_error = t_value * std_error

        return (self.mean - margin_of_error, self.mean + margin_of_error)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mean": self.mean,
            "median": self.median,
            "std_dev": self.std_dev,
            "variance": self.variance,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "sample_size": self.sample_size,
            "confidence_level": self.confidence_level,
            "confidence_interval": self.confidence_interval,
            "margin_of_error": (
                self.confidence_interval[1] - self.mean
                if self.confidence_interval
                else 0.0
            ),
        }


@dataclass
class HypothesisTestResult:
    """Result of a hypothesis test."""

    test_name: str
    test_statistic: float
    p_value: float
    alpha: float
    null_hypothesis: str
    alternative_hypothesis: str
    conclusion: str
    effect_size: Optional[float] = None
    confidence_interval: Optional[Tuple[float, float]] = None

    def is_significant(self) -> bool:
        """Check if result is statistically significant."""
        return self.p_value < self.alpha

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_name": self.test_name,
            "test_statistic": self.test_statistic,
            "p_value": self.p_value,
            "alpha": self.alpha,
            "significant": self.is_significant(),
            "null_hypothesis": self.null_hypothesis,
            "alternative_hypothesis": self.alternative_hypothesis,
            "conclusion": self.conclusion,
            "effect_size": self.effect_size,
            "confidence_interval": self.confidence_interval,
        }


class StatisticalValidator:
    """
    Statistical validation for benchmarking results.

    This class provides methods for statistical validation including
    confidence intervals, hypothesis testing, and effect size calculation.
    """

    def __init__(self, confidence_level: float = 0.95):
        """
        Initialize the statistical validator.

        Args:
            confidence_level: Default confidence level for intervals
        """
        self.confidence_level = confidence_level
        self.results_history = []  # type: ignore[var-annotated]

        logger.info(
            f"Initialized StatisticalValidator with confidence level: {confidence_level}"
        )

    def calculate_summary(self, data: List[float]) -> StatisticalSummary:
        """
        Calculate statistical summary of data.

        Args:
            data: List of numerical values

        Returns:
            StatisticalSummary object
        """
        if not data:
            raise ValueError("Data list cannot be empty")

        data_array = np.array(data)

        return StatisticalSummary(
            mean=float(np.mean(data_array)),
            median=float(np.median(data_array)),
            std_dev=float(np.std(data_array, ddof=1)),
            variance=float(np.var(data_array, ddof=1)),
            min_value=float(np.min(data_array)),
            max_value=float(np.max(data_array)),
            sample_size=len(data),
            confidence_level=self.confidence_level,
        )

    def calculate_confidence_interval(
        self, data: List[float], confidence_level: Optional[float] = None
    ) -> Tuple[float, float]:
        """
        Calculate confidence interval for the mean.

        Args:
            data: List of numerical values
            confidence_level: Confidence level (0-1)

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        if len(data) < 2:
            return (data[0], data[0]) if data else (0.0, 0.0)

        confidence_level = confidence_level or self.confidence_level
        summary = self.calculate_summary(data)
        summary.confidence_level = confidence_level

        return summary.confidence_interval

    def t_test_one_sample(
        self,
        data: List[float],
        expected_mean: float,
        alpha: float = 0.05,
        alternative: str = "two-sided",
    ) -> HypothesisTestResult:
        """
        Perform one-sample t-test.

        Args:
            data: List of numerical values
            expected_mean: Expected population mean
            alpha: Significance level
            alternative: Alternative hypothesis ('two-sided', 'less', 'greater')

        Returns:
            HypothesisTestResult object
        """
        if len(data) < 2:
            raise ValueError("Data must contain at least 2 values for t-test")

        # Perform t-test
        t_stat, p_value = stats.ttest_1samp(
            data, expected_mean, alternative=alternative
        )

        # Adjust p-value for one-sided tests
        if alternative == "less" or alternative == "greater":
            p_value = p_value / 2

        # Calculate effect size (Cohen's d)
        effect_size = (np.mean(data) - expected_mean) / np.std(data, ddof=1)

        # Formulate hypotheses
        null_hypothesis = f"Population mean = {expected_mean}"
        if alternative == "two-sided":
            alternative_hypothesis = f"Population mean ≠ {expected_mean}"
        elif alternative == "less":
            alternative_hypothesis = f"Population mean < {expected_mean}"
        else:  # greater
            alternative_hypothesis = f"Population mean > {expected_mean}"

        # Determine conclusion
        if p_value < alpha:
            conclusion = f"Reject null hypothesis at α={alpha}"
        else:
            conclusion = f"Fail to reject null hypothesis at α={alpha}"

        return HypothesisTestResult(
            test_name="One-sample t-test",
            test_statistic=float(t_stat),
            p_value=float(p_value),
            alpha=alpha,
            null_hypothesis=null_hypothesis,
            alternative_hypothesis=alternative_hypothesis,
            conclusion=conclusion,
            effect_size=float(effect_size),
        )

    def t_test_two_samples(
        self,
        data1: List[float],
        data2: List[float],
        alpha: float = 0.05,
        equal_var: bool = True,
        alternative: str = "two-sided",
    ) -> HypothesisTestResult:
        """
        Perform two-sample t-test.

        Args:
            data1: First sample of numerical values
            data2: Second sample of numerical values
            alpha: Significance level
            equal_var: Assume equal variances
            alternative: Alternative hypothesis ('two-sided', 'less', 'greater')

        Returns:
            HypothesisTestResult object
        """
        if len(data1) < 2 or len(data2) < 2:
            raise ValueError("Both samples must contain at least 2 values for t-test")

        # Perform t-test
        t_stat, p_value = stats.ttest_ind(
            data1, data2, equal_var=equal_var, alternative=alternative
        )

        # Adjust p-value for one-sided tests
        if alternative == "less" or alternative == "greater":
            p_value = p_value / 2

        # Calculate effect size (Cohen's d)
        mean1, mean2 = np.mean(data1), np.mean(data2)
        std1, std2 = np.std(data1, ddof=1), np.std(data2, ddof=1)

        if equal_var:
            # Pooled standard deviation
            n1, n2 = len(data1), len(data2)
            pooled_std = math.sqrt(
                ((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2)
            )
            effect_size = (mean1 - mean2) / pooled_std
        else:
            # Welch's t-test effect size
            effect_size = (mean1 - mean2) / math.sqrt((std1**2 + std2**2) / 2)

        # Formulate hypotheses
        null_hypothesis = "Population means are equal"
        if alternative == "two-sided":
            alternative_hypothesis = "Population means are not equal"
        elif alternative == "less":
            alternative_hypothesis = "Population mean 1 < Population mean 2"
        else:  # greater
            alternative_hypothesis = "Population mean 1 > Population mean 2"

        # Determine conclusion
        if p_value < alpha:
            conclusion = f"Reject null hypothesis at α={alpha}"
        else:
            conclusion = f"Fail to reject null hypothesis at α={alpha}"

        return HypothesisTestResult(
            test_name="Two-sample t-test",
            test_statistic=float(t_stat),
            p_value=float(p_value),
            alpha=alpha,
            null_hypothesis=null_hypothesis,
            alternative_hypothesis=alternative_hypothesis,
            conclusion=conclusion,
            effect_size=float(effect_size),
        )

    def paired_t_test(
        self,
        data1: List[float],
        data2: List[float],
        alpha: float = 0.05,
        alternative: str = "two-sided",
    ) -> HypothesisTestResult:
        """
        Perform paired t-test.

        Args:
            data1: First sample of numerical values
            data2: Second sample of numerical values
            alpha: Significance level
            alternative: Alternative hypothesis ('two-sided', 'less', 'greater')

        Returns:
            HypothesisTestResult object
        """
        if len(data1) != len(data2):
            raise ValueError("Paired samples must have the same length")

        if len(data1) < 2:
            raise ValueError("Samples must contain at least 2 values for t-test")

        # Calculate differences
        differences = [x - y for x, y in zip(data1, data2)]

        # Perform paired t-test
        t_stat, p_value = stats.ttest_rel(data1, data2, alternative=alternative)

        # Adjust p-value for one-sided tests
        if alternative == "less" or alternative == "greater":
            p_value = p_value / 2

        # Calculate effect size (Cohen's d for paired samples)
        mean_diff = np.mean(differences)
        std_diff = np.std(differences, ddof=1)
        effect_size = mean_diff / std_diff if std_diff > 0 else 0.0

        # Formulate hypotheses
        null_hypothesis = "Mean difference = 0"
        if alternative == "two-sided":
            alternative_hypothesis = "Mean difference ≠ 0"
        elif alternative == "less":
            alternative_hypothesis = "Mean difference < 0"
        else:  # greater
            alternative_hypothesis = "Mean difference > 0"

        # Determine conclusion
        if p_value < alpha:
            conclusion = f"Reject null hypothesis at α={alpha}"
        else:
            conclusion = f"Fail to reject null hypothesis at α={alpha}"

        return HypothesisTestResult(
            test_name="Paired t-test",
            test_statistic=float(t_stat),
            p_value=float(p_value),
            alpha=alpha,
            null_hypothesis=null_hypothesis,
            alternative_hypothesis=alternative_hypothesis,
            conclusion=conclusion,
            effect_size=float(effect_size),
        )

    def anova_test(
        self, samples: Dict[str, List[float]], alpha: float = 0.05
    ) -> HypothesisTestResult:
        """
        Perform one-way ANOVA test.

        Args:
            samples: Dictionary of sample groups
            alpha: Significance level

        Returns:
            HypothesisTestResult object
        """
        if len(samples) < 2:
            raise ValueError("ANOVA requires at least 2 sample groups")

        # Prepare data for ANOVA
        sample_lists = list(samples.values())

        # Check sample sizes
        for sample in sample_lists:
            if len(sample) < 2:
                raise ValueError("Each sample group must contain at least 2 values")

        # Perform ANOVA
        f_stat, p_value = stats.f_oneway(*sample_lists)

        # Calculate effect size (eta-squared)
        grand_mean = np.mean([val for sample in sample_lists for val in sample])
        ss_total = sum(
            (val - grand_mean) ** 2 for sample in sample_lists for val in sample
        )
        ss_between = sum(
            len(sample) * (np.mean(sample) - grand_mean) ** 2 for sample in sample_lists
        )
        eta_squared = ss_between / ss_total if ss_total > 0 else 0.0

        # Formulate hypotheses
        null_hypothesis = "All population means are equal"
        alternative_hypothesis = "At least one population mean is different"

        # Determine conclusion
        if p_value < alpha:
            conclusion = f"Reject null hypothesis at α={alpha}"
        else:
            conclusion = f"Fail to reject null hypothesis at α={alpha}"

        return HypothesisTestResult(
            test_name="One-way ANOVA",
            test_statistic=float(f_stat),
            p_value=float(p_value),
            alpha=alpha,
            null_hypothesis=null_hypothesis,
            alternative_hypothesis=alternative_hypothesis,
            conclusion=conclusion,
            effect_size=float(eta_squared),
        )

    def chi_square_test(
        self, observed: List[int], expected: List[int], alpha: float = 0.05
    ) -> HypothesisTestResult:
        """
        Perform chi-square goodness-of-fit test.

        Args:
            observed: List of observed frequencies
            expected: List of expected frequencies
            alpha: Significance level

        Returns:
            HypothesisTestResult object
        """
        if len(observed) != len(expected):
            raise ValueError("Observed and expected lists must have the same length")

        if sum(observed) == 0 or sum(expected) == 0:
            raise ValueError("Observed and expected frequencies cannot sum to zero")

        # Perform chi-square test
        chi2_stat, p_value = stats.chisquare(observed, expected)

        # Calculate effect size (Cramer's V)
        n = sum(observed)
        k = len(observed)
        phi = math.sqrt(chi2_stat / n)
        cramers_v = phi / math.sqrt(k - 1) if k > 1 else 0.0

        # Formulate hypotheses
        null_hypothesis = "Observed frequencies match expected frequencies"
        alternative_hypothesis = (
            "Observed frequencies do not match expected frequencies"
        )

        # Determine conclusion
        if p_value < alpha:
            conclusion = f"Reject null hypothesis at α={alpha}"
        else:
            conclusion = f"Fail to reject null hypothesis at α={alpha}"

        return HypothesisTestResult(
            test_name="Chi-square goodness-of-fit",
            test_statistic=float(chi2_stat),
            p_value=float(p_value),
            alpha=alpha,
            null_hypothesis=null_hypothesis,
            alternative_hypothesis=alternative_hypothesis,
            conclusion=conclusion,
            effect_size=float(cramers_v),
        )

    def correlation_test(
        self,
        x: List[float],
        y: List[float],
        alpha: float = 0.05,
        method: str = "pearson",
    ) -> HypothesisTestResult:
        """
        Perform correlation test.

        Args:
            x: First variable
            y: Second variable
            alpha: Significance level
            method: Correlation method ('pearson', 'spearman', 'kendall')

        Returns:
            HypothesisTestResult object
        """
        if len(x) != len(y):
            raise ValueError("x and y must have the same length")

        if len(x) < 3:
            raise ValueError("Correlation test requires at least 3 observations")

        # Perform correlation test
        if method == "pearson":
            corr, p_value = stats.pearsonr(x, y)
        elif method == "spearman":
            corr, p_value = stats.spearmanr(x, y)
        elif method == "kendall":
            corr, p_value = stats.kendalltau(x, y)
        else:
            raise ValueError(f"Unknown correlation method: {method}")

        # Formulate hypotheses
        null_hypothesis = f"No {method} correlation between variables"
        alternative_hypothesis = (
            f"{method.capitalize()} correlation exists between variables"
        )

        # Determine conclusion
        if p_value < alpha:
            conclusion = f"Reject null hypothesis at α={alpha}"
        else:
            conclusion = f"Fail to reject null hypothesis at α={alpha}"

        return HypothesisTestResult(
            test_name=f"{method.capitalize()} correlation test",
            test_statistic=float(corr),
            p_value=float(p_value),
            alpha=alpha,
            null_hypothesis=null_hypothesis,
            alternative_hypothesis=alternative_hypothesis,
            conclusion=conclusion,
            effect_size=float(corr),
        )

    def normality_test(
        self, data: List[float], alpha: float = 0.05, method: str = "shapiro"
    ) -> HypothesisTestResult:
        """
        Perform normality test.

        Args:
            data: List of numerical values
            alpha: Significance level
            method: Test method ('shapiro', 'kstest', 'normaltest')

        Returns:
            HypothesisTestResult object
        """
        if len(data) < 3:
            raise ValueError("Normality test requires at least 3 observations")

        # Perform normality test
        if method == "shapiro":
            if len(data) > 5000:
                raise ValueError(
                    "Shapiro-Wilk test is not recommended for samples > 5000"
                )
            stat, p_value = stats.shapiro(data)
        elif method == "kstest":
            stat, p_value = stats.kstest(
                data, "norm", args=(np.mean(data), np.std(data))
            )
        elif method == "normaltest":
            stat, p_value = stats.normaltest(data)
        else:
            raise ValueError(f"Unknown normality test method: {method}")

        # Formulate hypotheses
        null_hypothesis = "Data follows a normal distribution"
        alternative_hypothesis = "Data does not follow a normal distribution"

        # Determine conclusion
        if p_value < alpha:
            conclusion = f"Reject null hypothesis at α={alpha}"
        else:
            conclusion = f"Fail to reject null hypothesis at α={alpha}"

        return HypothesisTestResult(
            test_name=f"{method.capitalize()} normality test",
            test_statistic=float(stat),
            p_value=float(p_value),
            alpha=alpha,
            null_hypothesis=null_hypothesis,
            alternative_hypothesis=alternative_hypothesis,
            conclusion=conclusion,
        )

    def power_analysis(
        self,
        effect_size: float,
        alpha: float = 0.05,
        power: float = 0.8,
        test_type: str = "t-test",
        alternative: str = "two-sided",
    ) -> Dict[str, Any]:
        """
        Perform power analysis to determine required sample size.

        Args:
            effect_size: Expected effect size
            alpha: Significance level
            power: Desired statistical power
            test_type: Type of test ('t-test', 'anova', 'correlation')
            alternative: Alternative hypothesis type

        Returns:
            Dictionary with power analysis results
        """
        from statsmodels.stats.power import FTestAnovaPower, TTestIndPower

        if test_type == "t-test":
            power_analysis = TTestIndPower()
            if alternative == "two-sided":
                n = power_analysis.solve_power(
                    effect_size=effect_size,
                    alpha=alpha,
                    power=power,
                    alternative="two-sided",
                )
            else:
                n = power_analysis.solve_power(
                    effect_size=effect_size,
                    alpha=alpha,
                    power=power,
                    alternative="one-sided",
                )
        elif test_type == "anova":
            power_analysis = FTestAnovaPower()
            n = power_analysis.solve_power(
                effect_size=effect_size, alpha=alpha, power=power
            )
        elif test_type == "correlation":
            # For correlation, effect size is the correlation coefficient
            power_analysis = TTestIndPower()
            # Transform correlation to Cohen's d
            d = 2 * effect_size / math.sqrt(1 - effect_size**2)
            n = power_analysis.solve_power(effect_size=d, alpha=alpha, power=power)
        else:
            raise ValueError(f"Unknown test type: {test_type}")

        return {
            "test_type": test_type,
            "effect_size": effect_size,
            "alpha": alpha,
            "power": power,
            "required_sample_size": int(math.ceil(n)),
            "alternative": alternative,
        }

    def validate_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate benchmark results using statistical methods.

        Args:
            results: Dictionary of benchmark results

        Returns:
            Dictionary with validation results
        """
        validation_results = {
            "validation_timestamp": datetime.now().isoformat(),
            "metrics": {},
            "overall_validity": True,
        }

        for metric_name, metric_data in results.items():
            if isinstance(metric_data, list) and all(
                isinstance(x, (int, float)) for x in metric_data
            ):
                # Calculate statistical summary
                summary = self.calculate_summary(metric_data)

                # Test for normality
                if len(metric_data) >= 3:
                    normality_result = self.normality_test(metric_data)
                    is_normal = not normality_result.is_significant()
                else:
                    is_normal = None

                # Calculate coefficient of variation
                cv = (
                    (summary.std_dev / summary.mean)
                    if summary.mean != 0
                    else float("inf")
                )

                # Determine validity
                is_valid = True
                validity_issues = []

                # Check for high variability
                if cv > 0.5:  # Coefficient of variation > 50%
                    is_valid = False
                    validity_issues.append("High variability detected")

                # Check for small sample size
                if summary.sample_size < 5:
                    is_valid = False
                    validity_issues.append("Sample size too small")

                # Update overall validity
                if not is_valid:
                    validation_results["overall_validity"] = False

                validation_results["metrics"][metric_name] = {  # type: ignore[index]
                    "summary": summary.to_dict(),
                    "is_normal": is_normal,
                    "coefficient_of_variation": cv,
                    "is_valid": is_valid,
                    "validity_issues": validity_issues,
                }

        return validation_results
