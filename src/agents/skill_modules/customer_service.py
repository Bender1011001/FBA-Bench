"""
Customer Service Skill Module for FBA-Bench Multi-Domain Agent Architecture.

This module handles customer interactions and satisfaction, monitoring customer messages,
managing negative reviews and complaints, drafting responses, escalating issues,
and tracking satisfaction metrics through LLM-driven decision making.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from fba_events.base import BaseEvent
from fba_events.sales import SaleOccurred
from fba_events.time_events import TickEvent

from .base_skill import BaseSkill, SkillAction, SkillContext

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """Priority levels for customer messages."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class MessageType(Enum):
    """Types of customer messages."""

    INQUIRY = "inquiry"
    COMPLAINT = "complaint"
    RETURN_REQUEST = "return_request"
    REVIEW = "review"
    FEEDBACK = "feedback"
    TECHNICAL_ISSUE = "technical_issue"


@dataclass
class CustomerMessage:
    """
    Customer message requiring response and handling.

    Attributes:
        message_id: Unique identifier for the message
        customer_id: Customer identifier
        asin: Product ASIN related to the message
        message_type: Type of message (inquiry, complaint, etc.)
        priority: Message priority level
        content: Message content/text
        sentiment: Sentiment analysis score (-1.0 to 1.0)
        received_at: When the message was received
        response_deadline: When response is due
        tags: Categories/tags for the message
        customer_history: Previous interactions with this customer
    """

    message_id: str
    customer_id: str
    asin: str
    message_type: MessageType
    priority: MessagePriority
    content: str
    sentiment: float = 0.0
    received_at: datetime = field(default_factory=datetime.now)
    response_deadline: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    customer_history: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CustomerReview:
    """
    Customer review requiring monitoring and potential response.

    Attributes:
        review_id: Unique review identifier
        customer_id: Customer who wrote the review
        asin: Product being reviewed
        rating: Star rating (1-5)
        title: Review title
        content: Review content
        verified_purchase: Whether customer verified purchase
        sentiment: Sentiment analysis score
        review_date: When review was posted
        helpful_votes: Number of helpful votes
        requires_response: Whether review needs response
        impact_score: Potential impact on sales/reputation
    """

    review_id: str
    customer_id: str
    asin: str
    rating: int
    title: str
    content: str
    verified_purchase: bool = True
    sentiment: float = 0.0
    review_date: datetime = field(default_factory=datetime.now)
    helpful_votes: int = 0
    requires_response: bool = False
    impact_score: float = 0.0


@dataclass
class CustomerSatisfactionMetrics:
    """
    Customer satisfaction tracking and analysis.

    Attributes:
        period_start: Start of measurement period
        period_end: End of measurement period
        total_interactions: Total customer interactions
        average_response_time: Average response time in hours
        satisfaction_score: Overall satisfaction score (0.0 to 1.0)
        resolution_rate: Percentage of issues resolved
        escalation_rate: Percentage of issues escalated
        positive_reviews: Number of positive reviews
        negative_reviews: Number of negative reviews
        return_rate: Product return rate
        repeat_customer_rate: Rate of repeat customers
    """

    period_start: datetime
    period_end: datetime
    total_interactions: int = 0
    average_response_time: float = 0.0
    satisfaction_score: float = 0.0
    resolution_rate: float = 0.0
    escalation_rate: float = 0.0
    positive_reviews: int = 0
    negative_reviews: int = 0
    return_rate: float = 0.0
    repeat_customer_rate: float = 0.0


