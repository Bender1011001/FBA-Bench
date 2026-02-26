from __future__ import annotations

import glob
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field

# Import the module so tests patching 'scenarios.scenario_framework.ScenarioFramework'
# correctly intercept our usage at call time.
import scenarios.scenario_framework as scenario_framework


class Scenario(BaseModel):
    """Model representing a scenario configuration."""

    id: str = Field(..., description="Unique scenario identifier")
    name: str = Field(..., min_length=1, description="Human-readable scenario name")
    description: Optional[str] = Field(None, description="Scenario description")
    difficulty_tier: int = Field(..., ge=0, le=3, description="Difficulty level (0-3)")
    expected_duration: int = Field(
        ..., gt=0, description="Expected duration in simulation ticks"
    )
    tags: List[str] = Field(
        default_factory=list, description="Scenario tags for categorization"
    )
    default_params: Dict[str, Any] = Field(
        default_factory=dict, description="Default parameters"
    )
    success_criteria: Dict[str, Any] = Field(
        default_factory=dict, description="Success criteria"
    )
    market_conditions: Dict[str, Any] = Field(
        default_factory=dict, description="Market conditions"
    )
    external_events: List[Dict[str, Any]] = Field(
        default_factory=list, description="External events"
    )
    agent_constraints: Dict[str, Any] = Field(
        default_factory=dict, description="Agent constraints"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScenarioCreate(BaseModel):
    """Model for creating a new scenario."""

    name: str = Field(..., min_length=1, description="Human-readable scenario name")
    description: Optional[str] = Field(None, description="Scenario description")
    difficulty_tier: int = Field(..., ge=0, le=3, description="Difficulty level (0-3)")
    expected_duration: int = Field(
        ..., gt=0, description="Expected duration in simulation ticks"
    )
    tags: List[str] = Field(
        default_factory=list, description="Scenario tags for categorization"
    )
    default_params: Dict[str, Any] = Field(
        default_factory=dict, description="Default parameters"
    )
    success_criteria: Dict[str, Any] = Field(
        default_factory=dict, description="Success criteria"
    )
    market_conditions: Dict[str, Any] = Field(
        default_factory=dict, description="Market conditions"
    )
    external_events: List[Dict[str, Any]] = Field(
        default_factory=list, description="External events"
    )
    agent_constraints: Dict[str, Any] = Field(
        default_factory=dict, description="Agent constraints"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "New Product Launch",
                "description": "Launch a new product in a competitive market",
                "difficulty_tier": 2,
                "expected_duration": 30,
                "tags": ["launch", "tier_2"],
                "default_params": {"initial_inventory": 100},
                "success_criteria": {"profit_target": 5000},
                "market_conditions": {"competition_level": "high"},
                "external_events": [{"type": "market_shift", "day": 15}],
                "agent_constraints": {"max_daily_actions": 5},
            }
        }
    )


class ScenarioUpdate(BaseModel):
    """Model for updating an existing scenario."""

    name: Optional[str] = Field(
        None, min_length=1, description="Human-readable scenario name"
    )
    description: Optional[str] = Field(None, description="Scenario description")
    difficulty_tier: Optional[int] = Field(
        None, ge=0, le=3, description="Difficulty level (0-3)"
    )
    expected_duration: Optional[int] = Field(
        None, gt=0, description="Expected duration in simulation ticks"
    )
    tags: Optional[List[str]] = Field(
        None, description="Scenario tags for categorization"
    )
    default_params: Optional[Dict[str, Any]] = Field(
        None, description="Default parameters"
    )
    success_criteria: Optional[Dict[str, Any]] = Field(
        None, description="Success criteria"
    )
    market_conditions: Optional[Dict[str, Any]] = Field(
        None, description="Market conditions"
    )
    external_events: Optional[List[Dict[str, Any]]] = Field(
        None, description="External events"
    )
    agent_constraints: Optional[Dict[str, Any]] = Field(
        None, description="Agent constraints"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Product Launch",
                "difficulty_tier": 3,
                "success_criteria": {"profit_target": 10000},
            }
        }
    )


class ScenarioList(BaseModel):
    """Response model for paginated scenario listing."""

    scenarios: List[Scenario] = Field(..., description="List of scenarios")
    total: int = Field(..., description="Total number of scenarios")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")


