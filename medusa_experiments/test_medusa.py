import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import yaml

from medusa_experiments.medusa_analyzer import analyze_medusa_run
from medusa_experiments.schema import validate_genome_yaml
from medusa_trainer import MedusaTrainer


class TestMedusaEvolution(unittest.TestCase):
    def setUp(self):
        # Patch the trainer to avoid real LLM and subprocess calls
        self.patcher_llm = patch('medusa_trainer.OpenAI')
        self.patcher_subprocess = patch('medusa_trainer.subprocess.run')
        self.mock_openai = self.patcher_llm.start()
        self.mock_subprocess = self.patcher_subprocess.start()
        
        # Mock OpenAI client
        mock_client = MagicMock()
        self.mock_openai.return_value = mock_client
        
        # Mock LLM response for refinement
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '''
agent:
  name: "Candidate Student Agent Gen 1"
  description: "Improved agent with lower temperature for better decision making."
  agent_class: "benchmarking.agents.unified_agent.UnifiedAgent"
  llm_config:
    client_type: "openrouter"
    model: "xai/grok-beta"
    temperature: 0.5
    max_tokens: 2000
'''
        mock_response.usage = MagicMock()
        mock_response.usage.model_dump.return_value = {'prompt_tokens': 100, 'completion_tokens': 200}
        mock_client.chat.completions.create.return_value = mock_response
        
        # Mock subprocess for benchmark
        self.mock_subprocess.return_value = Mock(returncode=0, stdout='Benchmark success', stderr='')
        
        # Create trainer with mocks
        self.trainer = MedusaTrainer()
        self.genomes_dir = Path('medusa_experiments/genomes')
        self.results_dir = Path('medusa_experiments/results')

    def tearDown(self):
        self.patcher_llm.stop()
        self.patcher_subprocess.stop()

    def test_genesis_validation(self):
        """Test 3: Validate genesis genome."""
        genesis_path = self.genomes_dir / 'student_agent_gen_0.yaml'
        with open(genesis_path) as f:
            content = f.read()
        genome = validate_genome_yaml(content)
        self.assertEqual(genome.agent.name, 'Grok-4 Bot')
        print('Genesis validation: PASSED')

    def test_trainer_init(self):
        """Test 4: Trainer initialization and directory setup."""
        # Clean up any existing fake files
        fake_path = self.genomes_dir / 'student_agent_gen_1.yaml'
        if fake_path.exists():
            fake_path.unlink()
        
        self.assertEqual(self.trainer.elite_gen, 0)
        self.assertTrue(self.genomes_dir.exists())
        self.assertTrue(self.results_dir.exists())
        self.assertTrue(Path('medusa_experiments/logs').exists())
        print('Trainer init and directories: PASSED')

    def test_benchmark_integration(self):
        """Test 5: Benchmark script integration."""
        # Run the benchmark method with mocks
        elite_path = self.genomes_dir / 'student_agent_gen_0.yaml'
        results_path = self.trainer.run_benchmark(elite_path, 0, 'student_agent')
        self.assertTrue(results_path.exists())
        with open(results_path) as f:
            summary = json.load(f)
        self.assertIn('profitability', summary)
        print('Benchmark integration: PASSED')

    def test_generation_detection(self):
        """Test 6: Generation detection and file patterns."""
        # Clean up any existing fake files
        fake_path = self.genomes_dir / 'student_agent_gen_1.yaml'
        if fake_path.exists():
            fake_path.unlink()
        
        elite_gen = self.trainer.get_latest_generation_num()
        self.assertEqual(elite_gen, 0)
        # Create a fake gen 1 to test
        with open(fake_path, 'w') as f:
            yaml.dump({'agent': {'name': 'Fake'}}, f)
        elite_gen = self.trainer.get_latest_generation_num()
        self.assertEqual(elite_gen, 1)
        fake_path.unlink()
        print('Generation detection: PASSED')

    def test_single_evolution_cycle(self):
        """Test 8: Core evolutionary workflow with mocks."""
        # Run baseline
        elite_path = self.genomes_dir / 'student_agent_gen_0.yaml'
        elite_results = self.trainer.run_benchmark(elite_path, 0, 'student_agent')
        elite_profit = self.trainer.parse_profitability(elite_results)
        self.assertEqual(elite_profit, 100.0)

        # Refine to candidate
        elite_results_path = self.results_dir / 'medusa_student_agent_gen_0_summary.json'
        candidate_yaml = self.trainer.refine_agent(0, elite_results_path)
        candidate_path = self.genomes_dir / 'candidate_gen_1.yaml'
        with open(candidate_path, 'w') as f:
            f.write(candidate_yaml)
        genome = validate_genome_yaml(candidate_yaml)
        self.assertEqual(genome.agent.name, 'Candidate Student Agent Gen 1')
        self.assertEqual(genome.agent.llm_config.temperature, 0.5)

        # Test candidate
        candidate_results = self.trainer.run_benchmark(candidate_path, 1, 'candidate')
        # Mock better performance for promotion
        with open(candidate_results, 'w') as f:
            json.dump({'profitability': 110.0, 'total_profit': 110.0}, f)
        candidate_profit = self.trainer.parse_profitability(candidate_results)
        self.assertEqual(candidate_profit, 110.0)

        # Promotion logic (manual check)
        self.assertGreater(candidate_profit, elite_profit * 1.01)  # Triggers promotion

        print('Evolution cycle: PASSED')

    def test_error_handling_missing_api_key(self):
        """Test 9: Error handling for missing OPENROUTER_API_KEY."""
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(ValueError):
                MedusaTrainer()
        print('Missing API key error: PASSED')

    def test_budget_exceeded(self):
        """Test 9: Cost budget enforcement."""
        # Patch budget to exceed
        with patch.object(self.trainer.budget, 'spent', 11.0):
            with self.assertRaises(RuntimeError):
                self.trainer.budget.check_budget('test')
        print('Budget exceeded error: PASSED')

    def test_analyzer_integration(self):
        """Test 10: Analyzer on generated data."""
        # Generate test data
        elite_path = self.genomes_dir / 'student_agent_gen_0.yaml'
        elite_results = self.trainer.run_benchmark(elite_path, 0, 'student_agent')
        
        elite_results_path = self.results_dir / 'medusa_student_agent_gen_0_summary.json'
        candidate_yaml = self.trainer.refine_agent(0, elite_results_path)
        candidate_path = self.genomes_dir / 'candidate_gen_1.yaml'
        with open(candidate_path, 'w') as f:
            f.write(candidate_yaml)
        candidate_results = self.trainer.run_benchmark(candidate_path, 1, 'candidate')
        
        # Mock candidate summary
        candidate_results_path = self.results_dir / 'medusa_candidate_gen_1_summary.json'
        with open(candidate_results_path, 'w') as f:
            json.dump({'financial_summary': {'profitability': 110.0}}, f)
        
        # Run analyzer
        result = analyze_medusa_run()
        self.assertIn('evolutionary_summary', result)
        self.assertGreater(len(result['generation_analysis']), 0)
        print('Analyzer integration: PASSED')

    def test_dry_run_simulation(self):
        """Test 11: Dry-run with mocked responses."""
        # Simulate 2 cycles
        current_gen = 1
        elite_profit = 100.0
        elite_results_path = self.results_dir / 'medusa_student_agent_gen_0_summary.json'
        candidate_yaml = self.trainer.refine_agent(0, elite_results_path)
        candidate_path = self.genomes_dir / f'candidate_gen_{current_gen}.yaml'
        with open(candidate_path, 'w') as f:
            f.write(candidate_yaml)
        
        candidate_results_path = self.trainer.run_benchmark(candidate_path, current_gen, 'candidate')
        # Mock improved
        with open(candidate_results_path, 'w') as f:
            json.dump({'profitability': 110.0}, f)
        candidate_profit = self.trainer.parse_profitability(candidate_results_path)
        
        # Verify promotion
        if candidate_profit > elite_profit * 1.01:
            self.trainer.promote_candidate(candidate_path, current_gen)
            self.assertTrue((self.genomes_dir / f'student_agent_gen_{current_gen}.yaml').exists())
        
        # Verify file patterns
        self.assertTrue(elite_results_path.exists())
        self.assertTrue((self.results_dir / f'medusa_candidate_gen_{current_gen}_summary.json').exists())
        print('Dry-run simulation: PASSED')

    def test_file_structure(self):
        """Test 12: Validate final file structure."""
        expected_files = [
            self.genomes_dir / 'student_agent_gen_0.yaml',
            self.results_dir / 'medusa_student_agent_gen_0_summary.json',
            Path('medusa_experiments/logs/medusa_trainer.log')
        ]
        for file_path in expected_files:
            self.assertTrue(file_path.exists(), f'Missing expected file: {file_path}')
        print('File structure validation: PASSED')

if __name__ == '__main__':
    unittest.main(verbosity=2)
