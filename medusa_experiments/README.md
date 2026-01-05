# Project Medusa

Project Medusa is an autonomous agent evolution framework that employs genetic algorithms to evolve AI agents aimed at maximizing profitability in e-commerce simulations. It leverages the Grok-4 LLM as a mutation engine for intelligent evolution of agent configurations across generations.

## Directory Structure

- `genomes/`: Stores agent configurations (genomes) for each generation of evolution.
- `results/`: Contains performance summaries and evaluation metrics for each generation.
- `logs/`: Holds operational logs from training and evolution processes.
- `README.md`: This documentation file.

## Basic Usage Instructions

1. Ensure the baseline genome is in place at `genomes/student_agent_gen_0.yaml`.
2. Implement and run the MedusaTrainer to initiate the evolution process, which will mutate genomes, evaluate performance, and advance generations.
3. Monitor progress via logs in `logs/` and results in `results/`.
4. For detailed setup, refer to the main project documentation.

This setup prepares the system for Phase 2: MedusaTrainer implementation.
