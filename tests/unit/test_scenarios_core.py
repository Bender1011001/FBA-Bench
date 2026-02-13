import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scenarios.curriculum_validator import CurriculumValidator
from scenarios.scenario_framework import ScenarioFramework


class TestCurriculumValidator(unittest.TestCase):
    """Test suite for the CurriculumValidator class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.curriculum_validator = CurriculumValidator()

    def test_curriculum_validator_initialization(self):
        """Test that the curriculum validator initializes correctly."""
        self.assertIsNotNone(self.curriculum_validator)
        self.assertEqual(len(self.curriculum_validator._validation_rules), 0)
        self.assertEqual(len(self.curriculum_validator._curriculum_templates), 0)

    def test_add_validation_rule(self):
        """Test adding a validation rule."""
        rule_data = {
            "name": "Prerequisite Check",
            "description": "Ensure prerequisites are met",
            "condition": "prerequisites_met",
            "severity": "error",
            "message": "Prerequisites not met",
        }

        rule_id = self.curriculum_validator.add_validation_rule(rule_data)

        self.assertIsNotNone(rule_id)
        self.assertIn(rule_id, self.curriculum_validator._validation_rules)
        self.assertEqual(
            self.curriculum_validator._validation_rules[rule_id]["name"],
            "Prerequisite Check",
        )
        self.assertEqual(
            self.curriculum_validator._validation_rules[rule_id]["condition"],
            "prerequisites_met",
        )
        self.assertEqual(
            self.curriculum_validator._validation_rules[rule_id]["severity"], "error"
        )
        self.assertEqual(
            self.curriculum_validator._validation_rules[rule_id]["message"],
            "Prerequisites not met",
        )

    def test_update_validation_rule(self):
        """Test updating a validation rule."""
        rule_data = {
            "name": "Prerequisite Check",
            "description": "Ensure prerequisites are met",
            "condition": "prerequisites_met",
            "severity": "error",
            "message": "Prerequisites not met",
        }

        rule_id = self.curriculum_validator.add_validation_rule(rule_data)

        # Update the rule
        updated_data = {
            "name": "Updated Prerequisite Check",
            "description": "Ensure all prerequisites are met",
            "condition": "all_prerequisites_met",
            "severity": "warning",
            "message": "Some prerequisites not met",
        }

        self.curriculum_validator.update_validation_rule(rule_id, updated_data)

        self.assertEqual(
            self.curriculum_validator._validation_rules[rule_id]["name"],
            "Updated Prerequisite Check",
        )
        self.assertEqual(
            self.curriculum_validator._validation_rules[rule_id]["description"],
            "Ensure all prerequisites are met",
        )
        self.assertEqual(
            self.curriculum_validator._validation_rules[rule_id]["condition"],
            "all_prerequisites_met",
        )
        self.assertEqual(
            self.curriculum_validator._validation_rules[rule_id]["severity"], "warning"
        )
        self.assertEqual(
            self.curriculum_validator._validation_rules[rule_id]["message"],
            "Some prerequisites not met",
        )

    def test_delete_validation_rule(self):
        """Test deleting a validation rule."""
        rule_data = {
            "name": "Prerequisite Check",
            "description": "Ensure prerequisites are met",
            "condition": "prerequisites_met",
            "severity": "error",
            "message": "Prerequisites not met",
        }

        rule_id = self.curriculum_validator.add_validation_rule(rule_data)

        # Delete the rule
        self.curriculum_validator.delete_validation_rule(rule_id)

        self.assertNotIn(rule_id, self.curriculum_validator._validation_rules)

    def test_add_curriculum_template(self):
        """Test adding a curriculum template."""
        template_data = {
            "name": "Beginner Curriculum",
            "description": "Curriculum for beginners",
            "levels": [
                {
                    "name": "Level 1",
                    "description": "Introduction",
                    "prerequisites": [],
                    "objectives": ["Learn basics"],
                    "scenarios": ["scenario1", "scenario2"],
                },
                {
                    "name": "Level 2",
                    "description": "Intermediate",
                    "prerequisites": ["Level 1"],
                    "objectives": ["Learn intermediate concepts"],
                    "scenarios": ["scenario3", "scenario4"],
                },
            ],
        }

        template_id = self.curriculum_validator.add_curriculum_template(template_data)

        self.assertIsNotNone(template_id)
        self.assertIn(template_id, self.curriculum_validator._curriculum_templates)
        self.assertEqual(
            self.curriculum_validator._curriculum_templates[template_id]["name"],
            "Beginner Curriculum",
        )
        self.assertEqual(
            len(self.curriculum_validator._curriculum_templates[template_id]["levels"]),
            2,
        )

    def test_update_curriculum_template(self):
        """Test updating a curriculum template."""
        template_data = {
            "name": "Beginner Curriculum",
            "description": "Curriculum for beginners",
            "levels": [
                {
                    "name": "Level 1",
                    "description": "Introduction",
                    "prerequisites": [],
                    "objectives": ["Learn basics"],
                    "scenarios": ["scenario1", "scenario2"],
                }
            ],
        }

        template_id = self.curriculum_validator.add_curriculum_template(template_data)

        # Update the template
        updated_data = {
            "name": "Updated Beginner Curriculum",
            "description": "Updated curriculum for beginners",
            "levels": [
                {
                    "name": "Level 1",
                    "description": "Introduction",
                    "prerequisites": [],
                    "objectives": ["Learn basics"],
                    "scenarios": ["scenario1", "scenario2"],
                },
                {
                    "name": "Level 2",
                    "description": "Intermediate",
                    "prerequisites": ["Level 1"],
                    "objectives": ["Learn intermediate concepts"],
                    "scenarios": ["scenario3", "scenario4"],
                },
            ],
        }

        self.curriculum_validator.update_curriculum_template(template_id, updated_data)

        self.assertEqual(
            self.curriculum_validator._curriculum_templates[template_id]["name"],
            "Updated Beginner Curriculum",
        )
        self.assertEqual(
            self.curriculum_validator._curriculum_templates[template_id]["description"],
            "Updated curriculum for beginners",
        )
        self.assertEqual(
            len(self.curriculum_validator._curriculum_templates[template_id]["levels"]),
            2,
        )

    def test_delete_curriculum_template(self):
        """Test deleting a curriculum template."""
        template_data = {
            "name": "Beginner Curriculum",
            "description": "Curriculum for beginners",
            "levels": [
                {
                    "name": "Level 1",
                    "description": "Introduction",
                    "prerequisites": [],
                    "objectives": ["Learn basics"],
                    "scenarios": ["scenario1", "scenario2"],
                }
            ],
        }

        template_id = self.curriculum_validator.add_curriculum_template(template_data)

        # Delete the template
        self.curriculum_validator.delete_curriculum_template(template_id)

        self.assertNotIn(template_id, self.curriculum_validator._curriculum_templates)

    def test_validate_curriculum(self):
        """Test validating a curriculum."""
        # Add a validation rule
        rule_data = {
            "name": "Prerequisite Check",
            "description": "Ensure prerequisites are met",
            "condition": "prerequisites_met",
            "severity": "error",
            "message": "Prerequisites not met",
        }

        self.curriculum_validator.add_validation_rule(rule_data)

        # Create a curriculum with valid prerequisites
        valid_curriculum = {
            "name": "Valid Curriculum",
            "levels": [
                {
                    "name": "Level 1",
                    "prerequisites": [],
                    "objectives": ["Learn basics"],
                    "scenarios": ["scenario1"],
                },
                {
                    "name": "Level 2",
                    "prerequisites": ["Level 1"],
                    "objectives": ["Learn intermediate concepts"],
                    "scenarios": ["scenario2"],
                },
            ],
        }

        # Mock the validation function
        with patch.object(
            self.curriculum_validator, "_prerequisites_met"
        ) as mock_prerequisites:
            mock_prerequisites.return_value = True

            # Validate the curriculum
            result = self.curriculum_validator.validate_curriculum(valid_curriculum)

            self.assertTrue(result["valid"])
            self.assertEqual(len(result["errors"]), 0)
            self.assertEqual(len(result["warnings"]), 0)

    def test_validate_curriculum_with_errors(self):
        """Test validating a curriculum with errors."""
        # Add a validation rule
        rule_data = {
            "name": "Prerequisite Check",
            "description": "Ensure prerequisites are met",
            "condition": "prerequisites_met",
            "severity": "error",
            "message": "Prerequisites not met",
        }

        self.curriculum_validator.add_validation_rule(rule_data)

        # Create a curriculum with invalid prerequisites
        invalid_curriculum = {
            "name": "Invalid Curriculum",
            "levels": [
                {
                    "name": "Level 1",
                    "prerequisites": [],
                    "objectives": ["Learn basics"],
                    "scenarios": ["scenario1"],
                },
                {
                    "name": "Level 2",
                    "prerequisites": ["Level 3"],  # Non-existent level
                    "objectives": ["Learn intermediate concepts"],
                    "scenarios": ["scenario2"],
                },
            ],
        }

        # Mock the validation function
        with patch.object(
            self.curriculum_validator, "_prerequisites_met"
        ) as mock_prerequisites:
            mock_prerequisites.return_value = False

            # Validate the curriculum
            result = self.curriculum_validator.validate_curriculum(invalid_curriculum)

            self.assertFalse(result["valid"])
            self.assertGreater(len(result["errors"]), 0)
            self.assertEqual(len(result["warnings"]), 0)

    def test_get_curriculum_template(self):
        """Test getting a curriculum template."""
        template_data = {
            "name": "Beginner Curriculum",
            "description": "Curriculum for beginners",
            "levels": [
                {
                    "name": "Level 1",
                    "description": "Introduction",
                    "prerequisites": [],
                    "objectives": ["Learn basics"],
                    "scenarios": ["scenario1", "scenario2"],
                }
            ],
        }

        template_id = self.curriculum_validator.add_curriculum_template(template_data)

        # Get the template
        retrieved_template = self.curriculum_validator.get_curriculum_template(
            template_id
        )

        self.assertIsNotNone(retrieved_template)
        self.assertEqual(retrieved_template["name"], "Beginner Curriculum")
        self.assertEqual(len(retrieved_template["levels"]), 1)

    def test_get_all_curriculum_templates(self):
        """Test getting all curriculum templates."""
        template1_data = {
            "name": "Beginner Curriculum",
            "description": "Curriculum for beginners",
            "levels": [
                {
                    "name": "Level 1",
                    "description": "Introduction",
                    "prerequisites": [],
                    "objectives": ["Learn basics"],
                    "scenarios": ["scenario1", "scenario2"],
                }
            ],
        }

        template2_data = {
            "name": "Advanced Curriculum",
            "description": "Curriculum for advanced users",
            "levels": [
                {
                    "name": "Level 1",
                    "description": "Advanced concepts",
                    "prerequisites": [],
                    "objectives": ["Learn advanced concepts"],
                    "scenarios": ["scenario3", "scenario4"],
                }
            ],
        }

        self.curriculum_validator.add_curriculum_template(template1_data)
        self.curriculum_validator.add_curriculum_template(template2_data)

        # Get all templates
        all_templates = self.curriculum_validator.get_all_curriculum_templates()

        self.assertEqual(len(all_templates), 2)
        self.assertTrue(any(t["name"] == "Beginner Curriculum" for t in all_templates))
        self.assertTrue(any(t["name"] == "Advanced Curriculum" for t in all_templates))


class TestScenarioFramework(unittest.TestCase):
    """Test suite for the ScenarioFramework class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scenario_framework = ScenarioFramework()

    def test_scenario_framework_initialization(self):
        """Test that the scenario framework initializes correctly."""
        self.assertIsNotNone(self.scenario_framework)
        self.assertEqual(len(self.scenario_framework._scenarios), 0)
        self.assertEqual(len(self.scenario_framework._scenario_categories), 0)
        self.assertEqual(len(self.scenario_framework._scenario_templates), 0)

    def test_create_scenario(self):
        """Test creating a scenario."""
        scenario_data = {
            "name": "Test Scenario",
            "description": "A test scenario",
            "category": "test",
            "parameters": {
                "param1": {
                    "type": "string",
                    "description": "Parameter 1",
                    "default": "default1",
                },
                "param2": {
                    "type": "integer",
                    "description": "Parameter 2",
                    "default": 10,
                },
            },
            "steps": [
                {"name": "Step 1", "description": "First step"},
                {"name": "Step 2", "description": "Second step"},
            ],
            "expected_outcomes": ["Outcome 1", "Outcome 2"],
        }

        scenario_id = self.scenario_framework.create_scenario(scenario_data)

        self.assertIsNotNone(scenario_id)
        self.assertIn(scenario_id, self.scenario_framework._scenarios)
        self.assertEqual(
            self.scenario_framework._scenarios[scenario_id]["name"], "Test Scenario"
        )
        self.assertEqual(
            self.scenario_framework._scenarios[scenario_id]["category"], "test"
        )
        self.assertEqual(
            len(self.scenario_framework._scenarios[scenario_id]["steps"]), 2
        )

    def test_update_scenario(self):
        """Test updating a scenario."""
        scenario_data = {
            "name": "Test Scenario",
            "description": "A test scenario",
            "category": "test",
            "parameters": {
                "param1": {
                    "type": "string",
                    "description": "Parameter 1",
                    "default": "default1",
                },
                "param2": {
                    "type": "integer",
                    "description": "Parameter 2",
                    "default": 10,
                },
            },
            "steps": [
                {"name": "Step 1", "description": "First step"},
                {"name": "Step 2", "description": "Second step"},
            ],
            "expected_outcomes": ["Outcome 1", "Outcome 2"],
        }

        scenario_id = self.scenario_framework.create_scenario(scenario_data)

        # Update the scenario
        updated_data = {
            "name": "Updated Test Scenario",
            "description": "An updated test scenario",
            "category": "updated_test",
            "parameters": {
                "param1": {
                    "type": "string",
                    "description": "Parameter 1",
                    "default": "default1",
                },
                "param2": {
                    "type": "integer",
                    "description": "Parameter 2",
                    "default": 10,
                },
                "param3": {
                    "type": "boolean",
                    "description": "Parameter 3",
                    "default": True,
                },
            },
            "steps": [
                {"name": "Step 1", "description": "First step"},
                {"name": "Step 2", "description": "Second step"},
                {"name": "Step 3", "description": "Third step"},
            ],
            "expected_outcomes": ["Outcome 1", "Outcome 2", "Outcome 3"],
        }

        self.scenario_framework.update_scenario(scenario_id, updated_data)

        self.assertEqual(
            self.scenario_framework._scenarios[scenario_id]["name"],
            "Updated Test Scenario",
        )
        self.assertEqual(
            self.scenario_framework._scenarios[scenario_id]["description"],
            "An updated test scenario",
        )
        self.assertEqual(
            self.scenario_framework._scenarios[scenario_id]["category"], "updated_test"
        )
        self.assertEqual(
            len(self.scenario_framework._scenarios[scenario_id]["parameters"]), 3
        )
        self.assertEqual(
            len(self.scenario_framework._scenarios[scenario_id]["steps"]), 3
        )
        self.assertEqual(
            len(self.scenario_framework._scenarios[scenario_id]["expected_outcomes"]), 3
        )

    def test_delete_scenario(self):
        """Test deleting a scenario."""
        scenario_data = {
            "name": "Test Scenario",
            "description": "A test scenario",
            "category": "test",
            "parameters": {},
            "steps": [],
            "expected_outcomes": [],
        }

        scenario_id = self.scenario_framework.create_scenario(scenario_data)

        # Delete the scenario
        self.scenario_framework.delete_scenario(scenario_id)

        self.assertNotIn(scenario_id, self.scenario_framework._scenarios)

    def test_get_scenario(self):
        """Test getting a scenario."""
        scenario_data = {
            "name": "Test Scenario",
            "description": "A test scenario",
            "category": "test",
            "parameters": {},
            "steps": [],
            "expected_outcomes": [],
        }

        scenario_id = self.scenario_framework.create_scenario(scenario_data)

        # Get the scenario
        retrieved_scenario = self.scenario_framework.get_scenario(scenario_id)

        self.assertIsNotNone(retrieved_scenario)
        self.assertEqual(retrieved_scenario["name"], "Test Scenario")
        self.assertEqual(retrieved_scenario["category"], "test")

    def test_get_scenarios_by_category(self):
        """Test getting scenarios by category."""
        scenario1_data = {
            "name": "Test Scenario 1",
            "description": "A test scenario",
            "category": "test",
            "parameters": {},
            "steps": [],
            "expected_outcomes": [],
        }

        scenario2_data = {
            "name": "Test Scenario 2",
            "description": "Another test scenario",
            "category": "test",
            "parameters": {},
            "steps": [],
            "expected_outcomes": [],
        }

        scenario3_data = {
            "name": "Other Scenario",
            "description": "A scenario in another category",
            "category": "other",
            "parameters": {},
            "steps": [],
            "expected_outcomes": [],
        }

        self.scenario_framework.create_scenario(scenario1_data)
        self.scenario_framework.create_scenario(scenario2_data)
        self.scenario_framework.create_scenario(scenario3_data)

        # Get scenarios by category
        test_scenarios = self.scenario_framework.get_scenarios_by_category("test")
        other_scenarios = self.scenario_framework.get_scenarios_by_category("other")

        self.assertEqual(len(test_scenarios), 2)
        self.assertEqual(len(other_scenarios), 1)
        self.assertTrue(any(s["name"] == "Test Scenario 1" for s in test_scenarios))
        self.assertTrue(any(s["name"] == "Test Scenario 2" for s in test_scenarios))
        self.assertEqual(other_scenarios[0]["name"], "Other Scenario")

    def test_create_scenario_category(self):
        """Test creating a scenario category."""
        category_data = {
            "name": "Test Category",
            "description": "A category for test scenarios",
            "parent_category": None,
        }

        category_id = self.scenario_framework.create_scenario_category(category_data)

        self.assertIsNotNone(category_id)
        self.assertIn(category_id, self.scenario_framework._scenario_categories)
        self.assertEqual(
            self.scenario_framework._scenario_categories[category_id]["name"],
            "Test Category",
        )
        self.assertEqual(
            self.scenario_framework._scenario_categories[category_id]["description"],
            "A category for test scenarios",
        )

    def test_create_scenario_template(self):
        """Test creating a scenario template."""
        template_data = {
            "name": "Test Template",
            "description": "A template for test scenarios",
            "category": "test",
            "parameters": {
                "param1": {
                    "type": "string",
                    "description": "Parameter 1",
                    "default": "default1",
                },
                "param2": {
                    "type": "integer",
                    "description": "Parameter 2",
                    "default": 10,
                },
            },
            "steps": [
                {"name": "Step 1", "description": "First step", "template": True},
                {"name": "Step 2", "description": "Second step", "template": True},
            ],
        }

        template_id = self.scenario_framework.create_scenario_template(template_data)

        self.assertIsNotNone(template_id)
        self.assertIn(template_id, self.scenario_framework._scenario_templates)
        self.assertEqual(
            self.scenario_framework._scenario_templates[template_id]["name"],
            "Test Template",
        )
        self.assertEqual(
            self.scenario_framework._scenario_templates[template_id]["category"], "test"
        )
        self.assertEqual(
            len(self.scenario_framework._scenario_templates[template_id]["steps"]), 2
        )

    def test_create_scenario_from_template(self):
        """Test creating a scenario from a template."""
        template_data = {
            "name": "Test Template",
            "description": "A template for test scenarios",
            "category": "test",
            "parameters": {
                "param1": {
                    "type": "string",
                    "description": "Parameter 1",
                    "default": "default1",
                },
                "param2": {
                    "type": "integer",
                    "description": "Parameter 2",
                    "default": 10,
                },
            },
            "steps": [
                {"name": "Step 1", "description": "First step", "template": True},
                {"name": "Step 2", "description": "Second step", "template": True},
            ],
        }

        template_id = self.scenario_framework.create_scenario_template(template_data)

        # Create a scenario from the template
        scenario_data = {
            "name": "Scenario from Template",
            "description": "A scenario created from a template",
            "template_id": template_id,
            "parameters": {"param1": "custom_value1", "param2": 20},
        }

        scenario_id = self.scenario_framework.create_scenario_from_template(
            scenario_data
        )

        self.assertIsNotNone(scenario_id)
        self.assertIn(scenario_id, self.scenario_framework._scenarios)
        self.assertEqual(
            self.scenario_framework._scenarios[scenario_id]["name"],
            "Scenario from Template",
        )
        self.assertEqual(
            self.scenario_framework._scenarios[scenario_id]["description"],
            "A scenario created from a template",
        )
        self.assertEqual(
            self.scenario_framework._scenarios[scenario_id]["parameters"]["param1"],
            "custom_value1",
        )
        self.assertEqual(
            self.scenario_framework._scenarios[scenario_id]["parameters"]["param2"], 20
        )
        self.assertEqual(
            len(self.scenario_framework._scenarios[scenario_id]["steps"]), 2
        )

    def test_execute_scenario(self):
        """Test executing a scenario."""
        scenario_data = {
            "name": "Test Scenario",
            "description": "A test scenario",
            "category": "test",
            "parameters": {
                "param1": {
                    "type": "string",
                    "description": "Parameter 1",
                    "default": "default1",
                },
                "param2": {
                    "type": "integer",
                    "description": "Parameter 2",
                    "default": 10,
                },
            },
            "steps": [
                {"name": "Step 1", "description": "First step"},
                {"name": "Step 2", "description": "Second step"},
            ],
            "expected_outcomes": ["Outcome 1", "Outcome 2"],
        }

        scenario_id = self.scenario_framework.create_scenario(scenario_data)

        # Mock the scenario execution
        with patch.object(
            self.scenario_framework, "_execute_scenario_steps"
        ) as mock_execute:
            mock_execute.return_value = {
                "status": "success",
                "results": ["Step 1 completed", "Step 2 completed"],
                "outcomes": ["Outcome 1 achieved", "Outcome 2 achieved"],
            }

            # Execute the scenario
            execution_params = {"param1": "custom_value1", "param2": 20}

            result = self.scenario_framework.execute_scenario(
                scenario_id, execution_params
            )

            self.assertEqual(result["status"], "success")
            self.assertEqual(len(result["results"]), 2)
            self.assertEqual(len(result["outcomes"]), 2)
            mock_execute.assert_called_once()

    def test_validate_scenario(self):
        """Test validating a scenario."""
        scenario_data = {
            "name": "Test Scenario",
            "description": "A test scenario",
            "category": "test",
            "parameters": {
                "param1": {
                    "type": "string",
                    "description": "Parameter 1",
                    "default": "default1",
                },
                "param2": {
                    "type": "integer",
                    "description": "Parameter 2",
                    "default": 10,
                },
            },
            "steps": [
                {"name": "Step 1", "description": "First step"},
                {"name": "Step 2", "description": "Second step"},
            ],
            "expected_outcomes": ["Outcome 1", "Outcome 2"],
        }

        scenario_id = self.scenario_framework.create_scenario(scenario_data)

        # Validate the scenario
        result = self.scenario_framework.validate_scenario(scenario_id)

        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)
        self.assertEqual(len(result["warnings"]), 0)

    def test_validate_scenario_with_errors(self):
        """Test validating a scenario with errors."""
        # Create a scenario with missing required fields
        scenario_data = {
            "name": "Invalid Scenario",
            "description": "An invalid scenario",
            "category": "test",
            "parameters": {},
            "steps": [],
            "expected_outcomes": [],
        }

        scenario_id = self.scenario_framework.create_scenario(scenario_data)

        # Manually make the scenario invalid by removing required fields
        self.scenario_framework._scenarios[scenario_id]["name"] = ""

        # Validate the scenario
        result = self.scenario_framework.validate_scenario(scenario_id)

        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 0)
        self.assertEqual(len(result["warnings"]), 0)

    def test_get_scenario_execution_history(self):
        """Test getting scenario execution history."""
        scenario_data = {
            "name": "Test Scenario",
            "description": "A test scenario",
            "category": "test",
            "parameters": {},
            "steps": [],
            "expected_outcomes": [],
        }

        scenario_id = self.scenario_framework.create_scenario(scenario_data)

        # Add some execution history
        execution1 = {
            "timestamp": datetime.now() - timedelta(hours=1),
            "status": "success",
            "parameters": {},
            "results": [],
        }

        execution2 = {
            "timestamp": datetime.now() - timedelta(minutes=30),
            "status": "failure",
            "parameters": {},
            "results": [],
        }

        self.scenario_framework._scenarios[scenario_id]["execution_history"] = [
            execution1,
            execution2,
        ]

        # Get execution history
        history = self.scenario_framework.get_scenario_execution_history(scenario_id)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["status"], "success")
        self.assertEqual(history[1]["status"], "failure")

    def test_generate_scenario_report(self):
        """Test generating a scenario report."""
        scenario_data = {
            "name": "Test Scenario",
            "description": "A test scenario",
            "category": "test",
            "parameters": {},
            "steps": [],
            "expected_outcomes": [],
        }

        scenario_id = self.scenario_framework.create_scenario(scenario_data)

        # Add some execution history
        execution1 = {
            "timestamp": datetime.now() - timedelta(hours=1),
            "status": "success",
            "parameters": {},
            "results": [],
        }

        execution2 = {
            "timestamp": datetime.now() - timedelta(minutes=30),
            "status": "failure",
            "parameters": {},
            "results": [],
        }

        self.scenario_framework._scenarios[scenario_id]["execution_history"] = [
            execution1,
            execution2,
        ]

        # Generate report
        report = self.scenario_framework.generate_scenario_report(scenario_id)

        self.assertIsNotNone(report)
        self.assertIn("scenario", report)
        self.assertIn("execution_history", report)
        self.assertIn("statistics", report)
        self.assertEqual(report["scenario"]["name"], "Test Scenario")
        self.assertEqual(len(report["execution_history"]), 2)
        self.assertIn("total_executions", report["statistics"])
        self.assertIn("success_rate", report["statistics"])
        self.assertEqual(report["statistics"]["total_executions"], 2)
        self.assertEqual(report["statistics"]["success_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
