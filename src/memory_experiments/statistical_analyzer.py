"""
Statistical Analyzer

Provides statistical analysis methods for memory experiments,
including hypothesis testing, effect size calculations, and confidence intervals.
"""

import math
import statistics
from typing import List, Tuple

import numpy as np
from scipy import stats


class StatisticalAnalyzer:
    """
    Statistical analysis utilities for memory experiments.

    Provides methods for hypothesis testing, effect size calculations,
    and confidence interval estimation for experimental validation.
    """

    def __init__(self):
        self.alpha = 0.05  # Default significance level

    def ttest_independent(self, group1: List[float], group2: List[float]) -> float:
        """
        Perform independent samples t-test.

        Args:
            group1: First group of scores
            group2: Second group of scores

        Returns:
            p-value for the two-tailed test
        """
        if len(group1) < 2 or len(group2) < 2:
            return 1.0  # Cannot perform test with insufficient data

        try:
            statistic, p_value = stats.ttest_ind(group1, group2)
            return p_value
        except (ValueError, TypeError):
            return 1.0  # Return non-significant if test fails

    def ttest_paired(self, group1: List[float], group2: List[float]) -> float:
        """
        Perform paired samples t-test.

        Args:
            group1: First group of paired scores
            group2: Second group of paired scores

        Returns:
            p-value for the two-tailed test
        """
        if len(group1) != len(group2) or len(group1) < 2:
            return 1.0

        try:
            statistic, p_value = stats.ttest_rel(group1, group2)
            return p_value
        except (ValueError, TypeError):
            return 1.0

    def cohens_d(self, group1: List[float], group2: List[float]) -> float:
        """
        Calculate Cohen's d effect size.

        Args:
            group1: First group of scores
            group2: Second group of scores

        Returns:
            Cohen's d effect size
        """
        if len(group1) < 2 or len(group2) < 2:
            return 0.0

        try:
            mean1 = statistics.mean(group1)
            mean2 = statistics.mean(group2)

            # Calculate pooled standard deviation
            var1 = statistics.variance(group1)
            var2 = statistics.variance(group2)
            n1, n2 = len(group1), len(group2)

            pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))

            if pooled_std == 0:
                return 0.0

            return (mean1 - mean2) / pooled_std

        except (ValueError, statistics.StatisticsError):
            return 0.0

    def confidence_interval(
        self, data: List[float], confidence_level: float = 0.95
    ) -> Tuple[float, float]:
        """
        Calculate confidence interval for the mean.

        Args:
            data: List of data points
            confidence_level: Confidence level (e.g., 0.95 for 95%)

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        if len(data) < 2:
            return (0.0, 0.0)

        try:
            mean = statistics.mean(data)
            std_err = statistics.stdev(data) / math.sqrt(len(data))

            # Use t-distribution for small samples
            df = len(data) - 1
            alpha = 1 - confidence_level
            t_critical = stats.t.ppf(1 - alpha / 2, df)

            margin_error = t_critical * std_err

            return (mean - margin_error, mean + margin_error)

        except (ValueError, statistics.StatisticsError):
            return (0.0, 0.0)

    def variance(self, data: List[float]) -> float:
        """Calculate variance of a dataset."""
        if len(data) < 2:
            return 0.0

        try:
            return statistics.variance(data)
        except (ValueError, statistics.StatisticsError):
            return 0.0

    def correlation(self, x: List[float], y: List[float]) -> float:
        """
        Calculate Pearson correlation coefficient.

        Args:
            x: First variable
            y: Second variable

        Returns:
            Correlation coefficient (-1 to 1)
        """
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        try:
            correlation, _ = stats.pearsonr(x, y)
            return correlation
        except (ValueError, TypeError):
            return 0.0

    def anova_oneway(self, *groups: List[float]) -> Tuple[float, float]:
        """
        Perform one-way ANOVA.

        Args:
            groups: Multiple groups to compare

        Returns:
            Tuple of (F-statistic, p-value)
        """
        if len(groups) < 2:
            return 0.0, 1.0

        # Filter out empty groups
        valid_groups = [group for group in groups if len(group) >= 1]

        if len(valid_groups) < 2:
            return 0.0, 1.0

        try:
            f_stat, p_value = stats.f_oneway(*valid_groups)
            return f_stat, p_value
        except (ValueError, TypeError):
            return 0.0, 1.0

    def mann_whitney_u(self, group1: List[float], group2: List[float]) -> float:
        """
        Perform Mann-Whitney U test (non-parametric alternative to t-test).

        Args:
            group1: First group of scores
            group2: Second group of scores

        Returns:
            p-value for the test
        """
        if len(group1) < 1 or len(group2) < 1:
            return 1.0

        try:
            _, p_value = stats.mannwhitneyu(group1, group2, alternative="two-sided")
            return p_value
        except (ValueError, TypeError):
            return 1.0

    def effect_size_interpretation(self, cohens_d: float) -> str:
        """
        Interpret Cohen's d effect size.

        Args:
            cohens_d: Cohen's d value

        Returns:
            Interpretation string
        """
        abs_d = abs(cohens_d)

        if abs_d < 0.2:
            return "negligible"
        elif abs_d < 0.5:
            return "small"
        elif abs_d < 0.8:
            return "medium"
        else:
            return "large"

    def power_analysis(
        self, effect_size: float, sample_size: int, alpha: float = 0.05
    ) -> float:
        """
        Calculate statistical power for a two-sample t-test.

        Args:
            effect_size: Expected effect size (Cohen's d)
            sample_size: Sample size per group
            alpha: Significance level

        Returns:
            Statistical power (0 to 1)
        """
        try:
            from statsmodels.stats.power import ttest_power

            power = ttest_power(
                effect_size, sample_size, alpha, alternative="two-sided"
            )
            return max(0.0, min(1.0, power))
        except ImportError:
            # Fallback approximation if statsmodels not available
            return self._approximate_power(effect_size, sample_size, alpha)

    def _approximate_power(
        self, effect_size: float, sample_size: int, alpha: float
    ) -> float:
        """Approximate power calculation without statsmodels."""
        # Simple approximation based on normal distribution
        z_alpha = stats.norm.ppf(1 - alpha / 2)
        z_beta = effect_size * math.sqrt(sample_size / 2) - z_alpha
        power = stats.norm.cdf(z_beta)
        return max(0.0, min(1.0, power))

    def sample_size_calculation(
        self, effect_size: float, power: float = 0.8, alpha: float = 0.05
    ) -> int:
        """
        Calculate required sample size for desired power.

        Args:
            effect_size: Expected effect size (Cohen's d)
            power: Desired statistical power
            alpha: Significance level

        Returns:
            Required sample size per group
        """
        try:
            from statsmodels.stats.power import tt_solve_power

            sample_size = tt_solve_power(
                effect_size=effect_size, power=power, alpha=alpha
            )
            return max(1, int(math.ceil(sample_size)))
        except ImportError:
            # Fallback approximation
            return self._approximate_sample_size(effect_size, power, alpha)

    def _approximate_sample_size(
        self, effect_size: float, power: float, alpha: float
    ) -> int:
        """Approximate sample size calculation."""
        z_alpha = stats.norm.ppf(1 - alpha / 2)
        z_beta = stats.norm.ppf(power)

        if effect_size == 0:
            return 1000  # Very large sample needed for zero effect

        n = 2 * ((z_alpha + z_beta) / effect_size) ** 2
        return max(1, int(math.ceil(n)))

    def multiple_comparison_correction(
        self, p_values: List[float], method: str = "bonferroni"
    ) -> List[float]:
        """
        Apply multiple comparison correction.

        Args:
            p_values: List of uncorrected p-values
            method: Correction method ("bonferroni", "holm", "fdr_bh")

        Returns:
            List of corrected p-values
        """
        if not p_values:
            return []

        try:
            from statsmodels.stats.multitest import multipletests

            _, corrected_p, _, _ = multipletests(p_values, method=method)
            return corrected_p.tolist()
        except ImportError:
            # Fallback: simple Bonferroni correction
            if method == "bonferroni":
                n = len(p_values)
                return [min(1.0, p * n) for p in p_values]
            else:
                return p_values  # Return uncorrected if method unavailable

    def bootstrap_confidence_interval(
        self,
        data: List[float],
        statistic_func=None,
        confidence_level: float = 0.95,
        n_bootstrap: int = 1000,
    ) -> Tuple[float, float]:
        """
        Calculate bootstrap confidence interval.

        Args:
            data: Original data
            statistic_func: Function to calculate statistic (default: mean)
            confidence_level: Confidence level
            n_bootstrap: Number of bootstrap samples

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        if len(data) < 2:
            return (0.0, 0.0)

        if statistic_func is None:
            statistic_func = statistics.mean

        bootstrap_stats = []

        try:
            import random

            for _ in range(n_bootstrap):
                # Resample with replacement
                bootstrap_sample = [random.choice(data) for _ in range(len(data))]
                bootstrap_stat = statistic_func(bootstrap_sample)
                bootstrap_stats.append(bootstrap_stat)

            # Calculate percentiles
            alpha = 1 - confidence_level
            lower_percentile = (alpha / 2) * 100
            upper_percentile = (1 - alpha / 2) * 100

            lower_bound = np.percentile(bootstrap_stats, lower_percentile)
            upper_bound = np.percentile(bootstrap_stats, upper_percentile)

            return (lower_bound, upper_bound)

        except (ValueError, TypeError, statistics.StatisticsError):
            # Fallback to standard confidence interval
            return self.confidence_interval(data, confidence_level)

    def bayesian_factor(self, group1: List[float], group2: List[float]) -> float:
        """
        Calculate approximate Bayes factor for two groups.

        Args:
            group1: First group
            group2: Second group

        Returns:
            Bayes factor (BF10)
        """
        # This is a simplified approximation
        # For proper Bayesian analysis, specialized libraries would be needed

        t_stat, p_value = stats.ttest_ind(group1, group2)

        if p_value == 0:
            return float("inf")

        # Rough approximation: BF ≈ 1/p for small p-values
        # This is not mathematically rigorous but gives a sense of evidence strength
        if p_value < 0.01:
            return 1 / p_value
        elif p_value < 0.05:
            return 1 / (p_value * 2)
        else:
            return 1 / (p_value * 5)

    def generate_summary_statistics(self, data: List[float]) -> dict:
        """
        Generate comprehensive summary statistics.

        Args:
            data: List of data points

        Returns:
            Dictionary of summary statistics
        """
        if not data:
            return {}

        try:
            summary = {
                "count": len(data),
                "mean": statistics.mean(data),
                "median": statistics.median(data),
                "std_dev": statistics.stdev(data) if len(data) > 1 else 0.0,
                "variance": statistics.variance(data) if len(data) > 1 else 0.0,
                "min": min(data),
                "max": max(data),
                "range": max(data) - min(data),
            }

            # Add percentiles
            if len(data) >= 4:
                summary["q25"] = np.percentile(data, 25)
                summary["q75"] = np.percentile(data, 75)
                summary["iqr"] = summary["q75"] - summary["q25"]

            # Add skewness and kurtosis if scipy available
            try:
                summary["skewness"] = stats.skew(data)
                summary["kurtosis"] = stats.kurtosis(data)
            except (ValueError, TypeError):
                pass

            return summary

        except (ValueError, TypeError, statistics.StatisticsError):
            return {"count": len(data), "error": "Could not calculate statistics"}