class ScenarioService:
    """Service for loading and managing scenarios from YAML files."""

    def __init__(self, scenarios_dir: str = "src/scenarios"):
        self.scenarios_dir = scenarios_dir
        self._scenario_cache: Optional[Dict[str, Scenario]] = None
        self._cache_timestamp: Optional[datetime] = None

    def _get_scenario_files(self) -> List[str]:
        """Get all YAML scenario files (deduplicated)."""
        patterns = [
            os.path.join(self.scenarios_dir, "*.yaml"),
            os.path.join(self.scenarios_dir, "*.yml"),
            os.path.join(self.scenarios_dir, "business_types", "*.yaml"),
            os.path.join(self.scenarios_dir, "business_types", "*.yml"),
            os.path.join(self.scenarios_dir, "multi_agent", "*.yaml"),
            os.path.join(self.scenarios_dir, "multi_agent", "*.yml"),
        ]

        # Use a set to avoid duplicates (important for tests that patch glob to return same list)
        files_set = set()
        for pattern in patterns:
            for path in glob.glob(pattern):
                files_set.add(path)

        # Return as list; ordering not guaranteed but tests only assert membership and count
        return list(files_set)

    def _load_scenario_from_file(self, filepath: str) -> Optional[Scenario]:
        """Load a single scenario from YAML file."""
        try:
            with open(filepath, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                return None

            # Extract scenario ID from filename
            filename = os.path.basename(filepath)
            scenario_id = os.path.splitext(filename)[0]

            # Parse difficulty tier (handle both string and int values)
            difficulty_tier = data.get("difficulty_tier", 1)
            if isinstance(difficulty_tier, str):
                tier_map = {"beginner": 0, "moderate": 1, "advanced": 2, "expert": 3}
                difficulty_tier = tier_map.get(difficulty_tier.lower(), 1)

            # Generate tags from file location and content
            tags = []
            if "business_types" in filepath:
                tags.append("business_type")
            if "multi_agent" in filepath:
                tags.append("multi_agent")

            # Add tier-based tag
            tier_names = {0: "tier_0", 1: "tier_1", 2: "tier_2", 3: "tier_3"}
            if difficulty_tier in tier_names:
                tags.append(tier_names[difficulty_tier])

            # Extract categories from business_parameters if available
            business_params = data.get("business_parameters", {})
            product_categories = business_params.get("product_categories", [])
            if product_categories:
                tags.extend(
                    [
                        f"category_{cat}"
                        for cat in product_categories
                        if isinstance(cat, str)
                    ]
                )

            # Normalize success criteria format
            normalized_success_criteria = self._normalize_success_criteria(data)

            scenario = Scenario(
                id=scenario_id,
                name=data.get("scenario_name", scenario_id.replace("_", " ").title()),
                description=self._extract_description(data),
                difficulty_tier=difficulty_tier,
                expected_duration=data.get("expected_duration", 30),
                tags=tags,
                default_params=data.get("business_parameters", {}),
                success_criteria=normalized_success_criteria,
                market_conditions=data.get("market_conditions", {}),
                external_events=data.get("external_events", []),
                agent_constraints=data.get("agent_constraints", {}),
            )

            return scenario

        except Exception as e:
            # Log error but don't fail the entire service
            print(f"Error loading scenario from {filepath}: {e}")
            return None

    def _normalize_success_criteria(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize success_criteria from different formats to dict."""
        success_criteria = data.get("success_criteria", {})

        # Handle list format (from some YAML files)
        if isinstance(success_criteria, list):
            normalized = {}
            for criterion in success_criteria:
                if isinstance(criterion, dict):
                    metric = criterion.get("metric")
                    condition = criterion.get("condition", ">")
                    value = criterion.get("value")
                    if metric and value is not None:
                        normalized[f"{metric}_{condition}"] = value
                        # Also add without condition for backward compatibility
                        normalized[metric] = value
            return normalized

        # Already dict format
        if isinstance(success_criteria, dict):
            return success_criteria

        return {}

    def _extract_description(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract description from scenario data."""
        # Try multiple possible description fields
        for field in ["description", "summary", "overview"]:
            if data.get(field):
                return str(data[field])

        # Generate description from success criteria if available
        success_criteria = self._normalize_success_criteria(data)
        if success_criteria:
            parts = []
            if "profit_target" in success_criteria:
                parts.append(f"Profit target: ${success_criteria['profit_target']}")
            if "final_profit" in success_criteria:
                parts.append(
                    f"Final profit target: ${success_criteria['final_profit']}"
                )
            if "customer_satisfaction" in success_criteria:
                parts.append(
                    f"Customer satisfaction: {success_criteria['customer_satisfaction']:.0%}"
                )
            if parts:
                return "Scenario objectives: " + ", ".join(parts)

        return None

    def _should_refresh_cache(self) -> bool:
        """Check if scenario cache should be refreshed."""
        if self._scenario_cache is None or self._cache_timestamp is None:
            return True

        # Refresh cache every 5 minutes
        now = datetime.now(timezone.utc)
        cache_age = (now - self._cache_timestamp).total_seconds()
        return cache_age > 300  # 5 minutes

    def _refresh_scenarios(self) -> None:
        """Refresh the scenario cache from filesystem."""
        scenarios = {}

        for filepath in self._get_scenario_files():
            scenario = self._load_scenario_from_file(filepath)
            if scenario:
                scenarios[scenario.id] = scenario

        self._scenario_cache = scenarios
        self._cache_timestamp = datetime.now(timezone.utc)

    def list_scenarios(
        self,
        page: int = 1,
        page_size: int = 20,
        tags: Optional[List[str]] = None,
        difficulty_tier: Optional[int] = None,
    ) -> ScenarioList:
        """List all available scenarios with optional filtering and pagination."""
        if self._should_refresh_cache():
            self._refresh_scenarios()

        all_scenarios = (
            list(self._scenario_cache.values()) if self._scenario_cache else []
        )

        # Apply filters
        filtered_scenarios = all_scenarios

        if tags:
            filtered_scenarios = [
                s for s in filtered_scenarios if any(tag in s.tags for tag in tags)
            ]

        if difficulty_tier is not None:
            filtered_scenarios = [
                s for s in filtered_scenarios if s.difficulty_tier == difficulty_tier
            ]

        # Sort by difficulty tier then name
        filtered_scenarios.sort(key=lambda s: (s.difficulty_tier, s.name))

        # Apply pagination
        total = len(filtered_scenarios)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_scenarios = filtered_scenarios[start_idx:end_idx]

        total_pages = (total + page_size - 1) // page_size

        return ScenarioList(
            scenarios=page_scenarios,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        """Get a specific scenario by ID."""
        if self._should_refresh_cache():
            self._refresh_scenarios()

        return self._scenario_cache.get(scenario_id) if self._scenario_cache else None

    def validate_scenario(self, scenario_id: str) -> bool:
        """Validate a scenario for consistency."""
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            return False

        try:
            # Use the existing ScenarioFramework validation
            config_data = {
                "scenario_name": scenario.name,
                "difficulty_tier": scenario.difficulty_tier,
                "expected_duration": scenario.expected_duration,
                "success_criteria": scenario.success_criteria,
                "market_conditions": scenario.market_conditions,
                "external_events": scenario.external_events,
                "agent_constraints": scenario.agent_constraints,
            }

            framework = scenario_framework.ScenarioFramework(config_data)
            return framework.validate_scenario_consistency()

        except Exception:
            return False

    def create_scenario(self, create_data: ScenarioCreate) -> Scenario:
        """Create a new scenario and write to YAML file."""
        if self._should_refresh_cache():
            self._refresh_scenarios()

        scenario_id = create_data.name.lower().replace(" ", "_")
        if scenario_id in self._scenario_cache:  # type: ignore[operator]
            raise ValueError(f"Scenario ID '{scenario_id}' already exists")

        # Prepare YAML data
        yaml_data = {
            "scenario_name": create_data.name,
            "description": create_data.description,
            "difficulty_tier": create_data.difficulty_tier,
            "expected_duration": create_data.expected_duration,
            "business_parameters": create_data.default_params,
            "success_criteria": create_data.success_criteria,
            "market_conditions": create_data.market_conditions,
            "external_events": create_data.external_events,
            "agent_constraints": create_data.agent_constraints,
        }

        # Write to YAML file
        filepath = os.path.join(self.scenarios_dir, f"{scenario_id}.yaml")
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_data, f, default_flow_style=False, sort_keys=False)

        # Reload and return
        self._refresh_scenarios()
        created = self._scenario_cache.get(scenario_id)  # type: ignore[union-attr]
        if not created:
            raise ValueError("Failed to create scenario - reload error")
        return created

    def update_scenario(
        self, scenario_id: str, update_data: ScenarioUpdate
    ) -> Scenario:
        """Update an existing scenario and rewrite YAML file."""
        if self._should_refresh_cache():
            self._refresh_scenarios()

        if scenario_id not in self._scenario_cache:  # type: ignore[operator]
            raise ValueError(f"Scenario ID '{scenario_id}' not found")

        existing = self._scenario_cache[scenario_id]  # type: ignore[index]

        # Update fields if provided
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if key == "tags":
                existing.tags = value
            elif hasattr(existing, key):
                setattr(existing, key, value)

        # Prepare updated YAML data
        yaml_data = {
            "scenario_name": existing.name,
            "description": existing.description,
            "difficulty_tier": existing.difficulty_tier,
            "expected_duration": existing.expected_duration,
            "business_parameters": existing.default_params,
            "success_criteria": existing.success_criteria,
            "market_conditions": existing.market_conditions,
            "external_events": existing.external_events,
            "agent_constraints": existing.agent_constraints,
        }

        # Rewrite YAML file
        filepath = os.path.join(self.scenarios_dir, f"{scenario_id}.yaml")
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_data, f, default_flow_style=False, sort_keys=False)

        # Reload
        self._refresh_scenarios()
        updated = self._scenario_cache.get(scenario_id)  # type: ignore[union-attr]
        if not updated:
            raise ValueError("Failed to update scenario - reload error")
        return updated

    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete a scenario by removing its YAML file."""
        if self._should_refresh_cache():
            self._refresh_scenarios()

        if scenario_id not in self._scenario_cache:  # type: ignore[operator]
            return False

        filepath = os.path.join(self.scenarios_dir, f"{scenario_id}.yaml")
        if os.path.exists(filepath):
            os.remove(filepath)

        # Reload cache
        self._refresh_scenarios()
        return scenario_id not in self._scenario_cache  # type: ignore[operator]


# Global scenario service instance
_scenario_service: Optional[ScenarioService] = None


def get_scenario_service() -> ScenarioService:
    """Get the global scenario service instance."""
    global _scenario_service
    if _scenario_service is None:
        _scenario_service = ScenarioService()
    return _scenario_service
