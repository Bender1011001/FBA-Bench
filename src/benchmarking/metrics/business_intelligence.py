"""
Business intelligence metrics for FBA-Bench.

This module provides advanced metrics for evaluating business performance including
strategic decision-making, market trend analysis, competitive intelligence,
risk assessment, ROI optimization, and resource allocation efficiency.
"""

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict

from .base import BaseMetric, MetricConfig


@dataclass
class MarketTrend:
    """Market trend analysis data."""

    trend_direction: str  # 'up', 'down', 'stable'
    trend_strength: float
    prediction_accuracy: float
    market_volatility: float
    time_horizon: str  # 'short', 'medium', 'long'


@dataclass
class CompetitivePosition:
    """Competitive position analysis."""

    market_share: float
    competitive_advantage: float
    brand_strength: float
    customer_loyalty: float
    innovation_index: float


@dataclass
class RiskAssessment:
    """Risk assessment data."""

    risk_level: float
    risk_categories: Dict[str, float]
    mitigation_effectiveness: float
    risk_adjusted_return: float


class BusinessIntelligenceMetrics(BaseMetric):
    """
    Advanced metrics for evaluating business intelligence capabilities.

    This class provides comprehensive evaluation of business intelligence functions
    including strategic decision-making, market analysis, competitive intelligence,
    risk assessment, and resource optimization.
    """

    def __init__(self, config: MetricConfig = None):
        """
        Initialize business intelligence metrics.

        Args:
            config: Metric configuration (uses defaults if None)
        """
        if config is None:
            config = MetricConfig(
                name="business_intelligence_performance",
                description="Business intelligence performance score",
                unit="score",
                min_value=0.0,
                max_value=100.0,
                target_value=80.0,
            )

        super().__init__(config)

        # Sub-metric configurations
        self.strategic_decision_config = MetricConfig(
            name="strategic_decision_making",
            description="Strategic decision-making quality",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.market_trend_config = MetricConfig(
            name="market_trend_analysis",
            description="Market trend analysis accuracy",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.competitive_intelligence_config = MetricConfig(
            name="competitive_intelligence",
            description="Competitive intelligence capabilities",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.risk_assessment_config = MetricConfig(
            name="risk_assessment",
            description="Risk assessment and mitigation effectiveness",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.roi_optimization_config = MetricConfig(
            name="roi_optimization",
            description="ROI optimization capabilities",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.resource_allocation_config = MetricConfig(
            name="resource_allocation",
            description="Resource allocation efficiency",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.business_outcome_config = MetricConfig(
            name="business_outcome_prediction",
            description="Business outcome prediction accuracy",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

    def calculate(self, data: Dict[str, Any]) -> float:  # type: ignore[override]
        """
        Calculate business intelligence performance score from accumulated event-driven data.

        Expected keys in data:
            - sales: List[Dict] items of SaleOccurred summaries with keys: total_revenue, total_profit, agent_id, tick
            - ad_spend: List[Dict] items of AdSpendEvent summaries with keys: spend, campaign_id, asin, agent_id, tick
            - inventory_updates: List[Dict] snapshots or events for inventory/resource utilization
            - decisions: List[Dict] agent decision/action approvals with controller priority mappings
        """
        if not isinstance(data, dict):
            return 0.0
        # Aggregate ROI: profit / ad_spend (guard zero)
        sales = data.get("sales", [])
        ad_spend = data.get("ad_spend", [])
        total_profit = sum(float(s.get("total_profit", 0.0)) for s in sales)
        total_spend = 0.0
        for a in ad_spend:
            spend = a.get("spend")
            # spend may be Money str; accept numeric or parse "$x.xx"
            if isinstance(spend, (int, float)):
                total_spend += float(spend)
            elif isinstance(spend, str):
                try:
                    total_spend += float(str(spend).replace("$", "").replace(",", ""))
                except Exception:
                    pass
        roi = 0.0
        if total_spend > 0:
            roi = max(
                0.0, min(1.0, total_profit / total_spend)
            )  # normalize into 0..1 by clipping

        # Resource allocation efficiency: correlate spend to outcome (clicks->sales or impressions->units)
        # Use a simple efficiency: sales_count per $100 spend normalized
        units_sold = sum(int(s.get("units_sold", 0)) for s in sales)
        efficiency = 0.0
        if total_spend > 0:
            efficiency = max(
                0.0, min(1.0, (units_sold / max(1.0, total_spend / 100.0)) / 100.0)
            )

        # Strategic decision quality: correlate controller current_priority with approved actions
        # Expect "decisions" entries: {priority: float(0..1), action_type: str, success: bool}
        decisions = data.get("decisions", [])
        if decisions:
            weighted_quality = 0.0
            weight_sum = 0.0
            for d in decisions:
                pr = float(d.get("priority", 0.5))
                success = 1.0 if d.get("success", True) else 0.0
                # Reward when high priority aligns with success, penalize otherwise
                score = (pr * success) + ((1.0 - pr) * (1.0 - success))
                weighted_quality += score
                weight_sum += 1.0
            strategic_decision = (weighted_quality / weight_sum) * 100.0
        else:
            strategic_decision = 0.0

        # Compute remaining sub-scores from helpers (they also expect 0..100 outputs)
        market_trend = self.calculate_market_trend_analysis(data)
        competitive_intelligence = self.calculate_competitive_intelligence(data)
        risk_assessment = self.calculate_risk_assessment(data)
        # ROI optimization and resource allocation incorporate the event-driven aggregates
        roi_optimization = roi * 100.0
        resource_allocation = efficiency * 100.0
        business_outcome = self.calculate_business_outcome_prediction(data)

        weights = {
            "strategic_decision": 0.22,
            "market_trend": 0.14,
            "competitive_intelligence": 0.14,
            "risk_assessment": 0.14,
            "roi_optimization": 0.16,
            "resource_allocation": 0.10,
            "business_outcome": 0.10,
        }
        overall_score = (
            strategic_decision * weights["strategic_decision"]
            + market_trend * weights["market_trend"]
            + competitive_intelligence * weights["competitive_intelligence"]
            + risk_assessment * weights["risk_assessment"]
            + roi_optimization * weights["roi_optimization"]
            + resource_allocation * weights["resource_allocation"]
            + business_outcome * weights["business_outcome"]
        )
        return overall_score

    def calculate_strategic_decision_making(self, data: Dict[str, Any]) -> float:
        """
        Calculate strategic decision-making quality score.

        Args:
            data: Data containing strategic decision-making metrics

        Returns:
            Strategic decision-making score
        """
        decisions = data.get("strategic_decisions", [])
        if not decisions:
            return 0.0

        decision_scores = []

        for decision in decisions:
            # Evaluate decision quality components
            alignment_score = self._evaluate_strategic_alignment(decision)
            timing_score = self._evaluate_decision_timing(decision)
            implementation_score = self._evaluate_implementation_quality(decision)
            outcome_score = self._evaluate_decision_outcome(decision)

            # Calculate weighted decision score
            weights = {
                "alignment": 0.3,
                "timing": 0.2,
                "implementation": 0.2,
                "outcome": 0.3,
            }

            decision_score = (
                alignment_score * weights["alignment"]
                + timing_score * weights["timing"]
                + implementation_score * weights["implementation"]
                + outcome_score * weights["outcome"]
            )

            decision_scores.append(decision_score)

        return statistics.mean(decision_scores) * 100

    def calculate_market_trend_analysis(self, data: Dict[str, Any]) -> float:
        """
        Calculate market trend analysis accuracy score.

        Args:
            data: Data containing market trend analysis metrics

        Returns:
            Market trend analysis score
        """
        trend_analyses = data.get("market_trend_analyses", [])
        if not trend_analyses:
            return 0.0

        trend_scores = []

        for analysis in trend_analyses:
            if isinstance(analysis, dict):
                analysis = MarketTrend(
                    trend_direction=analysis.get("trend_direction", "stable"),
                    trend_strength=analysis.get("trend_strength", 0.0),
                    prediction_accuracy=analysis.get("prediction_accuracy", 0.0),
                    market_volatility=analysis.get("market_volatility", 0.0),
                    time_horizon=analysis.get("time_horizon", "medium"),
                )

            # Evaluate trend analysis components
            direction_accuracy = self._evaluate_trend_direction(analysis)
            strength_accuracy = self._evaluate_trend_strength(analysis)
            volatility_handling = self._evaluate_volatility_handling(analysis)
            horizon_appropriateness = self._evaluate_horizon_appropriateness(analysis)

            # Calculate weighted trend analysis score
            weights = {
                "direction_accuracy": 0.3,
                "strength_accuracy": 0.3,
                "volatility_handling": 0.2,
                "horizon_appropriateness": 0.2,
            }

            trend_score = (
                direction_accuracy * weights["direction_accuracy"]
                + strength_accuracy * weights["strength_accuracy"]
                + volatility_handling * weights["volatility_handling"]
                + horizon_appropriateness * weights["horizon_appropriateness"]
            )

            trend_scores.append(trend_score)

        return statistics.mean(trend_scores) * 100

    def calculate_competitive_intelligence(self, data: Dict[str, Any]) -> float:
        """
        Calculate competitive intelligence capabilities score.

        Args:
            data: Data containing competitive intelligence metrics

        Returns:
            Competitive intelligence score
        """
        competitive_analyses = data.get("competitive_analyses", [])
        if not competitive_analyses:
            return 0.0

        intelligence_scores = []

        for analysis in competitive_analyses:
            if isinstance(analysis, dict):
                analysis = CompetitivePosition(
                    market_share=analysis.get("market_share", 0.0),
                    competitive_advantage=analysis.get("competitive_advantage", 0.0),
                    brand_strength=analysis.get("brand_strength", 0.0),
                    customer_loyalty=analysis.get("customer_loyalty", 0.0),
                    innovation_index=analysis.get("innovation_index", 0.0),
                )

            # Evaluate competitive intelligence components
            market_positioning = self._evaluate_market_positioning(analysis)
            advantage_sustainability = self._evaluate_advantage_sustainability(analysis)
            competitor_analysis = self._evaluate_competitor_analysis(analysis)
            opportunity_identification = self._evaluate_opportunity_identification(
                analysis
            )

            # Calculate weighted intelligence score
            weights = {
                "market_positioning": 0.3,
                "advantage_sustainability": 0.25,
                "competitor_analysis": 0.25,
                "opportunity_identification": 0.2,
            }

            intelligence_score = (
                market_positioning * weights["market_positioning"]
                + advantage_sustainability * weights["advantage_sustainability"]
                + competitor_analysis * weights["competitor_analysis"]
                + opportunity_identification * weights["opportunity_identification"]
            )

            intelligence_scores.append(intelligence_score)

        return statistics.mean(intelligence_scores) * 100

    def calculate_risk_assessment(self, data: Dict[str, Any]) -> float:
        """
        Calculate risk assessment and mitigation effectiveness score.

        Args:
            data: Data containing risk assessment metrics

        Returns:
            Risk assessment score
        """
        risk_assessments = data.get("risk_assessments", [])
        if not risk_assessments:
            return 0.0

        risk_scores = []

        for assessment in risk_assessments:
            if isinstance(assessment, dict):
                assessment = RiskAssessment(
                    risk_level=assessment.get("risk_level", 0.0),
                    risk_categories=assessment.get("risk_categories", {}),
                    mitigation_effectiveness=assessment.get(
                        "mitigation_effectiveness", 0.0
                    ),
                    risk_adjusted_return=assessment.get("risk_adjusted_return", 0.0),
                )

            # Evaluate risk assessment components
            identification_accuracy = self._evaluate_risk_identification(assessment)
            quantification_accuracy = self._evaluate_risk_quantification(assessment)
            mitigation_effectiveness = self._evaluate_mitigation_effectiveness(
                assessment
            )
            risk_return_balance = self._evaluate_risk_return_balance(assessment)

            # Calculate weighted risk assessment score
            weights = {
                "identification_accuracy": 0.25,
                "quantification_accuracy": 0.25,
                "mitigation_effectiveness": 0.3,
                "risk_return_balance": 0.2,
            }

            risk_score = (
                identification_accuracy * weights["identification_accuracy"]
                + quantification_accuracy * weights["quantification_accuracy"]
                + mitigation_effectiveness * weights["mitigation_effectiveness"]
                + risk_return_balance * weights["risk_return_balance"]
            )

            risk_scores.append(risk_score)

        return statistics.mean(risk_scores) * 100

    def calculate_roi_optimization(self, data: Dict[str, Any]) -> float:
        """
        Calculate ROI optimization capabilities score.

        Args:
            data: Data containing ROI optimization metrics

        Returns:
            ROI optimization score
        """
        roi_analyses = data.get("roi_analyses", [])
        if not roi_analyses:
            return 0.0

        roi_scores = []

        for analysis in roi_analyses:
            # Evaluate ROI optimization components
            roi_accuracy = self._evaluate_roi_accuracy(analysis)
            investment_efficiency = self._evaluate_investment_efficiency(analysis)
            return_forecasting = self._evaluate_return_forecasting(analysis)
            optimization_strategies = self._evaluate_optimization_strategies(analysis)

            # Calculate weighted ROI score
            weights = {
                "roi_accuracy": 0.3,
                "investment_efficiency": 0.25,
                "return_forecasting": 0.25,
                "optimization_strategies": 0.2,
            }

            roi_score = (
                roi_accuracy * weights["roi_accuracy"]
                + investment_efficiency * weights["investment_efficiency"]
                + return_forecasting * weights["return_forecasting"]
                + optimization_strategies * weights["optimization_strategies"]
            )

            roi_scores.append(roi_score)

        return statistics.mean(roi_scores) * 100

    def calculate_resource_allocation(self, data: Dict[str, Any]) -> float:
        """
        Calculate resource allocation efficiency score.

        Args:
            data: Data containing resource allocation metrics

        Returns:
            Resource allocation score
        """
        allocation_decisions = data.get("resource_allocation_decisions", [])
        if not allocation_decisions:
            return 0.0

        allocation_scores = []

        for decision in allocation_decisions:
            # Evaluate resource allocation components
            alignment_with_strategy = self._evaluate_resource_alignment(decision)
            utilization_efficiency = self._evaluate_utilization_efficiency(decision)
            flexibility_adaptability = self._evaluate_allocation_flexibility(decision)
            cost_effectiveness = self._evaluate_cost_effectiveness(decision)

            # Calculate weighted allocation score
            weights = {
                "alignment_with_strategy": 0.3,
                "utilization_efficiency": 0.3,
                "flexibility_adaptability": 0.2,
                "cost_effectiveness": 0.2,
            }

            allocation_score = (
                alignment_with_strategy * weights["alignment_with_strategy"]
                + utilization_efficiency * weights["utilization_efficiency"]
                + flexibility_adaptability * weights["flexibility_adaptability"]
                + cost_effectiveness * weights["cost_effectiveness"]
            )

            allocation_scores.append(allocation_score)

        return statistics.mean(allocation_scores) * 100

    def calculate_business_outcome_prediction(self, data: Dict[str, Any]) -> float:
        """
        Calculate business outcome prediction accuracy score.

        Args:
            data: Data containing business outcome prediction metrics

        Returns:
            Business outcome prediction score
        """
        predictions = data.get("business_outcome_predictions", [])
        if not predictions:
            return 0.0

        prediction_scores = []

        for prediction in predictions:
            # Evaluate prediction components
            forecast_accuracy = self._evaluate_forecast_accuracy(prediction)
            uncertainty_handling = self._evaluate_uncertainty_handling(prediction)
            scenario_planning = self._evaluate_scenario_planning(prediction)
            adaptability_to_change = self._evaluate_prediction_adaptability(prediction)

            # Calculate weighted prediction score
            weights = {
                "forecast_accuracy": 0.35,
                "uncertainty_handling": 0.25,
                "scenario_planning": 0.25,
                "adaptability_to_change": 0.15,
            }

            prediction_score = (
                forecast_accuracy * weights["forecast_accuracy"]
                + uncertainty_handling * weights["uncertainty_handling"]
                + scenario_planning * weights["scenario_planning"]
                + adaptability_to_change * weights["adaptability_to_change"]
            )

            prediction_scores.append(prediction_score)

        return statistics.mean(prediction_scores) * 100

    def _evaluate_strategic_alignment(self, decision: Dict[str, Any]) -> float:
        """Evaluate strategic alignment of a decision."""
        business_goals = decision.get("business_goals", [])
        decision_objectives = decision.get("decision_objectives", [])

        if not business_goals or not decision_objectives:
            return 0.0

        # Calculate alignment between business goals and decision objectives
        alignment_score = 0.0
        total_comparisons = 0

        for goal in business_goals:
            for objective in decision_objectives:
                # Simple keyword-based alignment assessment
                goal_words = set(goal.lower().split())
                objective_words = set(objective.lower().split())

                if goal_words & objective_words:  # Common words indicate alignment
                    alignment_score += len(goal_words & objective_words) / len(
                        goal_words | objective_words
                    )
                total_comparisons += 1

        return alignment_score / total_comparisons if total_comparisons > 0 else 0.0

    def _evaluate_decision_timing(self, decision: Dict[str, Any]) -> float:
        """Evaluate timing of a decision."""
        decision_time = decision.get("decision_time", datetime.now())
        optimal_time = decision.get("optimal_time", datetime.now())
        time_window = decision.get("time_window", timedelta(days=30))

        # Calculate how close the decision was to optimal time
        time_diff = abs((decision_time - optimal_time).total_seconds())
        max_diff = time_window.total_seconds()

        timing_score = max(0.0, 1.0 - (time_diff / max_diff))

        return timing_score

    def _evaluate_implementation_quality(self, decision: Dict[str, Any]) -> float:
        """Evaluate implementation quality of a decision."""
        implementation_plan = decision.get("implementation_plan", {})
        actual_implementation = decision.get("actual_implementation", {})

        if not implementation_plan or not actual_implementation:
            return 0.0

        # Compare planned vs actual implementation
        plan_completeness = implementation_plan.get("completeness", 0.0)
        actual_completeness = actual_implementation.get("completeness", 0.0)

        plan_timeline = implementation_plan.get("timeline", 0.0)
        actual_timeline = actual_implementation.get("timeline", 0.0)

        plan_budget = implementation_plan.get("budget", 0.0)
        actual_budget = actual_implementation.get("budget", 0.0)

        # Calculate implementation quality
        completeness_ratio = (
            actual_completeness / plan_completeness if plan_completeness > 0 else 0.0
        )
        timeline_ratio = plan_timeline / actual_timeline if actual_timeline > 0 else 0.0
        budget_ratio = plan_budget / actual_budget if actual_budget > 0 else 0.0

        implementation_score = (
            completeness_ratio + min(1.0, timeline_ratio) + min(1.0, budget_ratio)
        ) / 3.0

        return implementation_score

    def _evaluate_decision_outcome(self, decision: Dict[str, Any]) -> float:
        """Evaluate outcome of a decision."""
        expected_outcomes = decision.get("expected_outcomes", {})
        actual_outcomes = decision.get("actual_outcomes", {})

        if not expected_outcomes or not actual_outcomes:
            return 0.0

        # Compare expected vs actual outcomes
        outcome_scores = []

        for key, expected_value in expected_outcomes.items():
            if key in actual_outcomes:
                actual_value = actual_outcomes[key]

                if isinstance(expected_value, (int, float)) and isinstance(
                    actual_value, (int, float)
                ):
                    # Numerical comparison
                    if expected_value != 0:
                        outcome_score = 1.0 - abs(expected_value - actual_value) / abs(
                            expected_value
                        )
                    else:
                        outcome_score = 1.0 if actual_value == 0 else 0.0
                else:
                    # Categorical comparison
                    outcome_score = 1.0 if expected_value == actual_value else 0.0

                outcome_scores.append(max(0.0, outcome_score))

        return statistics.mean(outcome_scores) if outcome_scores else 0.0

    def _evaluate_trend_direction(self, trend: MarketTrend) -> float:
        """Evaluate trend direction prediction accuracy."""
        predicted_direction = trend.trend_direction  # noqa: F841
        actual_direction = (  # noqa: F841
            trend.trend_direction
        )  # In practice, this would be compared to actual outcome

        # For this implementation, we'll use prediction_accuracy as a proxy
        return trend.prediction_accuracy

    def _evaluate_trend_strength(self, trend: MarketTrend) -> float:
        """Evaluate trend strength prediction accuracy."""
        predicted_strength = trend.trend_strength  # noqa: F841
        actual_strength = (  # noqa: F841
            trend.trend_strength
        )  # In practice, this would be compared to actual outcome

        # For this implementation, we'll use prediction_accuracy as a proxy
        return trend.prediction_accuracy

    def _evaluate_volatility_handling(self, trend: MarketTrend) -> float:
        """Evaluate handling of market volatility."""
        volatility = trend.market_volatility
        prediction_accuracy = trend.prediction_accuracy

        # Higher volatility should not significantly reduce accuracy
        volatility_penalty = min(0.5, volatility * 0.5)
        adjusted_accuracy = prediction_accuracy * (1.0 - volatility_penalty)

        return adjusted_accuracy

    def _evaluate_horizon_appropriateness(self, trend: MarketTrend) -> float:
        """Evaluate appropriateness of time horizon for trend analysis."""
        time_horizon = trend.time_horizon
        prediction_accuracy = trend.prediction_accuracy

        # Different time horizons have different accuracy expectations
        horizon_expectations = {
            "short": 0.9,  # High accuracy expected for short-term
            "medium": 0.7,  # Medium accuracy for medium-term
            "long": 0.5,  # Lower accuracy for long-term
        }

        expected_accuracy = horizon_expectations.get(time_horizon, 0.7)
        appropriateness = min(1.0, prediction_accuracy / expected_accuracy)

        return appropriateness

    def _evaluate_market_positioning(self, position: CompetitivePosition) -> float:
        """Evaluate market positioning analysis."""
        market_share = position.market_share
        competitive_advantage = position.competitive_advantage

        # Good market positioning balances share and advantage
        positioning_score = (market_share + competitive_advantage) / 2.0

        return positioning_score / 100.0  # Normalize to 0-1

    def _evaluate_advantage_sustainability(
        self, position: CompetitivePosition
    ) -> float:
        """Evaluate sustainability of competitive advantage."""
        brand_strength = position.brand_strength
        innovation_index = position.innovation_index
        customer_loyalty = position.customer_loyalty

        # Sustainable advantage requires strong brand, innovation, and loyalty
        sustainability_score = (
            brand_strength + innovation_index + customer_loyalty
        ) / 3.0

        return sustainability_score / 100.0  # Normalize to 0-1

    def _evaluate_competitor_analysis(self, position: CompetitivePosition) -> float:
        """Evaluate competitor analysis quality."""
        # This would typically involve comparing against actual competitor data
        # For this implementation, we'll use a proxy based on market share and advantage
        market_awareness = position.market_share / 100.0
        advantage_awareness = position.competitive_advantage / 100.0

        analysis_score = (market_awareness + advantage_awareness) / 2.0

        return analysis_score

    def _evaluate_opportunity_identification(
        self, position: CompetitivePosition
    ) -> float:
        """Evaluate opportunity identification capability."""
        innovation_index = position.innovation_index
        market_share = position.market_share

        # Opportunity identification is linked to innovation and market understanding
        opportunity_score = (innovation_index + (100.0 - market_share)) / 200.0

        return opportunity_score

    def _evaluate_risk_identification(self, risk: RiskAssessment) -> float:
        """Evaluate risk identification accuracy."""
        risk_categories = risk.risk_categories
        risk_level = risk.risk_level

        # Good risk identification should cover multiple categories
        category_coverage = (
            len(risk_categories) / 10.0
        )  # Assuming 10 major risk categories
        level_appropriateness = 1.0 - abs(
            risk_level - 0.5
        )  # Moderate risk level is often appropriate

        identification_score = (category_coverage + level_appropriateness) / 2.0

        return min(1.0, identification_score)

    def _evaluate_risk_quantification(self, risk: RiskAssessment) -> float:
        """Evaluate risk quantification accuracy."""
        risk_level = risk.risk_level
        risk_categories = risk.risk_categories

        # Risk quantification should be consistent across categories
        if not risk_categories:
            return 0.0

        category_risks = list(risk_categories.values())
        risk_consistency = (
            1.0 - statistics.stdev(category_risks) if len(category_risks) > 1 else 1.0
        )

        quantification_score = (risk_level + risk_consistency) / 2.0

        return quantification_score

    def _evaluate_mitigation_effectiveness(self, risk: RiskAssessment) -> float:
        """Evaluate risk mitigation effectiveness."""
        mitigation_effectiveness = risk.mitigation_effectiveness

        return mitigation_effectiveness / 100.0  # Normalize to 0-1

    def _evaluate_risk_return_balance(self, risk: RiskAssessment) -> float:
        """Evaluate risk-return balance."""
        risk_level = risk.risk_level
        risk_adjusted_return = risk.risk_adjusted_return

        # Good risk-return balance maximizes return for given risk level
        expected_return = risk_level * 2.0  # Simple linear relationship
        balance_score = (
            min(1.0, risk_adjusted_return / expected_return)
            if expected_return > 0
            else 0.0
        )

        return balance_score

    def _evaluate_roi_accuracy(self, analysis: Dict[str, Any]) -> float:
        """Evaluate ROI calculation accuracy."""
        predicted_roi = analysis.get("predicted_roi", 0.0)
        actual_roi = analysis.get("actual_roi", 0.0)

        if predicted_roi == 0:
            return 1.0 if actual_roi == 0 else 0.0

        roi_error = abs(predicted_roi - actual_roi) / abs(predicted_roi)
        roi_accuracy = max(0.0, 1.0 - roi_error)

        return roi_accuracy

    def _evaluate_investment_efficiency(self, analysis: Dict[str, Any]) -> float:
        """Evaluate investment efficiency."""
        investment_amount = analysis.get("investment_amount", 0.0)
        returns = analysis.get("returns", 0.0)

        if investment_amount <= 0:
            return 0.0

        efficiency = returns / investment_amount
        efficiency_score = min(1.0, efficiency / 2.0)  # Normalize to reasonable range

        return efficiency_score

    def _evaluate_return_forecasting(self, analysis: Dict[str, Any]) -> float:
        """Evaluate return forecasting accuracy."""
        forecasted_returns = analysis.get("forecasted_returns", [])
        actual_returns = analysis.get("actual_returns", [])

        if len(forecasted_returns) != len(actual_returns):
            return 0.0

        forecast_errors = []
        for forecasted, actual in zip(forecasted_returns, actual_returns):
            if forecasted != 0:
                error = abs(forecasted - actual) / abs(forecasted)
                forecast_errors.append(error)

        if not forecast_errors:
            return 0.0

        avg_error = statistics.mean(forecast_errors)
        forecasting_accuracy = max(0.0, 1.0 - avg_error)

        return forecasting_accuracy

    def _evaluate_optimization_strategies(self, analysis: Dict[str, Any]) -> float:
        """Evaluate optimization strategies."""
        strategies = analysis.get("optimization_strategies", [])
        strategy_effectiveness = analysis.get("strategy_effectiveness", 0.0)

        if not strategies:
            return 0.0

        # Evaluate based on number and effectiveness of strategies
        strategy_count_score = min(
            1.0, len(strategies) / 5.0
        )  # Normalize by expected number
        effectiveness_score = strategy_effectiveness / 100.0

        optimization_score = (strategy_count_score + effectiveness_score) / 2.0

        return optimization_score

    def _evaluate_resource_alignment(self, decision: Dict[str, Any]) -> float:
        """Evaluate resource alignment with strategy."""
        strategic_priorities = decision.get("strategic_priorities", [])
        resource_allocation = decision.get("resource_allocation", {})

        if not strategic_priorities or not resource_allocation:
            return 0.0

        # Calculate alignment between priorities and allocation
        alignment_score = 0.0
        total_priority_weight = 0.0

        for priority, weight in strategic_priorities:
            total_priority_weight += weight
            if priority in resource_allocation:
                allocation_weight = resource_allocation[priority]
                alignment_score += min(weight, allocation_weight)

        alignment_score = (
            alignment_score / total_priority_weight
            if total_priority_weight > 0
            else 0.0
        )

        return alignment_score

    def _evaluate_utilization_efficiency(self, decision: Dict[str, Any]) -> float:
        """Evaluate resource utilization efficiency."""
        allocated_resources = decision.get("allocated_resources", {})
        utilized_resources = decision.get("utilized_resources", {})

        if not allocated_resources or not utilized_resources:
            return 0.0

        # Calculate utilization efficiency
        utilization_scores = []

        for resource, allocated in allocated_resources.items():
            if resource in utilized_resources:
                utilized = utilized_resources[resource]
                if allocated > 0:
                    utilization = utilized / allocated
                    # Optimal utilization is around 80-90%
                    optimal_utilization = 0.85
                    utilization_score = 1.0 - abs(utilization - optimal_utilization)
                    utilization_scores.append(max(0.0, utilization_score))

        return statistics.mean(utilization_scores) if utilization_scores else 0.0

    def _evaluate_allocation_flexibility(self, decision: Dict[str, Any]) -> float:
        """Evaluate allocation flexibility and adaptability."""
        reallocation_history = decision.get("reallocation_history", [])
        adaptation_events = decision.get("adaptation_events", [])

        # Flexibility is demonstrated by successful reallocations
        successful_reallocations = sum(
            1 for r in reallocation_history if r.get("success", False)
        )
        total_reallocations = len(reallocation_history)

        reallocation_success = (
            successful_reallocations / total_reallocations
            if total_reallocations > 0
            else 0.0
        )

        # Adaptability is demonstrated by handling adaptation events
        successful_adaptations = sum(
            1 for a in adaptation_events if a.get("success", False)
        )
        total_adaptations = len(adaptation_events)

        adaptation_success = (
            successful_adaptations / total_adaptations if total_adaptations > 0 else 0.0
        )

        flexibility_score = (reallocation_success + adaptation_success) / 2.0

        return flexibility_score

    def _evaluate_cost_effectiveness(self, decision: Dict[str, Any]) -> float:
        """Evaluate cost effectiveness of resource allocation."""
        total_cost = decision.get("total_cost", 0.0)
        total_benefit = decision.get("total_benefit", 0.0)

        if total_cost <= 0:
            return 0.0

        cost_effectiveness = total_benefit / total_cost
        effectiveness_score = min(
            1.0, cost_effectiveness / 3.0
        )  # Normalize to reasonable range

        return effectiveness_score

    def _evaluate_forecast_accuracy(self, prediction: Dict[str, Any]) -> float:
        """Evaluate forecast accuracy."""
        predicted_outcomes = prediction.get("predicted_outcomes", {})
        actual_outcomes = prediction.get("actual_outcomes", {})

        if not predicted_outcomes or not actual_outcomes:
            return 0.0

        # Calculate forecast accuracy
        accuracy_scores = []

        for key, predicted_value in predicted_outcomes.items():
            if key in actual_outcomes:
                actual_value = actual_outcomes[key]

                if isinstance(predicted_value, (int, float)) and isinstance(
                    actual_value, (int, float)
                ):
                    if predicted_value != 0:
                        accuracy = 1.0 - abs(predicted_value - actual_value) / abs(
                            predicted_value
                        )
                    else:
                        accuracy = 1.0 if actual_value == 0 else 0.0
                else:
                    accuracy = 1.0 if predicted_value == actual_value else 0.0

                accuracy_scores.append(max(0.0, accuracy))

        return statistics.mean(accuracy_scores) if accuracy_scores else 0.0

    def _evaluate_uncertainty_handling(self, prediction: Dict[str, Any]) -> float:
        """Evaluate handling of uncertainty."""
        confidence_intervals = prediction.get("confidence_intervals", {})
        actual_outcomes = prediction.get("actual_outcomes", {})

        if not confidence_intervals or not actual_outcomes:
            return 0.0

        # Calculate how well confidence intervals captured actual outcomes
        capture_scores = []

        for key, (lower, upper) in confidence_intervals.items():
            if key in actual_outcomes:
                actual_value = actual_outcomes[key]
                if lower <= actual_value <= upper:
                    capture_scores.append(1.0)
                else:
                    # Partial credit for being close
                    if actual_value < lower:
                        distance = lower - actual_value
                        range_width = upper - lower
                        partial_credit = max(0.0, 1.0 - (distance / range_width))
                        capture_scores.append(partial_credit * 0.5)
                    else:  # actual_value > upper
                        distance = actual_value - upper
                        range_width = upper - lower
                        partial_credit = max(0.0, 1.0 - (distance / range_width))
                        capture_scores.append(partial_credit * 0.5)

        return statistics.mean(capture_scores) if capture_scores else 0.0

    def _evaluate_scenario_planning(self, prediction: Dict[str, Any]) -> float:
        """Evaluate scenario planning quality."""
        scenarios = prediction.get("scenarios", [])
        scenario_accuracy = prediction.get("scenario_accuracy", 0.0)

        if not scenarios:
            return 0.0

        # Evaluate based on number of scenarios and their accuracy
        scenario_count_score = min(
            1.0, len(scenarios) / 5.0
        )  # Normalize by expected number
        accuracy_score = scenario_accuracy / 100.0

        planning_score = (scenario_count_score + accuracy_score) / 2.0

        return planning_score

    def _evaluate_prediction_adaptability(self, prediction: Dict[str, Any]) -> float:
        """Evaluate prediction adaptability to changing conditions."""
        adaptation_events = prediction.get("adaptation_events", [])
        prediction_updates = prediction.get("prediction_updates", [])

        if not adaptation_events and not prediction_updates:
            return 0.0

        # Evaluate adaptability based on successful updates
        successful_adaptations = 0
        total_adaptations = 0

        for event in adaptation_events:
            total_adaptations += 1
            if event.get("successful", False):
                successful_adaptations += 1

        for update in prediction_updates:
            total_adaptations += 1
            if update.get("improved_accuracy", False):
                successful_adaptations += 1

        adaptability_score = (
            successful_adaptations / total_adaptations if total_adaptations > 0 else 0.0
        )

        return adaptability_score
