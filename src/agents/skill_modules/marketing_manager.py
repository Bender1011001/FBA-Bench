"""
Marketing Manager Skill Module for FBA-Bench Multi-Domain Agent Architecture.

This module handles advertising and pricing strategy, monitoring competitor prices,
optimizing ad spend, adjusting pricing strategies, and analyzing campaign performance
through LLM-driven decision making.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fba_bench_core.money import Money

from fba_events import BaseEvent
from fba_events.competitor import CompetitorPricesUpdated
from fba_events.pricing import ProductPriceUpdated
from fba_events.sales import SaleOccurred
from fba_events.time_events import TickEvent

from .base_skill import BaseSkill, SkillAction, SkillContext, SkillOutcome

logger = logging.getLogger(__name__)


@dataclass
class MarketingCampaign:
    """
    Marketing campaign configuration and tracking.

    Attributes:
        campaign_id: Unique identifier for the campaign
        campaign_type: Type of campaign (ppc, display, social, etc.)
        target_asin: Product ASIN being promoted
        budget: Campaign budget
        daily_budget: Daily budget limit
        keywords: Target keywords for the campaign
        bid_strategy: Bidding strategy (manual, automatic, target_acos)
        target_acos: Target Advertising Cost of Sales
        start_date: Campaign start date
        end_date: Campaign end date (optional)
        status: Current campaign status
        performance_metrics: Campaign performance data
    """

    campaign_id: str
    campaign_type: str
    target_asin: str
    budget: Money
    daily_budget: Money
    keywords: List[str] = field(default_factory=list)
    bid_strategy: str = "automatic"
    target_acos: float = 0.25  # 25% target ACOS
    start_date: datetime = field(default_factory=datetime.now)
    end_date: Optional[datetime] = None
    status: str = "active"
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PricingAnalysis:
    """
    Pricing analysis for strategic pricing decisions.

    Attributes:
        asin: Product ASIN being analyzed
        current_price: Current selling price
        competitor_avg_price: Average competitor price
        price_elasticity: Estimated price elasticity
        optimal_price: Recommended optimal price
        profit_margin: Current profit margin
        market_position: Position relative to competitors (premium, competitive, value)
        demand_forecast: Predicted demand at current price
        revenue_impact: Expected revenue impact of price change
        recommended_action: Recommended pricing action
    """

    asin: str
    current_price: Money
    competitor_avg_price: Money
    price_elasticity: float
    optimal_price: Money
    profit_margin: float
    market_position: str
    demand_forecast: float
    revenue_impact: Money
    recommended_action: str


@dataclass
class MarketTrend:
    """
    Market trend analysis for strategic decision making.

    Attributes:
        trend_type: Type of trend (price, demand, seasonal, etc.)
        direction: Trend direction (up, down, stable)
        strength: Trend strength (0.0 to 1.0)
        confidence: Confidence in trend analysis (0.0 to 1.0)
        time_horizon: Expected duration of trend
        impact_assessment: Expected impact on business
        recommended_response: Recommended strategic response
    """

    trend_type: str
    direction: str
    strength: float
    confidence: float
    time_horizon: str
    impact_assessment: str
    recommended_response: str


class MarketingManagerSkill(BaseSkill):
    """
    Marketing Manager Skill for advertising and pricing strategy.

    Handles price optimization, advertising campaign management, competitor analysis,
    and market trend assessment to maximize revenue and market share while
    maintaining profitability.
    """

    def __init__(self, agent_id: str, event_bus, config: Dict[str, Any] = None):
        """
        Initialize the Marketing Manager Skill.

        Args:
            agent_id: ID of the agent this skill belongs to
            event_bus: Event bus for communication
            config: Configuration parameters for marketing management
        """
        super().__init__("MarketingManager", agent_id, event_bus)

        # Configuration parameters
        self.config = config or {}
        self.target_profit_margin = self.config.get("target_profit_margin", 0.20)  # 20%
        self.max_advertising_budget = Money(
            self.config.get("max_ad_budget_cents", 200000)
        )  # $2000
        self.price_change_threshold = self.config.get(
            "price_change_threshold", 0.05
        )  # 5%
        self.competitor_response_delay = self.config.get(
            "competitor_response_delay", 2
        )  # ticks

        # Market tracking
        self.competitor_prices: Dict[str, List[Tuple[datetime, Money]]] = {}
        self.price_history: Dict[str, List[Tuple[datetime, Money]]] = {}
        self.sales_performance: Dict[str, List[Tuple[datetime, int, Money]]] = {}

        # Campaign management
        self.active_campaigns: Dict[str, MarketingCampaign] = {}
        self.campaign_performance: Dict[str, Dict[str, float]] = {}
        self.total_ad_spend: Money = Money(0)

        # Market analysis
        self.market_trends: List[MarketTrend] = []
        self.pricing_elasticity: Dict[str, float] = {}
        self.last_pricing_analysis = datetime.now()

        # Performance tracking
        self.successful_campaigns = 0
        self.total_campaign_launches = 0
        self.price_optimization_wins = 0
        self.total_price_changes = 0

        logger.info(f"MarketingManagerSkill initialized for agent {agent_id}")

    async def process_event(self, event: BaseEvent) -> Optional[List[SkillAction]]:
        """
        Process events relevant to marketing and generate actions.

        Args:
            event: Event to process

        Returns:
            List of marketing actions or None
        """
        actions = []

        try:
            if isinstance(event, CompetitorPricesUpdated):
                actions.extend(await self._handle_competitor_prices_updated(event))
            elif isinstance(event, SaleOccurred):
                actions.extend(await self._handle_sale_occurred(event))
            elif isinstance(event, ProductPriceUpdated):
                actions.extend(await self._handle_product_price_updated(event))
            elif isinstance(event, TickEvent):
                actions.extend(await self._handle_tick_event(event))

            # Filter actions by confidence threshold
            confidence_threshold = self.adaptation_parameters.get(
                "confidence_threshold", 0.6
            )
            filtered_actions = [
                action
                for action in actions
                if action.confidence >= confidence_threshold
            ]

            return filtered_actions if filtered_actions else None

        except Exception as e:
            logger.error(f"Error processing event in MarketingManagerSkill: {e}")
            return None

    async def _handle_competitor_prices_updated(
        self, event: CompetitorPricesUpdated
    ) -> List[SkillAction]:
        """Handle competitor price updates for competitive analysis."""
        actions = []

        # Update competitor price tracking
        for competitor in event.competitors:
            asin = competitor.asin
            if asin not in self.competitor_prices:
                self.competitor_prices[asin] = []

            self.competitor_prices[asin].append((datetime.now(), competitor.price))

            # Keep only recent history
            if len(self.competitor_prices[asin]) > 50:
                self.competitor_prices[asin] = self.competitor_prices[asin][-25:]

        # Analyze competitive positioning and potential price adjustments
        pricing_actions = await self._analyze_competitive_pricing()
        actions.extend(pricing_actions)

        # Check if advertising adjustment needed based on competitive landscape
        advertising_actions = await self._analyze_advertising_opportunities(event)
        actions.extend(advertising_actions)

        return actions

    async def _handle_sale_occurred(self, event: SaleOccurred) -> List[SkillAction]:
        """Handle sales events for performance tracking and optimization."""
        actions = []

        # Update sales performance tracking
        asin = event.asin
        if asin not in self.sales_performance:
            self.sales_performance[asin] = []

        self.sales_performance[asin].append(
            (datetime.now(), event.units_sold, event.unit_price)
        )

        # Keep only recent history
        if len(self.sales_performance[asin]) > 100:
            self.sales_performance[asin] = self.sales_performance[asin][-50:]

        # Update price elasticity estimates
        await self._update_price_elasticity(asin)

        # Analyze campaign performance if sale related to active campaigns
        campaign_actions = await self._analyze_campaign_performance(event)
        actions.extend(campaign_actions)

        return actions

    # Learning/adaptation hook: update elasticity and thresholds from outcomes
    async def learn(self, outcome: SkillOutcome) -> None:
        try:
            # Update price elasticity heuristics if sales volume responded to actions
            units = int(outcome.impact_metrics.get("units_sold", 0))
            revenue = float(outcome.impact_metrics.get("revenue", 0.0))
            profit = float(outcome.impact_metrics.get("profit", 0.0))
            roi = float(outcome.impact_metrics.get("roi", 0.0))
            # Simple adaptation: adjust confidence threshold based on ROI and success
            if outcome.success and roi > 0:
                self.adaptation_parameters["confidence_threshold"] = max(
                    0.4,
                    self.adaptation_parameters.get("confidence_threshold", 0.6) * 0.98,
                )
            elif not outcome.success:
                self.adaptation_parameters["confidence_threshold"] = min(
                    0.9,
                    self.adaptation_parameters.get("confidence_threshold", 0.6) * 1.02,
                )
            # Persist a learned insight
            lesson = (
                f"Units={units}, Rev={revenue:.2f}, Profit={profit:.2f}, ROI={roi:.3f}"
            )
            self.update_skill_state(
                SkillOutcome(
                    action_id=outcome.action_id,
                    success=outcome.success,
                    impact_metrics=outcome.impact_metrics,
                    execution_time=outcome.execution_time,
                    resource_cost=outcome.resource_cost,
                    lessons_learned=[lesson],
                    confidence_validation=outcome.confidence_validation,
                )
            )
        except Exception as e:
            logger.warning(f"MarketingManagerSkill.learn failed: {e}")

    async def _handle_product_price_updated(
        self, event: ProductPriceUpdated
    ) -> List[SkillAction]:
        """Handle price updates for tracking and analysis."""
        actions = []

        # Update price history
        asin = event.asin
        if asin not in self.price_history:
            self.price_history[asin] = []

        self.price_history[asin].append((datetime.now(), event.new_price))

        # Keep only recent history
        if len(self.price_history[asin]) > 50:
            self.price_history[asin] = self.price_history[asin][-25:]

        # If this was our price change, track effectiveness
        if event.agent_id == self.agent_id:
            self.total_price_changes += 1
            # Schedule follow-up analysis to measure impact
            actions.append(await self._create_price_impact_analysis_action(event))

        return actions

    async def _handle_tick_event(self, event: TickEvent) -> List[SkillAction]:
        """Handle periodic tick events for regular marketing analysis."""
        actions = []

        # Pricing analysis every few ticks
        if event.tick_number % 3 == 0:
            pricing_actions = await self._periodic_pricing_analysis()
            actions.extend(pricing_actions)

        # Campaign optimization every 5 ticks
        if event.tick_number % 5 == 0:
            campaign_actions = await self._optimize_active_campaigns()
            actions.extend(campaign_actions)

        # Market trend analysis every 10 ticks
        if event.tick_number % 10 == 0:
            trend_actions = await self._analyze_market_trends()
            actions.extend(trend_actions)

        return actions

    async def generate_actions(
        self, context: SkillContext, constraints: Dict[str, Any]
    ) -> List[SkillAction]:
        """
        Generate marketing actions based on current context.

        Args:
            context: Current context information
            constraints: Active constraints and limits

        Returns:
            List of recommended marketing actions
        """
        actions = []

        try:
            # Get budget constraints
            marketing_budget = constraints.get(
                "marketing_budget", self.max_advertising_budget
            )
            if isinstance(marketing_budget, (int, float)):
                marketing_budget = Money(int(marketing_budget))

            # Analyze pricing opportunities
            pricing_actions = await self._generate_pricing_actions(context, constraints)
            actions.extend(pricing_actions)

            # Analyze advertising opportunities
            if marketing_budget.cents > 0:
                advertising_actions = await self._generate_advertising_actions(
                    context, marketing_budget
                )
                actions.extend(advertising_actions)

            # Sort by expected impact and priority
            actions.sort(key=lambda x: x.priority * x.confidence, reverse=True)

            return actions

        except Exception as e:
            logger.error(f"Error generating marketing actions: {e}")
            return []

    def get_priority_score(self, event: BaseEvent) -> float:
        """Calculate priority score for marketing events."""
        if isinstance(event, CompetitorPricesUpdated):
            # High priority for competitive price changes
            return 0.8

        elif isinstance(event, SaleOccurred):
            # Medium-high priority for sales tracking
            return 0.7

        elif isinstance(event, ProductPriceUpdated):
            # Medium priority for price tracking
            return 0.6

        elif isinstance(event, TickEvent):
            # Lower priority for routine analysis
            return 0.3

        return 0.2

    async def _analyze_competitive_pricing(self) -> List[SkillAction]:
        """Analyze competitive landscape and suggest pricing adjustments."""
        actions = []

        for asin, competitor_history in self.competitor_prices.items():
            if len(competitor_history) < 2:
                continue

            try:
                # Calculate current competitive position
                recent_prices = [price for _, price in competitor_history[-5:]]
                avg_competitor_price = Money(
                    sum(p.cents for p in recent_prices) // len(recent_prices)
                )

                # Get our current price if available
                current_price = None
                if self.price_history.get(asin):
                    current_price = self.price_history[asin][-1][1]

                if current_price:
                    analysis = await self._create_pricing_analysis(
                        asin, current_price, avg_competitor_price
                    )
                    if analysis and analysis.recommended_action != "maintain":
                        action = await self._create_pricing_action(analysis)
                        if action:
                            actions.append(action)

            except Exception as e:
                logger.error(f"Error analyzing competitive pricing for {asin}: {e}")

        return actions

    async def _create_pricing_analysis(
        self, asin: str, current_price: Money, competitor_avg: Money
    ) -> Optional[PricingAnalysis]:
        """Create detailed pricing analysis for decision making."""
        try:
            # Calculate price difference
            price_diff_pct = (
                current_price.cents - competitor_avg.cents
            ) / competitor_avg.cents

            # Estimate price elasticity (simplified)
            elasticity = self.pricing_elasticity.get(asin, -1.5)  # Default elasticity

            # Calculate optimal price (simplified optimization)
            cost_estimate = Money(int(current_price.cents * 0.7))  # Assume 30% margin
            optimal_markup = 1.0 / (1.0 + (1.0 / abs(elasticity)))
            optimal_price = Money(int(cost_estimate.cents / optimal_markup))

            # Determine market position
            if price_diff_pct > 0.1:
                position = "premium"
            elif price_diff_pct < -0.1:
                position = "value"
            else:
                position = "competitive"

            # Calculate profit margin
            profit_margin = (
                current_price.cents - cost_estimate.cents
            ) / current_price.cents

            # Determine recommended action
            if abs(price_diff_pct) > self.price_change_threshold:
                if price_diff_pct > 0.2:  # Too expensive
                    recommended_action = "decrease_price"
                elif price_diff_pct < -0.2:  # Too cheap
                    recommended_action = "increase_price"
                else:
                    recommended_action = "adjust_price"
            else:
                recommended_action = "maintain"

            # Estimate revenue impact
            demand_change = (
                elasticity
                * (optimal_price.cents - current_price.cents)
                / current_price.cents
            )
            revenue_impact = Money(
                int(current_price.cents * demand_change * 0.1)
            )  # Simplified

            return PricingAnalysis(
                asin=asin,
                current_price=current_price,
                competitor_avg_price=competitor_avg,
                price_elasticity=elasticity,
                optimal_price=optimal_price,
                profit_margin=profit_margin,
                market_position=position,
                demand_forecast=1.0 + demand_change,
                revenue_impact=revenue_impact,
                recommended_action=recommended_action,
            )

        except Exception as e:
            logger.error(f"Error creating pricing analysis: {e}")
            return None

    async def _create_pricing_action(
        self, analysis: PricingAnalysis
    ) -> Optional[SkillAction]:
        """Create pricing action based on analysis."""
        try:
            # Calculate confidence based on data quality and market conditions
            confidence = self._calculate_pricing_confidence(analysis)

            # Determine priority based on potential impact
            priority = min(
                0.9, abs(analysis.revenue_impact.cents) / 100000.0
            )  # Higher for larger impact

            # Determine new price based on recommendation
            if analysis.recommended_action == "increase_price":
                new_price = Money(
                    min(
                        analysis.optimal_price.cents,
                        int(analysis.current_price.cents * 1.1),  # Max 10% increase
                    )
                )
            elif analysis.recommended_action == "decrease_price":
                new_price = Money(
                    max(
                        analysis.optimal_price.cents,
                        int(analysis.current_price.cents * 0.9),  # Max 10% decrease
                    )
                )
            else:  # adjust_price
                new_price = analysis.optimal_price

            reasoning = (
                f"Pricing optimization for {analysis.asin}: current ${analysis.current_price.to_float():.2f}, "
                f"competitor avg ${analysis.competitor_avg_price.to_float():.2f}, "
                f"position: {analysis.market_position}. Expected revenue impact: ${analysis.revenue_impact.to_float():.2f}"
            )

            return SkillAction(
                action_type="set_price",
                parameters={
                    "asin": analysis.asin,
                    "price": new_price.to_float(),
                    "reasoning": analysis.recommended_action,
                    "market_position": analysis.market_position,
                },
                confidence=confidence,
                reasoning=reasoning,
                priority=priority,
                resource_requirements={"pricing_authority": True},
                expected_outcome={
                    "price_change": new_price.to_float()
                    - analysis.current_price.to_float(),
                    "demand_impact": analysis.demand_forecast - 1.0,
                    "revenue_impact": analysis.revenue_impact.cents,
                },
                skill_source=self.skill_name,
            )

        except Exception as e:
            logger.error(f"Error creating pricing action: {e}")
            return None

    async def _analyze_advertising_opportunities(
        self, event: CompetitorPricesUpdated
    ) -> List[SkillAction]:
        """Analyze advertising opportunities based on competitive landscape."""
        actions = []

        # Check if competitor price changes create advertising opportunities
        for competitor in event.competitors:
            # If competitor raised prices significantly, opportunity for increased advertising
            if len(self.competitor_prices.get(competitor.asin, [])) >= 2:
                recent_prices = [
                    p[1] for p in self.competitor_prices[competitor.asin][-2:]
                ]
                if len(recent_prices) == 2:
                    price_increase_pct = (
                        recent_prices[1].cents - recent_prices[0].cents
                    ) / recent_prices[0].cents
                    if price_increase_pct > 0.1:  # 10% increase
                        action = await self._create_advertising_opportunity_action(
                            competitor.asin, price_increase_pct
                        )
                        if action:
                            actions.append(action)

        return actions

    async def _create_advertising_opportunity_action(
        self, asin: str, opportunity_strength: float
    ) -> Optional[SkillAction]:
        """Create advertising action based on competitive opportunity."""
        try:
            # Calculate campaign budget based on opportunity strength
            base_budget = min(
                self.max_advertising_budget.cents // 10, 50000
            )  # Max $500
            campaign_budget = Money(int(base_budget * (1 + opportunity_strength)))

            # Generate campaign parameters
            campaign_id = f"competitive_response_{asin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            reasoning = (
                f"Competitive opportunity detected for {asin}: competitor price increase of "
                f"{opportunity_strength:.1%} creates advertising advantage"
            )

            return SkillAction(
                action_type="run_marketing_campaign",
                parameters={
                    "campaign_id": campaign_id,
                    "campaign_type": "competitive_response",
                    "target_asin": asin,
                    "budget": campaign_budget.cents,
                    "duration_days": 7,
                    "bid_strategy": "aggressive",
                    "target_acos": 0.2,  # 20% target ACOS
                    "keywords": ["competitive", "price", "value"],
                },
                confidence=0.7 + min(0.2, opportunity_strength),
                reasoning=reasoning,
                priority=0.6 + min(0.3, opportunity_strength),
                resource_requirements={
                    "budget": campaign_budget.cents,
                    "campaign_slots": 1,
                },
                expected_outcome={
                    "sales_lift": opportunity_strength * 0.5,
                    "market_share_gain": opportunity_strength * 0.3,
                    "roi_estimate": 2.0 + opportunity_strength,
                },
                skill_source=self.skill_name,
            )

        except Exception as e:
            logger.error(f"Error creating advertising opportunity action: {e}")
            return None

    async def _periodic_pricing_analysis(self) -> List[SkillAction]:
        """Perform periodic pricing analysis and optimization."""
        actions = []

        # Analyze all products we have pricing data for
        for asin in self.price_history.keys():
            if self.competitor_prices.get(asin):
                current_price = self.price_history[asin][-1][1]
                recent_competitor_prices = [
                    p[1] for p in self.competitor_prices[asin][-3:]
                ]
                avg_competitor_price = Money(
                    sum(p.cents for p in recent_competitor_prices)
                    // len(recent_competitor_prices)
                )

                analysis = await self._create_pricing_analysis(
                    asin, current_price, avg_competitor_price
                )
                if analysis and analysis.recommended_action != "maintain":
                    action = await self._create_pricing_action(analysis)
                    if action:
                        actions.append(action)

        return actions

    async def _optimize_active_campaigns(self) -> List[SkillAction]:
        """Optimize active advertising campaigns based on performance."""
        actions = []

        for campaign_id, campaign in self.active_campaigns.items():
            performance = self.campaign_performance.get(campaign_id, {})

            # Analyze campaign performance and suggest optimizations
            optimization_action = await self._create_campaign_optimization_action(
                campaign, performance
            )
            if optimization_action:
                actions.append(optimization_action)

        return actions

    async def _create_campaign_optimization_action(
        self, campaign: MarketingCampaign, performance: Dict[str, float]
    ) -> Optional[SkillAction]:
        """Create campaign optimization action based on performance."""
        try:
            current_acos = performance.get("acos", 0.3)
            current_roas = performance.get("roas", 2.0)

            # Determine optimization needed
            if current_acos > campaign.target_acos * 1.2:  # ACOS too high
                action_type = "reduce_campaign_spend"
                adjustment = -0.2  # Reduce by 20%
                reasoning = f"Campaign {campaign.campaign_id} ACOS too high: {current_acos:.1%} vs target {campaign.target_acos:.1%}"
            elif (
                current_acos < campaign.target_acos * 0.8 and current_roas > 3.0
            ):  # Great performance, scale up
                action_type = "increase_campaign_spend"
                adjustment = 0.3  # Increase by 30%
                reasoning = f"Campaign {campaign.campaign_id} performing well: ACOS {current_acos:.1%}, ROAS {current_roas:.1f}"
            else:
                return None  # No optimization needed

            new_budget = Money(int(campaign.daily_budget.cents * (1 + adjustment)))

            return SkillAction(
                action_type=action_type,
                parameters={
                    "campaign_id": campaign.campaign_id,
                    "new_daily_budget": new_budget.cents,
                    "adjustment_percentage": adjustment,
                    "reason": reasoning,
                },
                confidence=0.8,
                reasoning=reasoning,
                priority=0.6,
                resource_requirements={
                    "budget_change": abs(adjustment) * campaign.daily_budget.cents
                },
                expected_outcome={
                    "acos_improvement": (campaign.target_acos - current_acos) * 0.5,
                    "performance_optimization": abs(adjustment),
                },
                skill_source=self.skill_name,
            )

        except Exception as e:
            logger.error(f"Error creating campaign optimization action: {e}")
            return None

    def _calculate_pricing_confidence(self, analysis: PricingAnalysis) -> float:
        """Calculate confidence score for pricing decisions."""
        base_confidence = 0.7

        # Adjust based on data quality
        data_quality = (
            0.9 if len(self.price_history.get(analysis.asin, [])) > 10 else 0.6
        )

        # Adjust based on market volatility
        volatility_penalty = (
            abs(analysis.price_elasticity + 1.0) * 0.1
        )  # Closer to -1.0 is more stable

        # Adjust based on profit margin safety
        margin_confidence = min(1.0, analysis.profit_margin / self.target_profit_margin)

        confidence = (
            base_confidence * data_quality * margin_confidence - volatility_penalty
        )
        return max(0.3, min(0.95, confidence))

    async def _update_price_elasticity(self, asin: str):
        """Update price elasticity estimates based on sales data."""
        if asin not in self.sales_performance or len(self.sales_performance[asin]) < 3:
            return

        try:
            # Simple elasticity calculation using recent data points
            recent_sales = self.sales_performance[asin][-3:]
            if len(recent_sales) >= 2:
                # Calculate price and quantity changes
                price_changes = []
                quantity_changes = []

                for i in range(1, len(recent_sales)):
                    prev_sale = recent_sales[i - 1]
                    curr_sale = recent_sales[i]

                    price_change = (
                        curr_sale[2].cents - prev_sale[2].cents
                    ) / prev_sale[2].cents
                    qty_change = (curr_sale[1] - prev_sale[1]) / max(prev_sale[1], 1)

                    if abs(price_change) > 0.01:  # Only if significant price change
                        price_changes.append(price_change)
                        quantity_changes.append(qty_change)

                if price_changes and quantity_changes:
                    # Simple elasticity estimate
                    avg_price_change = sum(price_changes) / len(price_changes)
                    avg_qty_change = sum(quantity_changes) / len(quantity_changes)

                    if abs(avg_price_change) > 0.001:
                        elasticity = avg_qty_change / avg_price_change
                        # Smooth with existing estimate
                        if asin in self.pricing_elasticity:
                            self.pricing_elasticity[asin] = (
                                self.pricing_elasticity[asin] * 0.7
                            ) + (elasticity * 0.3)
                        else:
                            self.pricing_elasticity[asin] = elasticity

                        logger.debug(
                            f"Updated price elasticity for {asin}: {self.pricing_elasticity[asin]:.2f}"
                        )

        except Exception as e:
            logger.error(f"Error updating price elasticity for {asin}: {e}")

    async def _analyze_market_trends(self) -> List[SkillAction]:
        """Analyze market trends and suggest strategic responses."""
        actions = []

        # Analyze pricing trends across all tracked products
        trends = await self._identify_market_trends()
        self.market_trends = trends

        # Generate actions based on identified trends
        for trend in trends:
            if trend.confidence > 0.7 and trend.strength > 0.5:
                trend_action = await self._create_trend_response_action(trend)
                if trend_action:
                    actions.append(trend_action)

        return actions

    async def _identify_market_trends(self) -> List[MarketTrend]:
        """Identify current market trends from historical data."""
        trends = []

        try:
            # Analyze price trends
            if self.competitor_prices:
                all_recent_prices = []
                for asin, price_history in self.competitor_prices.items():
                    if len(price_history) >= 5:
                        recent_prices = [p[1].cents for p in price_history[-5:]]
                        all_recent_prices.extend(recent_prices)

                if len(all_recent_prices) >= 10:
                    # Simple trend analysis
                    first_half = all_recent_prices[: len(all_recent_prices) // 2]
                    second_half = all_recent_prices[len(all_recent_prices) // 2 :]

                    avg_first = sum(first_half) / len(first_half)
                    avg_second = sum(second_half) / len(second_half)

                    price_change = (avg_second - avg_first) / avg_first

                    if abs(price_change) > 0.05:  # 5% change
                        direction = "up" if price_change > 0 else "down"
                        strength = min(1.0, abs(price_change) * 10)  # Scale to 0-1

                        trend = MarketTrend(
                            trend_type="price",
                            direction=direction,
                            strength=strength,
                            confidence=0.8,
                            time_horizon="short_term",
                            impact_assessment=f"Market prices trending {direction} by {abs(price_change):.1%}",
                            recommended_response=(
                                "adjust_pricing_strategy"
                                if strength > 0.7
                                else "monitor"
                            ),
                        )
                        trends.append(trend)

        except Exception as e:
            logger.error(f"Error identifying market trends: {e}")

        return trends

    async def _create_trend_response_action(
        self, trend: MarketTrend
    ) -> Optional[SkillAction]:
        """Create action to respond to identified market trend."""
        try:
            if (
                trend.trend_type == "price"
                and trend.recommended_response == "adjust_pricing_strategy"
            ):
                # Create strategic pricing adjustment
                return SkillAction(
                    action_type="adjust_pricing_strategy",
                    parameters={
                        "trend_direction": trend.direction,
                        "trend_strength": trend.strength,
                        "adjustment_magnitude": min(0.1, trend.strength * 0.2),
                        "time_horizon": trend.time_horizon,
                    },
                    confidence=trend.confidence,
                    reasoning=f"Market trend response: {trend.impact_assessment}",
                    priority=0.7,
                    resource_requirements={"strategic_authority": True},
                    expected_outcome={
                        "competitive_positioning": trend.strength,
                        "trend_adaptation": trend.confidence,
                    },
                    skill_source=self.skill_name,
                )

        except Exception as e:
            logger.error(f"Error creating trend response action: {e}")

        return None

    async def _generate_pricing_actions(
        self, context: SkillContext, constraints: Dict[str, Any]
    ) -> List[SkillAction]:
        """Generate pricing-related actions based on context."""
        actions = []

        # Use current agent state to determine products to analyze
        target_asins = context.agent_state.get("target_asins", [])

        for asin in target_asins:
            if asin in self.price_history and asin in self.competitor_prices:
                current_price = self.price_history[asin][-1][1]
                recent_competitor_prices = [
                    p[1] for p in self.competitor_prices[asin][-3:]
                ]
                if recent_competitor_prices:
                    avg_competitor_price = Money(
                        sum(p.cents for p in recent_competitor_prices)
                        // len(recent_competitor_prices)
                    )

                    analysis = await self._create_pricing_analysis(
                        asin, current_price, avg_competitor_price
                    )
                    if analysis and analysis.recommended_action != "maintain":
                        action = await self._create_pricing_action(analysis)
                        if action:
                            actions.append(action)

        return actions

    async def _generate_advertising_actions(
        self, context: SkillContext, budget: Money
    ) -> List[SkillAction]:
        """Generate advertising-related actions based on context and budget."""
        actions = []

        # Check for underperforming products that might benefit from advertising
        target_asins = context.agent_state.get("target_asins", [])

        remaining_budget = budget
        for asin in target_asins:
            if remaining_budget.cents < 10000:  # Less than $100 remaining
                break

            # Check if product needs advertising boost
            if asin in self.sales_performance:
                recent_sales = self.sales_performance[asin][-5:]
                if recent_sales:
                    avg_daily_sales = sum(sale[1] for sale in recent_sales) / len(
                        recent_sales
                    )
                    if avg_daily_sales < 5:  # Low sales volume
                        campaign_budget = Money(
                            min(remaining_budget.cents // 2, 50000)
                        )  # Max $500 per campaign

                        campaign_action = (
                            await self._create_advertising_campaign_action(
                                asin, campaign_budget
                            )
                        )
                        if campaign_action:
                            actions.append(campaign_action)
                            remaining_budget = Money(
                                remaining_budget.cents - campaign_budget.cents
                            )

        return actions

    async def _create_advertising_campaign_action(
        self, asin: str, budget: Money
    ) -> Optional[SkillAction]:
        """Create advertising campaign action for specific product."""
        try:
            campaign_id = (
                f"performance_boost_{asin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

            return SkillAction(
                action_type="run_marketing_campaign",
                parameters={
                    "campaign_id": campaign_id,
                    "campaign_type": "performance_boost",
                    "target_asin": asin,
                    "budget": budget.cents,
                    "duration_days": 14,
                    "bid_strategy": "target_acos",
                    "target_acos": 0.25,
                    "keywords": ["product", "quality", "bestseller"],
                },
                confidence=0.7,
                reasoning=f"Performance boost campaign for underperforming product {asin}",
                priority=0.5,
                resource_requirements={"budget": budget.cents, "campaign_slots": 1},
                expected_outcome={
                    "sales_lift": 0.3,
                    "visibility_increase": 0.4,
                    "roi_estimate": 2.5,
                },
                skill_source=self.skill_name,
            )

        except Exception as e:
            logger.error(f"Error creating advertising campaign action: {e}")
            return None

    async def _create_price_impact_analysis_action(
        self, event: ProductPriceUpdated
    ) -> SkillAction:
        """Create action to analyze price change impact."""
        return SkillAction(
            action_type="analyze_price_impact",
            parameters={
                "asin": event.asin,
                "price_change": event.new_price.cents - event.previous_price.cents,
                "analysis_period": 7,  # days to monitor impact
            },
            confidence=0.9,
            reasoning=f"Schedule price impact analysis for {event.asin} price change",
            priority=0.4,
            resource_requirements={},
            expected_outcome={"elasticity_update": True, "performance_insight": True},
            skill_source=self.skill_name,
        )

    async def _analyze_campaign_performance(
        self, event: SaleOccurred
    ) -> List[SkillAction]:
        """Analyze if sale was influenced by active campaigns."""
        actions = []

        # Check if any active campaigns target this ASIN
        relevant_campaigns = [
            c for c in self.active_campaigns.values() if c.target_asin == event.asin
        ]

        for campaign in relevant_campaigns:
            # Update campaign performance metrics (simplified)
            if campaign.campaign_id not in self.campaign_performance:
                self.campaign_performance[campaign.campaign_id] = {}

            # Simple attribution - assume sale was influenced by campaign
            self.campaign_performance[campaign.campaign_id]["attributed_sales"] = (
                self.campaign_performance[campaign.campaign_id].get(
                    "attributed_sales", 0
                )
                + event.units_sold
            )

            logger.debug(
                f"Updated campaign {campaign.campaign_id} performance with {event.units_sold} attributed sales"
            )

        return actions

    async def optimize_ad_spend(self) -> Dict[str, Any]:
        """Optimize advertising spend across all campaigns."""
        optimization_results = {}

        for campaign_id, campaign in self.active_campaigns.items():
            performance = self.campaign_performance.get(campaign_id, {})
            current_acos = performance.get("acos", 0.3)

            if current_acos > campaign.target_acos * 1.1:
                # Reduce spend
                optimization_results[campaign_id] = {
                    "action": "reduce_spend",
                    "new_budget": campaign.daily_budget.cents * 0.8,
                    "reason": "ACOS too high",
                }
            elif current_acos < campaign.target_acos * 0.8:
                # Increase spend
                optimization_results[campaign_id] = {
                    "action": "increase_spend",
                    "new_budget": campaign.daily_budget.cents * 1.2,
                    "reason": "Good performance, scale up",
                }

        return optimization_results

    async def adjust_pricing_strategy(
        self, market_conditions: Dict[str, Any]
    ) -> Dict[str, Money]:
        """Adjust pricing strategy based on market conditions."""
        price_adjustments = {}

        for asin in self.price_history.keys():
            if asin in self.competitor_prices:
                current_price = self.price_history[asin][-1][1]
                competitor_avg = Money(
                    sum(p[1].cents for p in self.competitor_prices[asin][-3:]) // 3
                )

                analysis = await self._create_pricing_analysis(
                    asin, current_price, competitor_avg
                )
                if analysis and analysis.recommended_action != "maintain":
                    price_adjustments[asin] = analysis.optimal_price

        return price_adjustments

    async def analyze_campaign_performance(self) -> Dict[str, Dict[str, float]]:
        """Analyze performance of all active campaigns."""
        performance_analysis = {}

        for campaign_id, campaign in self.active_campaigns.items():
            performance = self.campaign_performance.get(campaign_id, {})

            performance_analysis[campaign_id] = {
                "acos": performance.get("acos", 0.0),
                "roas": performance.get("roas", 0.0),
                "ctr": performance.get("ctr", 0.0),
                "conversion_rate": performance.get("conversion_rate", 0.0),
                "attributed_sales": performance.get("attributed_sales", 0),
                "spend": performance.get("spend", 0.0),
            }

        return performance_analysis


# Alias for backward compatibility
MarketingManager = MarketingManagerSkill