class CustomerServiceSkill(BaseSkill):
    """
    Customer Service Skill for customer interaction and satisfaction management.

    Handles customer message processing, review monitoring, response generation,
    issue escalation, and satisfaction tracking to maintain high service levels
    and protect brand reputation.
    """

    def __init__(self, agent_id: str, event_bus, config: Dict[str, Any] = None):
        """
        Initialize the Customer Service Skill.

        Args:
            agent_id: ID of the agent this skill belongs to
            event_bus: Event bus for communication
            config: Configuration parameters for customer service
        """
        super().__init__("CustomerService", agent_id, event_bus)

        # Configuration parameters
        self.config = config or {}
        self.response_time_target = self.config.get(
            "response_time_hours", 12
        )  # 12 hours
        self.satisfaction_target = self.config.get("satisfaction_target", 0.85)  # 85%
        self.escalation_threshold = self.config.get(
            "escalation_threshold", 0.3
        )  # 30% negative sentiment
        self.auto_response_enabled = self.config.get("auto_response_enabled", True)

        # Message and review queues
        self.pending_messages: Dict[str, CustomerMessage] = {}
        self.pending_reviews: Dict[str, CustomerReview] = {}
        self.escalated_issues: Dict[str, Dict[str, Any]] = {}

        # Customer tracking
        self.customer_profiles: Dict[str, Dict[str, Any]] = {}
        self.interaction_history: List[Dict[str, Any]] = []
        self.satisfaction_metrics: List[CustomerSatisfactionMetrics] = []

        # Performance tracking
        self.total_messages_handled = 0
        self.total_reviews_responded = 0
        self.average_response_time = 0.0
        self.escalation_count = 0
        self.satisfaction_scores: List[float] = []

        # Response templates and knowledge base
        self.response_templates = self._initialize_response_templates()
        self.knowledge_base = self._initialize_knowledge_base()

        logger.info(f"CustomerServiceSkill initialized for agent {agent_id}")

    def _initialize_response_templates(self) -> Dict[str, str]:
        """Initialize response templates for common customer interactions."""
        return {
            "inquiry_general": "Thank you for your inquiry. We're happy to help! {specific_response}",
            "complaint_acknowledgment": "We sincerely apologize for the inconvenience. We take all feedback seriously and are working to resolve this issue.",
            "return_process": "We understand you'd like to return your item. Here's how to proceed: {return_instructions}",
            "technical_support": "We're sorry you're experiencing technical difficulties. Let us help you troubleshoot: {troubleshooting_steps}",
            "review_response_positive": "Thank you so much for your positive review! We're thrilled you're happy with your purchase.",
            "review_response_negative": "Thank you for your feedback. We're sorry your experience didn't meet expectations. We'd like to make this right: {resolution_offer}",
            "escalation_notice": "We've escalated your issue to our specialist team for priority handling. You'll hear from us within {timeframe}.",
        }

    def _initialize_knowledge_base(self) -> Dict[str, Any]:
        """Initialize knowledge base for customer service information."""
        return {
            "return_policy": {
                "window_days": 30,
                "condition_requirements": "unused, original packaging",
                "process": "contact support, receive return label, ship item",
            },
            "shipping_info": {
                "standard_delivery": "5-7 business days",
                "expedited_delivery": "2-3 business days",
                "tracking_available": True,
            },
            "product_support": {
                "warranty_period": "1 year",
                "technical_support_hours": "9 AM - 6 PM EST",
                "common_issues": ["setup", "connectivity", "performance"],
            },
            "contact_options": {
                "email": "support@company.com",
                "phone": "1-800-SUPPORT",
                "chat": "available on website",
            },
        }

    async def process_event(self, event: BaseEvent) -> Optional[List[SkillAction]]:
        """
        Process events relevant to customer service and generate actions.

        Args:
            event: Event to process

        Returns:
            List of customer service actions or None
        """
        actions = []

        try:
            # Note: In a real implementation, there would be specific event types
            # like CustomerMessageReceived, NegativeReviewEvent, ComplaintEvent
            # For now, we'll simulate based on available events

            if isinstance(event, SaleOccurred):
                actions.extend(await self._handle_sale_occurred(event))
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
            logger.error(f"Error processing event in CustomerServiceSkill: {e}")
            return None

    async def _handle_sale_occurred(self, event: SaleOccurred) -> List[SkillAction]:
        """Handle sales events to proactively engage with customers."""
        actions = []

        # Proactive customer engagement for high-value sales
        if event.total_revenue.cents > 10000:  # $100+ order
            follow_up_action = await self._create_proactive_follow_up_action(event)
            if follow_up_action:
                actions.append(follow_up_action)

        # Check for potential issues based on trust score
        if event.trust_score_at_sale < 0.7:
            prevention_action = await self._create_issue_prevention_action(event)
            if prevention_action:
                actions.append(prevention_action)

        return actions

    async def _handle_tick_event(self, event: TickEvent) -> List[SkillAction]:
        """Handle periodic tick events for customer service monitoring."""
        actions = []

        # Process pending messages every tick
        message_actions = await self._process_pending_messages()
        actions.extend(message_actions)

        # Review monitoring every few ticks
        if event.tick_number % 3 == 0:
            review_actions = await self._monitor_reviews()
            actions.extend(review_actions)

        # Satisfaction analysis every 5 ticks
        if event.tick_number % 5 == 0:
            satisfaction_actions = await self._analyze_satisfaction_metrics()
            actions.extend(satisfaction_actions)

        # Generate synthetic customer interactions for testing
        if event.tick_number % 7 == 0:
            synthetic_actions = await self._generate_synthetic_interactions(event)
            actions.extend(synthetic_actions)

        return actions

    async def generate_actions(
        self, context: SkillContext, constraints: Dict[str, Any]
    ) -> List[SkillAction]:
        """
        Generate customer service actions based on current context.

        Args:
            context: Current context information
            constraints: Active constraints and limits

        Returns:
            List of recommended customer service actions
        """
        actions = []

        try:
            # Get resource constraints
            response_capacity = constraints.get(
                "response_capacity", 10
            )  # Max responses per period
            escalation_budget = constraints.get(
                "escalation_budget", 5
            )  # Max escalations

            # Process high-priority messages first
            priority_actions = await self._process_priority_messages(response_capacity)
            actions.extend(priority_actions)

            # Handle reviews requiring response
            review_actions = await self._generate_review_responses(
                response_capacity - len(actions)
            )
            actions.extend(review_actions)

            # Proactive satisfaction improvements
            if len(actions) < response_capacity:
                proactive_actions = await self._generate_proactive_actions(context)
                actions.extend(proactive_actions)

            # Sort by priority and urgency
            actions.sort(
                key=lambda x: (x.priority, -self._calculate_urgency_score(x)),
                reverse=True,
            )

            return actions[:response_capacity]  # Respect capacity constraints

        except Exception as e:
            logger.error(f"Error generating customer service actions: {e}")
            return []

    def get_priority_score(self, event: BaseEvent) -> float:
        """Calculate priority score for customer service events."""
        if isinstance(event, SaleOccurred):
            # Higher priority for high-value sales or low trust scores
            priority = 0.3  # Base priority
            if event.total_revenue.cents > 10000:  # $100+ order
                priority += 0.2
            if event.trust_score_at_sale < 0.7:
                priority += 0.3
            return min(0.9, priority)

        elif isinstance(event, TickEvent):
            # Regular monitoring is lower priority
            return 0.2

        return 0.1

    async def _process_pending_messages(self) -> List[SkillAction]:
        """Process pending customer messages and generate responses."""
        actions = []

        # Sort messages by priority and urgency
        sorted_messages = sorted(
            self.pending_messages.values(),
            key=lambda m: (
                self._get_priority_value(m.priority),
                self._calculate_message_urgency(m),
            ),
            reverse=True,
        )

        for message in sorted_messages[:5]:  # Process top 5 messages
            response_action = await self._create_message_response_action(message)
            if response_action:
                actions.append(response_action)
                # Remove from pending after processing
                if message.message_id in self.pending_messages:
                    del self.pending_messages[message.message_id]

        return actions

    async def _create_message_response_action(
        self, message: CustomerMessage
    ) -> Optional[SkillAction]:
        """Create response action for customer message."""
        try:
            # Determine response strategy based on message type and sentiment
            if message.sentiment < -0.5:  # Very negative
                if message.message_type == MessageType.COMPLAINT:
                    response_strategy = "complaint_resolution"
                else:
                    response_strategy = "negative_response"
            elif message.message_type == MessageType.RETURN_REQUEST:
                response_strategy = "return_assistance"
            elif message.message_type == MessageType.TECHNICAL_ISSUE:
                response_strategy = "technical_support"
            else:
                response_strategy = "general_inquiry"

            # Generate response content
            response_content = await self._generate_response_content(
                message, response_strategy
            )

            # Calculate confidence based on message complexity and sentiment
            confidence = self._calculate_response_confidence(message)

            # Determine if escalation is needed
            needs_escalation = (
                message.sentiment < self.escalation_threshold
                or message.priority == MessagePriority.URGENT
                or "refund" in message.content.lower()
                or "legal" in message.content.lower()
            )

            # Calculate priority based on message urgency and customer value
            priority = self._calculate_response_priority(message)

            action_type = (
                "escalate_issue" if needs_escalation else "respond_to_customer_message"
            )

            parameters = {
                "message_id": message.message_id,
                "customer_id": message.customer_id,
                "response_content": response_content,
                "response_strategy": response_strategy,
                "escalation_required": needs_escalation,
                "estimated_resolution_time": self._estimate_resolution_time(message),
                "follow_up_required": message.sentiment < -0.3,
            }

            reasoning = (
                f"Responding to {message.message_type.value} from customer {message.customer_id} "
                f"(sentiment: {message.sentiment:.2f}, priority: {message.priority.value})"
            )

            if needs_escalation:
                reasoning += " - Escalating due to complexity/sentiment"

            return SkillAction(
                action_type=action_type,
                parameters=parameters,
                confidence=confidence,
                reasoning=reasoning,
                priority=priority,
                resource_requirements={
                    "response_time_minutes": 15 if not needs_escalation else 5,
                    "escalation_slot": needs_escalation,
                },
                expected_outcome={
                    "customer_satisfaction_improvement": (
                        0.3 if message.sentiment < 0 else 0.1
                    ),
                    "issue_resolution_probability": (
                        0.8 if not needs_escalation else 0.9
                    ),
                    "response_time_hours": 1 if needs_escalation else 2,
                },
                skill_source=self.skill_name,
            )

        except Exception as e:
            logger.error(f"Error creating message response action: {e}")
            return None

    async def _generate_response_content(
        self, message: CustomerMessage, strategy: str
    ) -> str:
        """Generate appropriate response content for customer message."""
        # Get base template
        template_key = self._get_template_key(strategy)
        base_template = self.response_templates.get(
            template_key, "Thank you for contacting us. We'll get back to you soon."
        )

        # Customize based on message content and customer history
        specific_response = ""

        if strategy == "complaint_resolution":
            specific_response = "We're investigating this issue and will provide a resolution within 24 hours."
        elif strategy == "return_assistance":
            return_info = self.knowledge_base.get("return_policy", {})
            specific_response = (
                f"You can return items within {return_info.get('window_days', 30)} days. "
                f"Please ensure items are {return_info.get('condition_requirements', 'in original condition')}."
            )
        elif strategy == "technical_support":
            specific_response = (
                "Our technical team will help you resolve this issue. "
                f"Support is available {self.knowledge_base.get('product_support', {}).get('technical_support_hours', '24/7')}."
            )
        elif strategy == "general_inquiry":
            specific_response = "We're happy to provide the information you requested."

        # Replace placeholders in template
        response = base_template.format(
            specific_response=specific_response,
            customer_name=message.customer_id,  # In real system, would lookup actual name
            resolution_offer=(
                "full refund or replacement"
                if message.sentiment < -0.7
                else "store credit"
            ),
            return_instructions=specific_response if "return" in strategy else "",
            troubleshooting_steps=specific_response if "technical" in strategy else "",
            timeframe=(
                "24 hours" if message.priority == MessagePriority.URGENT else "48 hours"
            ),
        )

        return response

    def _get_template_key(self, strategy: str) -> str:
        """Map response strategy to template key."""
        strategy_mapping = {
            "complaint_resolution": "complaint_acknowledgment",
            "negative_response": "complaint_acknowledgment",
            "return_assistance": "return_process",
            "technical_support": "technical_support",
            "general_inquiry": "inquiry_general",
        }
        return strategy_mapping.get(strategy, "inquiry_general")

    async def _monitor_reviews(self) -> List[SkillAction]:
        """Monitor reviews and generate response actions for negative reviews."""
        actions = []

        # Process pending negative reviews
        for review in list(self.pending_reviews.values()):
            if review.rating <= 2 and review.requires_response:  # 1-2 star reviews
                response_action = await self._create_review_response_action(review)
                if response_action:
                    actions.append(response_action)
                    # Remove from pending
                    if review.review_id in self.pending_reviews:
                        del self.pending_reviews[review.review_id]

        return actions

    async def _create_review_response_action(
        self, review: CustomerReview
    ) -> Optional[SkillAction]:
        """Create response action for customer review."""
        try:
            # Determine response approach based on rating and sentiment
            if review.rating <= 2:
                response_type = "negative_review_response"
                template_key = "review_response_negative"
            else:
                response_type = "positive_review_response"
                template_key = "review_response_positive"

            # Generate response content
            base_response = self.response_templates[template_key]

            if review.rating <= 2:
                resolution_offer = "We'd like to make this right. Please contact us directly so we can resolve this issue."
                response_content = base_response.format(
                    resolution_offer=resolution_offer
                )
            else:
                response_content = base_response

            confidence = (
                0.8 if review.rating <= 2 else 0.9
            )  # Higher confidence for positive responses
            priority = (
                0.7 if review.rating <= 2 else 0.4
            )  # Higher priority for negative reviews

            return SkillAction(
                action_type="respond_to_review",
                parameters={
                    "review_id": review.review_id,
                    "customer_id": review.customer_id,
                    "response_content": response_content,
                    "response_type": response_type,
                    "public_response": True,
                    "follow_up_privately": review.rating <= 2,
                },
                confidence=confidence,
                reasoning=f"Responding to {review.rating}-star review for {review.asin} to maintain reputation",
                priority=priority,
                resource_requirements={"response_time_minutes": 10},
                expected_outcome={
                    "reputation_protection": 0.6 if review.rating <= 2 else 0.2,
                    "customer_retention_probability": (
                        0.4 if review.rating <= 2 else 0.8
                    ),
                },
                skill_source=self.skill_name,
            )

        except Exception as e:
            logger.error(f"Error creating review response action: {e}")
            return None

    async def _analyze_satisfaction_metrics(self) -> List[SkillAction]:
        """Analyze customer satisfaction metrics and generate improvement actions."""
        actions = []

        # Calculate current satisfaction metrics
        current_metrics = await self._calculate_current_satisfaction_metrics()

        # Identify areas needing improvement
        if current_metrics.satisfaction_score < self.satisfaction_target:
            improvement_action = await self._create_satisfaction_improvement_action(
                current_metrics
            )
            if improvement_action:
                actions.append(improvement_action)

        if current_metrics.average_response_time > self.response_time_target:
            response_time_action = await self._create_response_time_improvement_action(
                current_metrics
            )
            if response_time_action:
                actions.append(response_time_action)

        return actions

    async def _calculate_current_satisfaction_metrics(
        self,
    ) -> CustomerSatisfactionMetrics:
        """Calculate current customer satisfaction metrics."""
        now = datetime.now()
        period_start = now - timedelta(days=7)  # Last 7 days

        # Calculate metrics based on recent interactions
        recent_scores = [
            score for score in self.satisfaction_scores[-20:]
        ]  # Last 20 interactions
        avg_satisfaction = (
            sum(recent_scores) / len(recent_scores) if recent_scores else 0.5
        )

        # Calculate response time from recent interactions
        avg_response_time = self.average_response_time

        # Calculate resolution and escalation rates
        recent_interactions = len(
            self.interaction_history[-50:]
        )  # Last 50 interactions
        escalations = min(self.escalation_count, recent_interactions)
        escalation_rate = (
            escalations / recent_interactions if recent_interactions > 0 else 0.0
        )
        resolution_rate = 1.0 - escalation_rate  # Simplified calculation

        return CustomerSatisfactionMetrics(
            period_start=period_start,
            period_end=now,
            total_interactions=recent_interactions,
            average_response_time=avg_response_time,
            satisfaction_score=avg_satisfaction,
            resolution_rate=resolution_rate,
            escalation_rate=escalation_rate,
            positive_reviews=len(
                [r for r in self.pending_reviews.values() if r.rating >= 4]
            ),
            negative_reviews=len(
                [r for r in self.pending_reviews.values() if r.rating <= 2]
            ),
        )

    async def _create_satisfaction_improvement_action(
        self, metrics: CustomerSatisfactionMetrics
    ) -> Optional[SkillAction]:
        """Create action to improve customer satisfaction."""
        try:
            # Identify specific improvement areas
            improvement_areas = []
            if metrics.resolution_rate < 0.8:
                improvement_areas.append("resolution_process")
            if metrics.average_response_time > self.response_time_target:
                improvement_areas.append("response_time")
            if metrics.escalation_rate > 0.2:
                improvement_areas.append("first_contact_resolution")

            return SkillAction(
                action_type="improve_customer_satisfaction",
                parameters={
                    "current_satisfaction": metrics.satisfaction_score,
                    "target_satisfaction": self.satisfaction_target,
                    "improvement_areas": improvement_areas,
                    "priority_focus": (
                        improvement_areas[0] if improvement_areas else "general"
                    ),
                    "implementation_timeline": "immediate",
                },
                confidence=0.7,
                reasoning=f"Customer satisfaction ({metrics.satisfaction_score:.2f}) below target ({self.satisfaction_target:.2f})",
                priority=0.8,
                resource_requirements={
                    "process_improvement_effort": True,
                    "training_resources": "response_time" in improvement_areas,
                },
                expected_outcome={
                    "satisfaction_improvement": self.satisfaction_target
                    - metrics.satisfaction_score,
                    "process_efficiency_gain": 0.2,
                },
                skill_source=self.skill_name,
            )

        except Exception as e:
            logger.error(f"Error creating satisfaction improvement action: {e}")
            return None

    async def _generate_synthetic_interactions(
        self, event: TickEvent
    ) -> List[SkillAction]:
        """Generate synthetic customer interactions for testing purposes."""
        actions = []  # type: ignore[var-annotated]

        # Simulate receiving customer messages periodically
        if event.tick_number % 10 == 0:  # Every 10 ticks
            synthetic_message = await self._create_synthetic_message(event.tick_number)
            if synthetic_message:
                self.pending_messages[synthetic_message.message_id] = synthetic_message

        # Simulate receiving reviews periodically
        if event.tick_number % 15 == 0:  # Every 15 ticks
            synthetic_review = await self._create_synthetic_review(event.tick_number)
            if synthetic_review:
                self.pending_reviews[synthetic_review.review_id] = synthetic_review

        return actions

    async def _create_synthetic_message(
        self, tick_number: int
    ) -> Optional[CustomerMessage]:
        """Create synthetic customer message for testing."""
        import random

        message_types = list(MessageType)
        priorities = list(MessagePriority)

        message_type = random.choice(message_types)
        priority = random.choice(priorities)
        sentiment = random.uniform(-0.8, 0.8)

        # Generate content based on type
        content_templates = {
            MessageType.INQUIRY: "I have a question about my recent order. Can you help?",
            MessageType.COMPLAINT: "I'm not satisfied with my purchase. The product doesn't work as expected.",
            MessageType.RETURN_REQUEST: "I need to return this item. How do I proceed?",
            MessageType.TECHNICAL_ISSUE: "I'm having trouble setting up the product. Can you provide support?",
            MessageType.FEEDBACK: "I wanted to share some feedback about my experience.",
        }

        content = content_templates.get(
            message_type, "I need assistance with my order."
        )

        return CustomerMessage(
            message_id=f"msg_{tick_number}_{random.randint(1000, 9999)}",
            customer_id=f"customer_{random.randint(100, 999)}",
            asin=f"ASIN{random.randint(1000, 9999)}",
            message_type=message_type,
            priority=priority,
            content=content,
            sentiment=sentiment,
            response_deadline=datetime.now()
            + timedelta(hours=self.response_time_target),
        )

    async def _create_synthetic_review(
        self, tick_number: int
    ) -> Optional[CustomerReview]:
        """Create synthetic customer review for testing."""
        import random

        rating = random.randint(1, 5)
        sentiment = -0.6 if rating <= 2 else (0.8 if rating >= 4 else 0.2)

        title_templates = {
            1: "Very disappointed",
            2: "Not what I expected",
            3: "Okay product",
            4: "Good purchase",
            5: "Excellent product!",
        }

        content_templates = {
            1: "This product did not meet my expectations at all. Would not recommend.",
            2: "Had some issues with this product. Quality could be better.",
            3: "Average product. Does what it says but nothing special.",
            4: "Good product overall. Happy with the purchase.",
            5: "Amazing product! Exceeded my expectations. Highly recommend!",
        }

        return CustomerReview(
            review_id=f"review_{tick_number}_{random.randint(1000, 9999)}",
            customer_id=f"customer_{random.randint(100, 999)}",
            asin=f"ASIN{random.randint(1000, 9999)}",
            rating=rating,
            title=title_templates[rating],
            content=content_templates[rating],
            sentiment=sentiment,
            requires_response=rating <= 2
            or random.random() < 0.3,  # Always respond to negative, sometimes to others
            impact_score=0.8 if rating <= 2 else 0.2,
        )

    def _get_priority_value(self, priority: MessagePriority) -> int:
        """Convert priority enum to numeric value for sorting."""
        priority_values = {
            MessagePriority.LOW: 1,
            MessagePriority.MEDIUM: 2,
            MessagePriority.HIGH: 3,
            MessagePriority.URGENT: 4,
        }
        return priority_values[priority]

    def _calculate_message_urgency(self, message: CustomerMessage) -> float:
        """Calculate urgency score for message based on various factors."""
        urgency = 0.0

        # Time-based urgency
        if message.response_deadline:
            time_remaining = (
                message.response_deadline - datetime.now()
            ).total_seconds() / 3600  # hours
            if time_remaining < 2:
                urgency += 0.5
            elif time_remaining < 6:
                urgency += 0.3

        # Sentiment-based urgency
        if message.sentiment < -0.5:
            urgency += 0.4
        elif message.sentiment < -0.2:
            urgency += 0.2

        # Type-based urgency
        if message.message_type == MessageType.COMPLAINT:
            urgency += 0.3
        elif message.message_type == MessageType.RETURN_REQUEST:
            urgency += 0.2

        return min(1.0, urgency)

    def _calculate_response_confidence(self, message: CustomerMessage) -> float:
        """Calculate confidence score for response generation."""
        base_confidence = 0.8

        # Adjust based on message complexity
        complexity_indicators = ["legal", "refund", "lawsuit", "attorney"]
        if any(
            indicator in message.content.lower() for indicator in complexity_indicators
        ):
            base_confidence -= 0.3

        # Adjust based on sentiment
        if message.sentiment < -0.7:
            base_confidence -= 0.2
        elif message.sentiment > 0.5:
            base_confidence += 0.1

        return max(0.3, min(0.95, base_confidence))

    def _calculate_response_priority(self, message: CustomerMessage) -> float:
        """Calculate priority score for response action."""
        priority = self._get_priority_value(message.priority) / 4.0  # Normalize to 0-1

        # Adjust based on sentiment
        if message.sentiment < -0.5:
            priority += 0.2

        # Adjust based on customer value (simplified)
        if message.customer_id in self.customer_profiles:
            customer_value = self.customer_profiles[message.customer_id].get(
                "value_tier", "standard"
            )
            if customer_value == "premium":
                priority += 0.1

        return min(0.9, priority)

    def _estimate_resolution_time(self, message: CustomerMessage) -> int:
        """Estimate resolution time in hours for a message."""
        base_time = {
            MessageType.INQUIRY: 2,
            MessageType.COMPLAINT: 8,
            MessageType.RETURN_REQUEST: 4,
            MessageType.TECHNICAL_ISSUE: 6,
            MessageType.FEEDBACK: 1,
            MessageType.REVIEW: 2,
        }

        estimated_time = base_time.get(message.message_type, 4)

        # Adjust based on complexity
        if message.sentiment < -0.5:
            estimated_time *= 1.5  # type: ignore[assignment]

        if message.priority == MessagePriority.URGENT:
            estimated_time *= 0.5  # Faster for urgent  # type: ignore[assignment]

        return int(estimated_time)

    def _calculate_urgency_score(self, action: SkillAction) -> float:
        """Calculate urgency score for action prioritization."""
        urgency = 0.5  # Base urgency

        # Increase urgency for escalations
        if action.action_type == "escalate_issue":
            urgency += 0.3

        # Increase urgency for negative reviews
        if (
            action.action_type == "respond_to_review"
            and action.parameters.get("response_type") == "negative_review_response"
        ):
            urgency += 0.2

        return urgency

    async def _process_priority_messages(self, capacity: int) -> List[SkillAction]:
        """Process highest priority messages within capacity limits."""
        actions = []

        # Sort pending messages by priority and urgency
        sorted_messages = sorted(
            self.pending_messages.values(),
            key=lambda m: (
                self._get_priority_value(m.priority),
                self._calculate_message_urgency(m),
            ),
            reverse=True,
        )

        for message in sorted_messages[:capacity]:
            action = await self._create_message_response_action(message)
            if action:
                actions.append(action)

        return actions

    async def _generate_review_responses(
        self, remaining_capacity: int
    ) -> List[SkillAction]:
        """Generate review responses within remaining capacity."""
        actions = []

        # Focus on negative reviews requiring response
        negative_reviews = [
            r
            for r in self.pending_reviews.values()
            if r.rating <= 2 and r.requires_response
        ]

        for review in negative_reviews[:remaining_capacity]:
            action = await self._create_review_response_action(review)
            if action:
                actions.append(action)

        return actions

    async def _generate_proactive_actions(
        self, context: SkillContext
    ) -> List[SkillAction]:
        """Generate proactive customer service actions."""
        actions = []

        # Proactive outreach to customers with recent issues
        if len(self.escalated_issues) > 0:
            follow_up_action = await self._create_proactive_follow_up_action(None)
            if follow_up_action:
                actions.append(follow_up_action)

        return actions

    async def _create_proactive_follow_up_action(
        self, event: Optional[SaleOccurred]
    ) -> Optional[SkillAction]:
        """Create proactive customer follow-up action."""
        try:
            if event:
                # Follow-up for high-value sale
                return SkillAction(
                    action_type="send_proactive_follow_up",
                    parameters={
                        "customer_id": f"customer_from_sale_{event.asin}",
                        "follow_up_type": "post_purchase",
                        "message_content": "Thank you for your recent purchase! We want to ensure you're completely satisfied. Please let us know if you need any assistance.",
                        "timing": "24_hours_post_purchase",
                    },
                    confidence=0.8,
                    reasoning=f"Proactive follow-up for high-value sale (${event.total_revenue.to_float():.2f})",
                    priority=0.4,
                    resource_requirements={"outreach_capacity": 1},
                    expected_outcome={
                        "customer_satisfaction_boost": 0.2,
                        "issue_prevention": 0.3,
                    },
                    skill_source=self.skill_name,
                )
            else:
                # General proactive follow-up
                return SkillAction(
                    action_type="conduct_satisfaction_survey",
                    parameters={
                        "survey_type": "general_satisfaction",
                        "target_customers": "recent_purchasers",
                        "questions": [
                            "How satisfied are you with your recent purchase?",
                            "Would you recommend us to a friend?",
                        ],
                        "incentive": "5% discount on next purchase",
                    },
                    confidence=0.7,
                    reasoning="Proactive customer satisfaction measurement",
                    priority=0.3,
                    resource_requirements={"survey_capacity": 1},
                    expected_outcome={
                        "satisfaction_insights": True,
                        "customer_engagement": 0.2,
                    },
                    skill_source=self.skill_name,
                )

        except Exception as e:
            logger.error(f"Error creating proactive follow-up action: {e}")
            return None

    async def _create_issue_prevention_action(
        self, event: SaleOccurred
    ) -> Optional[SkillAction]:
        """Create issue prevention action for low trust score sales."""
        try:
            return SkillAction(
                action_type="implement_issue_prevention",
                parameters={
                    "sale_id": event.event_id,
                    "asin": event.asin,
                    "trust_score": event.trust_score_at_sale,
                    "prevention_measures": [
                        "proactive_quality_check",
                        "enhanced_shipping_tracking",
                        "expedited_support_access",
                    ],
                    "monitoring_period": "14_days",
                },
                confidence=0.6,
                reasoning=f"Issue prevention for sale with low trust score ({event.trust_score_at_sale:.2f})",
                priority=0.5,
                resource_requirements={"prevention_resources": True},
                expected_outcome={
                    "issue_reduction_probability": 0.4,
                    "customer_confidence_boost": 0.3,
                },
                skill_source=self.skill_name,
            )

        except Exception as e:
            logger.error(f"Error creating issue prevention action: {e}")
            return None

    async def _create_response_time_improvement_action(
        self, metrics: CustomerSatisfactionMetrics
    ) -> Optional[SkillAction]:
        """Create action to improve response times."""
        try:
            return SkillAction(
                action_type="optimize_response_time",
                parameters={
                    "current_avg_time": metrics.average_response_time,
                    "target_time": self.response_time_target,
                    "optimization_strategies": [
                        "auto_response_templates",
                        "priority_queue_optimization",
                        "staff_scheduling_adjustment",
                    ],
                    "implementation_timeline": "1_week",
                },
                confidence=0.8,
                reasoning=f"Response time ({metrics.average_response_time:.1f}h) exceeds target ({self.response_time_target}h)",
                priority=0.6,
                resource_requirements={
                    "process_optimization": True,
                    "staff_training": True,
                },
                expected_outcome={
                    "response_time_reduction": metrics.average_response_time
                    - self.response_time_target,
                    "efficiency_improvement": 0.25,
                },
                skill_source=self.skill_name,
            )

        except Exception as e:
            logger.error(f"Error creating response time improvement action: {e}")
            return None

    async def draft_response(self, message_id: str) -> Optional[str]:
        """Public method to draft response for external use."""
        if message_id in self.pending_messages:
            message = self.pending_messages[message_id]
            return await self._generate_response_content(message, "general_inquiry")
        return None

    async def escalate_issue(self, message_id: str, escalation_reason: str) -> bool:
        """Public method to escalate issue for external use."""
        if message_id in self.pending_messages:
            message = self.pending_messages[message_id]
            self.escalated_issues[message_id] = {
                "message": message,
                "escalation_reason": escalation_reason,
                "escalated_at": datetime.now(),
                "status": "escalated",
            }
            self.escalation_count += 1
            del self.pending_messages[message_id]
            return True
        return False

    async def track_satisfaction(
        self, interaction_id: str, satisfaction_score: float
    ) -> None:
        """Public method to track satisfaction for external use."""
        self.satisfaction_scores.append(satisfaction_score)
        self.interaction_history.append(
            {
                "interaction_id": interaction_id,
                "satisfaction_score": satisfaction_score,
                "timestamp": datetime.now(),
                "skill_source": self.skill_name,
            }
        )

        # Update average satisfaction using exponential moving average
        if len(self.satisfaction_scores) == 1:
            avg_satisfaction = satisfaction_score
        else:
            prev_avg = sum(self.satisfaction_scores[:-1]) / len(
                self.satisfaction_scores[:-1]
            )
            avg_satisfaction = (prev_avg * 0.9) + (satisfaction_score * 0.1)

        logger.debug(
            f"Tracked satisfaction: {satisfaction_score:.2f}, running average: {avg_satisfaction:.2f}"
        )


# Alias for backward compatibility
CustomerService = CustomerServiceSkill
