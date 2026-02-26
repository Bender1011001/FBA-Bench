"""
Advanced cognitive evaluation metrics for FBA-Bench.

This module provides sophisticated metrics for evaluating agent cognitive capabilities
including logical consistency, causal reasoning, abstract reasoning, metacognition,
multi-step planning, memory efficiency, and learning assessment.
"""

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Tuple

from .base import BaseMetric, MetricConfig


@dataclass
class ReasoningTrace:
    """Trace of a reasoning process."""

    steps: List[str]
    logical_connections: List[
        Tuple[int, int, str]
    ]  # (from_step, to_step, connection_type)
    confidence_scores: List[float]
    timestamp: datetime


@dataclass
class MemoryAssessment:
    """Assessment of memory capabilities."""

    recall_accuracy: float
    retention_rate: float
    retrieval_speed: float
    memory_efficiency: float
    interference_resistance: float


class AdvancedCognitiveMetrics(BaseMetric):
    """
    Advanced metrics for evaluating sophisticated cognitive capabilities.

    This class provides comprehensive evaluation of advanced cognitive functions
    including logical consistency, causal reasoning, abstract reasoning, and metacognition.
    """

    def __init__(self, config: MetricConfig = None):
        """
        Initialize advanced cognitive metrics.

        Args:
            config: Metric configuration (uses defaults if None)
        """
        if config is None:
            config = MetricConfig(
                name="advanced_cognitive_performance",
                description="Advanced cognitive performance score",
                unit="score",
                min_value=0.0,
                max_value=100.0,
                target_value=85.0,
            )

        super().__init__(config)

        # Sub-metric configurations
        self.logical_consistency_config = MetricConfig(
            name="logical_consistency",
            description="Logical consistency in reasoning",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.causal_reasoning_config = MetricConfig(
            name="causal_reasoning",
            description="Causal reasoning capability",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.abstract_reasoning_config = MetricConfig(
            name="abstract_reasoning",
            description="Abstract reasoning capability",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.metacognition_config = MetricConfig(
            name="metacognition",
            description="Metacognitive awareness and reflection",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.multistep_planning_config = MetricConfig(
            name="multistep_planning",
            description="Multi-step planning and execution",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.memory_efficiency_config = MetricConfig(
            name="memory_efficiency",
            description="Memory efficiency and retention",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.learning_adaptation_config = MetricConfig(
            name="learning_adaptation",
            description="Learning and adaptation capability",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

    def calculate(self, data: Dict[str, Any]) -> float:  # type: ignore[override]
        """
        Calculate advanced cognitive performance score.

        Args:
            data: Data containing advanced cognitive metrics

        Returns:
            Overall advanced cognitive score
        """
        if not isinstance(data, dict):
            return 0.0
        # Calculate sub-metric scores
        logical_consistency = self.calculate_logical_consistency(data)
        causal_reasoning = self.calculate_causal_reasoning(data)
        abstract_reasoning = self.calculate_abstract_reasoning(data)
        metacognition = self.calculate_metacognition(data)
        multistep_planning = self.calculate_multistep_planning(data)
        memory_efficiency = self.calculate_memory_efficiency(data)
        learning_adaptation = self.calculate_learning_adaptation(data)

        # Calculate weighted average
        weights = {
            "logical_consistency": 0.18,
            "causal_reasoning": 0.15,
            "abstract_reasoning": 0.15,
            "metacognition": 0.12,
            "multistep_planning": 0.15,
            "memory_efficiency": 0.12,
            "learning_adaptation": 0.13,
        }

        overall_score = (
            logical_consistency * weights["logical_consistency"]
            + causal_reasoning * weights["causal_reasoning"]
            + abstract_reasoning * weights["abstract_reasoning"]
            + metacognition * weights["metacognition"]
            + multistep_planning * weights["multistep_planning"]
            + memory_efficiency * weights["memory_efficiency"]
            + learning_adaptation * weights["learning_adaptation"]
        )

        return overall_score

    def calculate_logical_consistency(self, data: Dict[str, Any]) -> float:
        """
        Calculate logical consistency score.

        Args:
            data: Data containing logical consistency metrics

        Returns:
            Logical consistency score
        """
        reasoning_traces = data.get("reasoning_traces", [])
        if not reasoning_traces:
            return 0.0

        consistency_scores = []

        for trace in reasoning_traces:
            if isinstance(trace, dict):
                trace = ReasoningTrace(
                    steps=trace.get("steps", []),
                    logical_connections=trace.get("logical_connections", []),
                    confidence_scores=trace.get("confidence_scores", []),
                    timestamp=datetime.now(),
                )

            # Check for contradictions
            contradictions = self._detect_contradictions(trace)

            # Evaluate logical flow
            logical_flow_score = self._evaluate_logical_flow(trace)

            # Check confidence consistency
            confidence_consistency = self._evaluate_confidence_consistency(trace)

            # Calculate overall consistency for this trace
            trace_consistency = (
                (1.0 - contradictions) * 0.4
                + logical_flow_score * 0.3
                + confidence_consistency * 0.3
            )
            consistency_scores.append(trace_consistency)

        return statistics.mean(consistency_scores) * 100

    def calculate_causal_reasoning(self, data: Dict[str, Any]) -> float:
        """
        Calculate causal reasoning score.

        Args:
            data: Data containing causal reasoning metrics

        Returns:
            Causal reasoning score
        """
        causal_chains = data.get("causal_chains", [])
        intervention_results = data.get("intervention_results", [])

        if not causal_chains and not intervention_results:
            return 0.0

        causal_scores = []

        # Evaluate causal chains
        for chain in causal_chains:
            chain_score = self._evaluate_causal_chain(chain)
            causal_scores.append(chain_score)

        # Evaluate intervention understanding
        for intervention in intervention_results:
            intervention_score = self._evaluate_intervention_reasoning(intervention)
            causal_scores.append(intervention_score)

        return statistics.mean(causal_scores) * 100 if causal_scores else 0.0

    def calculate_abstract_reasoning(self, data: Dict[str, Any]) -> float:
        """
        Calculate abstract reasoning score.

        Args:
            data: Data containing abstract reasoning metrics

        Returns:
            Abstract reasoning score
        """
        pattern_recognition = data.get("pattern_recognition_tasks", [])
        analogy_tasks = data.get("analogy_tasks", [])
        abstraction_tasks = data.get("abstraction_tasks", [])

        if not pattern_recognition and not analogy_tasks and not abstraction_tasks:
            return 0.0

        abstract_scores = []

        # Evaluate pattern recognition
        for task in pattern_recognition:
            score = self._evaluate_pattern_recognition(task)
            abstract_scores.append(score)

        # Evaluate analogy reasoning
        for task in analogy_tasks:
            score = self._evaluate_analogy_reasoning(task)
            abstract_scores.append(score)

        # Evaluate abstraction capability
        for task in abstraction_tasks:
            score = self._evaluate_abstraction_capability(task)
            abstract_scores.append(score)

        return statistics.mean(abstract_scores) * 100 if abstract_scores else 0.0

    def calculate_metacognition(self, data: Dict[str, Any]) -> float:
        """
        Calculate metacognition score.

        Accepts confidence_calibration as:
        - List[dict] with keys 'confidence_levels' and 'accuracy_levels'
        - Single dict with the same keys
        - Scalar (int/float) which will be treated as both confidence and accuracy for a single-point calibration
        """
        self_assessments = data.get("self_assessments", [])
        reflection_episodes = data.get("reflection_episodes", [])
        confidence_calibration = data.get("confidence_calibration", [])

        # Normalize confidence_calibration to a list of dicts
        if isinstance(confidence_calibration, (int, float)):
            val = float(confidence_calibration)
            confidence_calibration = [
                {
                    "confidence_levels": [val],
                    "accuracy_levels": [val],
                }
            ]
        elif isinstance(confidence_calibration, dict):
            confidence_calibration = [confidence_calibration]
        elif not isinstance(confidence_calibration, list):
            confidence_calibration = []

        if (
            not self_assessments
            and not reflection_episodes
            and not confidence_calibration
        ):
            return 0.0

        metacognition_scores: List[float] = []

        # Evaluate self-assessment accuracy
        for assessment in self_assessments:
            score = self._evaluate_self_assessment(assessment)
            metacognition_scores.append(score)

        # Evaluate reflection quality
        for reflection in reflection_episodes:
            score = self._evaluate_reflection_quality(reflection)
            metacognition_scores.append(score)

        # Evaluate confidence calibration
        for calibration in confidence_calibration:
            if isinstance(calibration, dict):
                score = self._evaluate_confidence_calibration(calibration)
                metacognition_scores.append(score)

        return (
            statistics.mean(metacognition_scores) * 100 if metacognition_scores else 0.0
        )

    def calculate_multistep_planning(self, data: Dict[str, Any]) -> float:
        """
        Calculate multi-step planning score.

        Args:
            data: Data containing multi-step planning metrics

        Returns:
            Multi-step planning score
        """
        plans = data.get("multistep_plans", [])
        execution_traces = data.get("execution_traces", [])

        if not plans and not execution_traces:
            return 0.0

        planning_scores = []

        # Evaluate plan quality
        for plan in plans:
            score = self._evaluate_plan_quality(plan)
            planning_scores.append(score)

        # Evaluate execution quality
        for trace in execution_traces:
            score = self._evaluate_execution_quality(trace)
            planning_scores.append(score)

        return statistics.mean(planning_scores) * 100 if planning_scores else 0.0

    def calculate_memory_efficiency(self, data: Dict[str, Any]) -> float:
        """
        Calculate memory efficiency score.

        Args:
            data: Data containing memory efficiency metrics

        Returns:
            Memory efficiency score
        """
        memory_assessments = data.get("memory_assessments", [])
        if not memory_assessments:
            return 0.0

        memory_scores = []

        for assessment in memory_assessments:
            if isinstance(assessment, dict):
                assessment = MemoryAssessment(
                    recall_accuracy=assessment.get("recall_accuracy", 0.0),
                    retention_rate=assessment.get("retention_rate", 0.0),
                    retrieval_speed=assessment.get("retrieval_speed", 0.0),
                    memory_efficiency=assessment.get("memory_efficiency", 0.0),
                    interference_resistance=assessment.get(
                        "interference_resistance", 0.0
                    ),
                )

            # Calculate weighted memory score
            weights = {
                "recall_accuracy": 0.25,
                "retention_rate": 0.25,
                "retrieval_speed": 0.15,
                "memory_efficiency": 0.20,
                "interference_resistance": 0.15,
            }

            memory_score = (
                assessment.recall_accuracy * weights["recall_accuracy"]
                + assessment.retention_rate * weights["retention_rate"]
                + assessment.retrieval_speed * weights["retrieval_speed"]
                + assessment.memory_efficiency * weights["memory_efficiency"]
                + assessment.interference_resistance
                * weights["interference_resistance"]
            )

            memory_scores.append(memory_score)

        return statistics.mean(memory_scores) * 100

    def calculate_learning_adaptation(self, data: Dict[str, Any]) -> float:
        """
        Calculate learning and adaptation score.

        Args:
            data: Data containing learning and adaptation metrics

        Returns:
            Learning and adaptation score
        """
        learning_episodes = data.get("learning_episodes", [])
        adaptation_tasks = data.get("adaptation_tasks", [])

        if not learning_episodes and not adaptation_tasks:
            return 0.0

        learning_scores = []

        # Evaluate learning episodes
        for episode in learning_episodes:
            score = self._evaluate_learning_episode(episode)
            learning_scores.append(score)

        # Evaluate adaptation tasks
        for task in adaptation_tasks:
            score = self._evaluate_adaptation_task(task)
            learning_scores.append(score)

        return statistics.mean(learning_scores) * 100 if learning_scores else 0.0

    def _detect_contradictions(self, trace: ReasoningTrace) -> float:
        """Detect contradictions in reasoning trace."""
        contradictions = 0
        total_pairs = 0

        for i in range(len(trace.steps)):
            for j in range(i + 1, len(trace.steps)):
                total_pairs += 1
                if self._are_contradictory(trace.steps[i], trace.steps[j]):
                    contradictions += 1

        return contradictions / total_pairs if total_pairs > 0 else 0.0

    def _are_contradictory(self, statement1: str, statement2: str) -> bool:
        """Check if two statements are contradictory."""
        # Simple keyword-based contradiction detection
        # In a real implementation, this would use more sophisticated NLP
        negation_words = ["not", "no", "never", "none", "nothing"]

        words1 = statement1.lower().split()
        words2 = statement2.lower().split()

        # Check if one statement is a negation of the other
        for word in negation_words:
            if word in words1 and word not in words2:
                # Check if the rest of the words are similar
                rest1 = [w for w in words1 if w not in negation_words]
                rest2 = [w for w in words2 if w not in negation_words]
                if len(set(rest1) & set(rest2)) / max(len(rest1), len(rest2)) > 0.7:
                    return True

        return False

    def _evaluate_logical_flow(self, trace: ReasoningTrace) -> float:
        """Evaluate the logical flow of reasoning."""
        if len(trace.steps) < 2:
            return 1.0

        # Check if logical connections form a coherent flow
        flow_score = 0.0

        # Evaluate connection quality
        for from_idx, to_idx, connection_type in trace.logical_connections:
            if connection_type in ["implies", "supports", "follows_from"]:
                flow_score += 1.0
            elif connection_type in ["contradicts", "weakens"]:
                flow_score -= 0.5

        # Normalize by number of connections
        if trace.logical_connections:
            flow_score = max(0.0, flow_score / len(trace.logical_connections))

        return flow_score

    def _evaluate_confidence_consistency(self, trace: ReasoningTrace) -> float:
        """Evaluate consistency of confidence scores."""
        if len(trace.confidence_scores) < 2:
            return 1.0

        # Calculate variance in confidence scores
        variance = statistics.variance(trace.confidence_scores)

        # Lower variance indicates more consistent confidence
        consistency_score = max(0.0, 1.0 - variance)

        return consistency_score

    def _evaluate_causal_chain(self, chain: Dict[str, Any]) -> float:
        """Evaluate a causal chain."""
        events = chain.get("events", [])
        causal_links = chain.get("causal_links", [])

        if not events or not causal_links:
            return 0.0

        # Check if causal links are valid
        valid_links = 0
        for link in causal_links:
            cause = link.get("cause")
            effect = link.get("effect")
            strength = link.get("strength", 0.0)

            if cause in events and effect in events and strength > 0.5:
                valid_links += 1

        return valid_links / len(causal_links) if causal_links else 0.0

    def _evaluate_intervention_reasoning(self, intervention: Dict[str, Any]) -> float:
        """Evaluate intervention reasoning."""
        predicted_outcome = intervention.get("predicted_outcome", {})
        actual_outcome = intervention.get("actual_outcome", {})

        if not predicted_outcome or not actual_outcome:
            return 0.0

        # Compare predicted vs actual outcomes
        accuracy = 0.0
        compared_aspects = 0

        for aspect in predicted_outcome:
            if aspect in actual_outcome:
                pred_val = predicted_outcome[aspect]
                act_val = actual_outcome[aspect]

                if isinstance(pred_val, (int, float)) and isinstance(
                    act_val, (int, float)
                ):
                    # Numerical comparison
                    diff = abs(pred_val - act_val)
                    max_val = max(abs(pred_val), abs(act_val))
                    aspect_accuracy = 1.0 - (diff / max_val) if max_val > 0 else 1.0
                else:
                    # Categorical comparison
                    aspect_accuracy = 1.0 if pred_val == act_val else 0.0

                accuracy += aspect_accuracy
                compared_aspects += 1

        return accuracy / compared_aspects if compared_aspects > 0 else 0.0

    def _evaluate_pattern_recognition(self, task: Dict[str, Any]) -> float:
        """Evaluate pattern recognition task."""
        expected_pattern = task.get("expected_pattern", [])
        recognized_pattern = task.get("recognized_pattern", [])

        if not expected_pattern or not recognized_pattern:
            return 0.0

        # Calculate pattern similarity
        similarity = self._calculate_pattern_similarity(
            expected_pattern, recognized_pattern
        )

        return similarity

    def _calculate_pattern_similarity(
        self, pattern1: List[Any], pattern2: List[Any]
    ) -> float:
        """Calculate similarity between two patterns."""
        if len(pattern1) != len(pattern2):
            # Handle different length patterns
            min_len = min(len(pattern1), len(pattern2))
            pattern1 = pattern1[:min_len]
            pattern2 = pattern2[:min_len]

        matches = sum(1 for a, b in zip(pattern1, pattern2) if a == b)
        return matches / len(pattern1) if pattern1 else 0.0

    def _evaluate_analogy_reasoning(self, task: Dict[str, Any]) -> float:
        """Evaluate analogy reasoning task."""
        analogy_structure = task.get("analogy_structure", {})
        response = task.get("response", {})

        if not analogy_structure or not response:
            return 0.0

        # Check if analogy structure is preserved
        structure_preserved = True
        for key in analogy_structure:
            if key not in response:
                structure_preserved = False
                break

        if not structure_preserved:
            return 0.0

        # Evaluate correctness of analogy mapping
        correct_mappings = 0
        total_mappings = 0

        for key, expected_value in analogy_structure.items():
            if key in response:
                total_mappings += 1
                if response[key] == expected_value:
                    correct_mappings += 1

        return correct_mappings / total_mappings if total_mappings > 0 else 0.0

    def _evaluate_abstraction_capability(self, task: Dict[str, Any]) -> float:
        """Evaluate abstraction capability."""
        concrete_examples = task.get("concrete_examples", [])
        abstract_concept = task.get("abstract_concept", "")
        generated_abstraction = task.get("generated_abstraction", "")

        if not concrete_examples or not abstract_concept or not generated_abstraction:
            return 0.0

        # Evaluate if generated abstraction captures the essence of examples
        # This is a simplified evaluation - in practice, would use more sophisticated NLP
        example_keywords = set()
        for example in concrete_examples:
            if isinstance(example, str):
                example_keywords.update(example.lower().split())

        abstraction_keywords = set(generated_abstraction.lower().split())
        concept_keywords = set(abstract_concept.lower().split())

        # Check if abstraction captures relevant keywords
        relevant_keywords = example_keywords & concept_keywords
        captured_keywords = relevant_keywords & abstraction_keywords

        if not relevant_keywords:
            return 0.0

        return len(captured_keywords) / len(relevant_keywords)

    def _evaluate_self_assessment(self, assessment: Dict[str, Any]) -> float:
        """Evaluate self-assessment accuracy."""
        self_evaluation = assessment.get("self_evaluation", 0.0)
        actual_performance = assessment.get("actual_performance", 0.0)

        # Calculate accuracy of self-assessment
        error = abs(self_evaluation - actual_performance)
        max_error = 100.0  # Maximum possible error

        accuracy = max(0.0, 1.0 - (error / max_error))

        return accuracy

    def _evaluate_reflection_quality(self, reflection: Dict[str, Any]) -> float:
        """Evaluate reflection quality."""
        reflection_depth = reflection.get("reflection_depth", 0)
        insight_quality = reflection.get("insight_quality", 0.0)
        actionability = reflection.get("actionability", 0.0)

        # Calculate weighted reflection score
        weights = {
            "reflection_depth": 0.4,
            "insight_quality": 0.4,
            "actionability": 0.2,
        }

        reflection_score = (
            reflection_depth * weights["reflection_depth"]
            + insight_quality * weights["insight_quality"]
            + actionability * weights["actionability"]
        )

        return reflection_score / 100.0  # Normalize to 0-1

    def _evaluate_confidence_calibration(self, calibration: Dict[str, Any]) -> float:
        """Evaluate confidence calibration."""
        confidence_levels = calibration.get("confidence_levels", [])
        accuracy_levels = calibration.get("accuracy_levels", [])

        if len(confidence_levels) != len(accuracy_levels):
            return 0.0

        # Calculate calibration error
        calibration_error = 0.0
        for conf, acc in zip(confidence_levels, accuracy_levels):
            calibration_error += abs(conf - acc)

        avg_error = (
            calibration_error / len(confidence_levels) if confidence_levels else 0.0
        )

        # Convert error to calibration score
        calibration_score = max(0.0, 1.0 - avg_error)

        return calibration_score

    def _evaluate_plan_quality(self, plan: Dict[str, Any]) -> float:
        """Evaluate plan quality."""
        completeness = plan.get("completeness", 0.0)
        feasibility = plan.get("feasibility", 0.0)
        optimality = plan.get("optimality", 0.0)
        robustness = plan.get("robustness", 0.0)

        # Calculate weighted plan score
        weights = {
            "completeness": 0.3,
            "feasibility": 0.3,
            "optimality": 0.2,
            "robustness": 0.2,
        }

        plan_score = (
            completeness * weights["completeness"]
            + feasibility * weights["feasibility"]
            + optimality * weights["optimality"]
            + robustness * weights["robustness"]
        )

        return plan_score / 100.0  # Normalize to 0-1

    def _evaluate_execution_quality(self, trace: Dict[str, Any]) -> float:
        """Evaluate execution quality."""
        plan_adherence = trace.get("plan_adherence", 0.0)
        error_handling = trace.get("error_handling", 0.0)
        efficiency = trace.get("efficiency", 0.0)
        adaptability = trace.get("adaptability", 0.0)

        # Calculate weighted execution score
        weights = {
            "plan_adherence": 0.3,
            "error_handling": 0.3,
            "efficiency": 0.2,
            "adaptability": 0.2,
        }

        execution_score = (
            plan_adherence * weights["plan_adherence"]
            + error_handling * weights["error_handling"]
            + efficiency * weights["efficiency"]
            + adaptability * weights["adaptability"]
        )

        return execution_score / 100.0  # Normalize to 0-1

    def _evaluate_learning_episode(self, episode: Dict[str, Any]) -> float:
        """Evaluate learning episode."""
        knowledge_gain = episode.get("knowledge_gain", 0.0)
        skill_improvement = episode.get("skill_improvement", 0.0)
        generalization = episode.get("generalization", 0.0)
        retention = episode.get("retention", 0.0)

        # Calculate weighted learning score
        weights = {
            "knowledge_gain": 0.3,
            "skill_improvement": 0.3,
            "generalization": 0.2,
            "retention": 0.2,
        }

        learning_score = (
            knowledge_gain * weights["knowledge_gain"]
            + skill_improvement * weights["skill_improvement"]
            + generalization * weights["generalization"]
            + retention * weights["retention"]
        )

        return learning_score / 100.0  # Normalize to 0-1

    def _evaluate_adaptation_task(self, task: Dict[str, Any]) -> float:
        """Evaluate adaptation task."""
        adaptation_speed = task.get("adaptation_speed", 0.0)
        adaptation_quality = task.get("adaptation_quality", 0.0)
        resource_efficiency = task.get("resource_efficiency", 0.0)

        # Calculate weighted adaptation score
        weights = {
            "adaptation_speed": 0.3,
            "adaptation_quality": 0.5,
            "resource_efficiency": 0.2,
        }

        adaptation_score = (
            adaptation_speed * weights["adaptation_speed"]
            + adaptation_quality * weights["adaptation_quality"]
            + resource_efficiency * weights["resource_efficiency"]
        )

        return adaptation_score / 100.0  # Normalize to 0-1

    def calculate_multi_step_planning(self, data: Dict[str, Any]) -> float:
        """
        Alias for calculate_multistep_planning to match external API expectations.
        """
        return self.calculate_multistep_planning(data)
