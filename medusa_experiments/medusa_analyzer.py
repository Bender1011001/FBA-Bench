import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from medusa_experiments.schema import Genome, validate_genome_yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MedusaAnalyzer:
    """
    Enhanced analyzer for Medusa evolutionary experiments.
    Handles new file patterns for elite/candidate agents and summaries,
    provides evolutionary tracking, and maintains backward compatibility.
    """

    def __init__(self, base_dir: Path = Path("medusa_experiments")):
        self.base_dir = base_dir
        self.genomes_dir = base_dir / "genomes"
        self.results_dir = base_dir / "results"
        self.logger = logging.getLogger(__name__)

    def parse_generation(self, filename: str) -> int:
        """
        Parse generation number from new and old file patterns.
        
        Supported patterns:
        - student_agent_gen_X.yaml / candidate_gen_X.yaml -> X
        - medusa_student_agent_gen_X_summary.json / medusa_candidate_gen_X_summary.json -> X
        - Backward: gen_X_summary.json -> X
        
        Returns -1 if no match.
        """
        match = re.search(r'gen_(\d+)', filename)
        if match:
            return int(match.group(1))
        # Backward compatibility for old pattern
        if filename.startswith('gen_') and '_summary.json' in filename:
            parts = filename.split('_')
            if len(parts) >= 2:
                try:
                    return int(parts[1])
                except ValueError:
                    pass
        self.logger.warning(f"Could not parse generation from: {filename}")
        return -1

    def find_files(self) -> Dict[str, List[Tuple[int, Path]]]:
        """
        Find and categorize files by type and generation.
        Returns sorted lists of (generation, path) tuples.
        """
        files = {
            'elite_genomes': [],
            'candidate_genomes': [],
            'elite_summaries': [],
            'candidate_summaries': [],
            'old_summaries': []
        }

        # Ensure directories exist
        self.genomes_dir.mkdir(exist_ok=True)
        self.results_dir.mkdir(exist_ok=True)

        # Elite genomes: student_agent_gen_*.yaml
        for file_path in self.genomes_dir.glob("student_agent_gen_*.yaml"):
            gen = self.parse_generation(file_path.name)
            if gen >= 0:
                files['elite_genomes'].append((gen, file_path))
                self.logger.info(f"Found elite genome: gen {gen} at {file_path}")

        # Candidate genomes: candidate_gen_*.yaml
        for file_path in self.genomes_dir.glob("candidate_gen_*.yaml"):
            gen = self.parse_generation(file_path.name)
            if gen >= 0:
                files['candidate_genomes'].append((gen, file_path))
                self.logger.info(f"Found candidate genome: gen {gen} at {file_path}")

        # Elite summaries: medusa_student_agent_gen_*_summary.json
        for file_path in self.results_dir.glob("medusa_student_agent_gen_*_summary.json"):
            gen = self.parse_generation(file_path.name)
            if gen >= 0:
                files['elite_summaries'].append((gen, file_path))
                self.logger.info(f"Found elite summary: gen {gen} at {file_path}")

        # Candidate summaries: medusa_candidate_gen_*_summary.json
        for file_path in self.results_dir.glob("medusa_candidate_gen_*_summary.json"):
            gen = self.parse_generation(file_path.name)
            if gen >= 0:
                files['candidate_summaries'].append((gen, file_path))
                self.logger.info(f"Found candidate summary: gen {gen} at {file_path}")

        # Backward compatibility: old gen_*_summary.json (treat as elite)
        for file_path in self.results_dir.glob("gen_*_summary.json"):
            gen = self.parse_generation(file_path.name)
            if gen >= 0:
                files['old_summaries'].append((gen, file_path))
                self.logger.info(f"Found old summary (treated as elite): gen {gen} at {file_path}")

        # Sort all lists by generation
        for key in files:
            files[key].sort(key=lambda x: x[0])

        return files

    def load_summary(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load and return JSON summary, or None on error."""
        try:
            with open(file_path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError, FileNotFoundError) as e:
            self.logger.error(f"Failed to load summary {file_path}: {e}")
            return None

    def load_genome_data(self, genome_path: Path) -> Optional[Genome]:
        """Load and validate YAML genome using schema."""
        try:
            with open(genome_path) as f:
                yaml_content = f.read()
            validated = validate_genome_yaml(yaml_content)
            self.logger.info(f"Validated genome {genome_path}")
            return validated
        except Exception as e:
            self.logger.error(f"Failed to validate genome {genome_path}: {e}")
            return None

    def extract_summary_metrics(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key metrics from summary JSON."""
        if not summary:
            return {}
        try:
            return {
                "profitability": summary.get("financial_summary", {}).get("profitability", 0.0),
                "total_revenue": summary.get("financial_summary", {}).get("total_revenue", 0.0),
                "total_cost": summary.get("financial_summary", {}).get("total_cost", 0.0),
                "final_cash": summary.get("financial_summary", {}).get("final_cash", 0.0),
                "orders_fulfilled": summary.get("operational_summary", {}).get("orders_fulfilled", 0),
                "orders_missed": summary.get("operational_summary", {}).get("orders_missed", 0),
                "error_rate": summary.get("agent_performance", {}).get("error_rate", 0.0)
            }
        except Exception as e:
            self.logger.warning(f"Error extracting metrics from summary: {e}")
            return {}

    def compare_genomes_for_mutations(self, prev_genome: Optional[Genome], curr_genome: Optional[Genome]) -> Dict[str, Any]:
        """
        Identify mutations (changes) between consecutive elite genomes.
        Returns dict of changed fields.
        """
        if not prev_genome or not curr_genome:
            return {"mutations": [], "significant": False}
        
        prev_dump = prev_genome.model_dump()
        curr_dump = curr_genome.model_dump()
        
        mutations = []
        for key in set(prev_dump.keys()) | set(curr_dump.keys()):
            if prev_dump.get(key) != curr_dump.get(key):
                mutations.append({
                    "field": key,
                    "previous": prev_dump.get(key),
                    "current": curr_dump.get(key),
                    "type": "changed"
                })
        
        significant = any("temperature" in str(m) or "max_tokens" in str(m) for m in mutations)
        return {"mutations": mutations, "significant": significant, "count": len(mutations)}

    def analyze_elite_progression(self, elite_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze how elite agents evolved over generations."""
        if not elite_data:
            return {"error": "No elite data available"}
        
        df = pd.DataFrame(elite_data)
        if df.empty:
            return {"error": "Empty elite DataFrame"}
        
        progression = {
            "generations": len(df),
            "performance_history": df['profitability'].tolist(),
            "best_generation": int(df.loc[df['profitability'].idxmax(), 'generation']),
            "avg_profitability": float(df['profitability'].mean()),
            "improvement_rates": [],
            "avg_improvement": 0.0,
            "mutation_analysis": []
        }
        
        if len(df) > 1:
            df_sorted = df.sort_values('generation')
            improvements = df_sorted['profitability'].diff().dropna()
            progression["improvement_rates"] = improvements.tolist()
            progression["avg_improvement"] = float(improvements.mean())
            
            # Mutation tracking (assuming genomes in data)
            for i in range(1, len(df_sorted)):
                prev = df_sorted.iloc[i-1].get('genome')
                curr = df_sorted.iloc[i].get('genome')
                if isinstance(prev, dict) and isinstance(curr, dict):
                    mutations = self.compare_genomes_for_mutations(
                        Genome(**prev) if prev else None,
                        Genome(**curr) if curr else None
                    )
                    progression["mutation_analysis"].append({
                        "from_gen": int(df_sorted.iloc[i-1]['generation']),
                        "to_gen": int(df_sorted.iloc[i]['generation']),
                        **mutations
                    })
        
        self.logger.info(f"Elite progression analyzed: {len(elite_data)} generations")
        return progression

    def analyze_candidate_success_rate(self, candidate_data: List[Dict[str, Any]], elite_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate promotion rate of candidates to elite status."""
        if not candidate_data:
            return {"error": "No candidate data available"}
        
        candidate_df = pd.DataFrame(candidate_data)
        elite_df = pd.DataFrame(elite_data) if elite_data else pd.DataFrame()
        
        total_candidates = len(candidate_df)
        successful = 0
        promotions = []
        
        for _, cand in candidate_df.iterrows():
            gen = int(cand['generation'])
            elite_for_gen = elite_df[elite_df['generation'] == gen]
            if not elite_for_gen.empty:
                elite_perf = elite_for_gen['profitability'].iloc[0]
                outperformed = cand['profitability'] > elite_perf
                if outperformed:
                    successful += 1
                    promotions.append({
                        "generation": gen,
                        "candidate_profit": float(cand['profitability']),
                        "elite_profit": float(elite_perf),
                        "improvement": float(cand['profitability'] - elite_perf)
                    })
        
        success_rate = successful / total_candidates if total_candidates > 0 else 0.0
        promotion_rate = len(promotions) / total_candidates if total_candidates > 0 else 0.0
        
        result = {
            "total_candidates": total_candidates,
            "successful_candidates": successful,
            "success_rate": success_rate,
            "promotion_rate": promotion_rate,
            "promotions": promotions,
            "failed_candidates": total_candidates - successful
        }
        
        self.logger.info(f"Candidate success analyzed: {success_rate:.2%} promotion rate")
        return result

    def analyze_performance_trends(self, all_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Track profitability trends across generations using linear regression."""
        if not all_data:
            return {"error": "No data for trend analysis"}
        
        df = pd.DataFrame(all_data)
        if df.empty or len(df) < 2:
            return {"error": "Insufficient data for trends (need at least 2 points)"}
        
        trends = {
            "overall_trend": {},
            "elite_trend": {},
            "candidate_trend": {}
        }
        
        # Overall trend
        x = df['generation'].values
        y = df['profitability'].values
        slope, intercept = np.polyfit(x, y, 1)
        r_value = np.corrcoef(x, y)[0, 1]
        trends["overall_trend"] = {
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": float(r_value ** 2),
            "interpretation": "positive" if slope > 0 else "negative" if slope < 0 else "stable"
        }
        
        # Elite trend
        elite_df = df[df['type'] == 'elite']
        if len(elite_df) >= 2:
            x_elite = elite_df['generation'].values
            y_elite = elite_df['profitability'].values
            slope_e, intercept_e = np.polyfit(x_elite, y_elite, 1)
            r_e = np.corrcoef(x_elite, y_elite)[0, 1]
            trends["elite_trend"] = {
                "slope": float(slope_e),
                "intercept": float(intercept_e),
                "r_squared": float(r_e ** 2)
            }
        
        # Candidate trend
        cand_df = df[df['type'] == 'candidate']
        if len(cand_df) >= 2:
            x_cand = cand_df['generation'].values
            y_cand = cand_df['profitability'].values
            slope_c, intercept_c = np.polyfit(x_cand, y_cand, 1)
            r_c = np.corrcoef(x_cand, y_cand)[0, 1]
            trends["candidate_trend"] = {
                "slope": float(slope_c),
                "intercept": float(intercept_c),
                "r_squared": float(r_c ** 2)
            }
        
        self.logger.info("Performance trends analyzed with linear regression")
        return trends

    def analyze_medusa_run(self) -> Dict[str, Any]:
        """
        Main analysis method. Loads data, performs enhanced evolutionary analysis,
        generates output, prints summary, and creates visualizations.
        Backward compatible with old file patterns.
        """
        self.logger.info("Starting Medusa analysis run")
        
        files = self.find_files()
        if not any(files.values()):
            self.logger.warning("No files found. Ensure genomes/ and results/ contain expected patterns.")
            return {"error": "No data files found"}
        
        data: List[Dict[str, Any]] = []
        elite_data: List[Dict[str, Any]] = []
        candidate_data: List[Dict[str, Any]] = []
        all_data: List[Dict[str, Any]] = []
        
        # Load old summaries (backward compatibility, treat as elite)
        for gen, file_path in files['old_summaries']:
            summary = self.load_summary(file_path)
            metrics = self.extract_summary_metrics(summary)
            if metrics:
                row = {
                    "generation": gen,
                    "type": "elite",
                    "source": "old",
                    **metrics
                }
                data.append(row)
                elite_data.append(row)
                all_data.append(row)
                self.logger.info(f"Loaded old elite data for gen {gen}")
        
        # Load elite genomes and summaries
        for gen, genome_path in files['elite_genomes']:
            genome = self.load_genome_data(genome_path)
            summary_path = self.results_dir / f"medusa_student_agent_gen_{gen}_summary.json"
            summary = self.load_summary(summary_path) if summary_path.exists() else None
            metrics = self.extract_summary_metrics(summary)
            
            row = {
                "generation": gen,
                "type": "elite",
                "genome": genome.model_dump() if genome else None,
                **metrics
            }
            elite_data.append(row)
            all_data.append(row)
            if any(metrics.values()):
                data.append(row)
                self.logger.info(f"Loaded elite data for gen {gen} (profit: {metrics.get('profitability', 'N/A')})")
        
        # Load candidate genomes and summaries
        for gen, genome_path in files['candidate_genomes']:
            genome = self.load_genome_data(genome_path)
            summary_path = self.results_dir / f"medusa_candidate_gen_{gen}_summary.json"
            summary = self.load_summary(summary_path) if summary_path.exists() else None
            metrics = self.extract_summary_metrics(summary)
            
            row = {
                "generation": gen,
                "type": "candidate",
                "genome": genome.model_dump() if genome else None,
                **metrics
            }
            candidate_data.append(row)
            all_data.append(row)
            if any(metrics.values()):
                data.append(row)
                self.logger.info(f"Loaded candidate data for gen {gen} (profit: {metrics.get('profitability', 'N/A')})")
        
        if not data:
            self.logger.error("No valid data loaded after processing files")
            return {"error": "No valid data could be loaded"}
        
        df = pd.DataFrame(data)
        self.logger.info(f"Analysis DataFrame created with {len(df)} rows")
        
        # Perform enhanced analyses
        elite_prog = self.analyze_elite_progression(elite_data)
        cand_success = self.analyze_candidate_success_rate(candidate_data, elite_data)
        perf_trends = self.analyze_performance_trends(all_data)
        
        # Evolutionary summary
        total_gens = int(df['generation'].max() - df['generation'].min() + 1) if not df.empty else 0
        best_perf = float(df['profitability'].max()) if 'profitability' in df and not df.empty else 0.0
        elite_count = len([r for r in data if r.get('type') == 'elite'])
        cand_count = len([r for r in data if r.get('type') == 'candidate'])
        promotion_rate = cand_success.get('promotion_rate', 0.0)
        performance_improvement = elite_prog.get('avg_improvement', 0.0)
        
        evolutionary_summary = {
            "total_generations": total_gens,
            "elite_agents": elite_count,
            "candidates_tested": cand_count,
            "promotion_rate": float(promotion_rate),
            "best_performance": best_perf,
            "performance_improvement": float(performance_improvement)
        }
        
        # Generation analysis timeline
        gen_analysis = []
        unique_gens = sorted(set(df['generation']))
        for gen in unique_gens:
            gen_df = df[df['generation'] == gen]
            gen_info = {"generation": int(gen)}
            
            elite_for_gen = gen_df[gen_df['type'] == 'elite']
            candidates_for_gen = gen_df[gen_df['type'] == 'candidate']
            
            if not elite_for_gen.empty:
                gen_info["elite_performance"] = float(elite_for_gen['profitability'].iloc[0])
            
            if not candidates_for_gen.empty:
                avg_cand_perf = float(candidates_for_gen['profitability'].mean())
                gen_info["candidate_performance"] = avg_cand_perf
                elite_perf = gen_info.get("elite_performance", 0)
                gen_info["promoted"] = bool(len(candidates_for_gen[candidates_for_gen['profitability'] > elite_perf]) > 0)
                gen_info["candidates_tested"] = len(candidates_for_gen)
            
            if gen == 0:
                gen_info["type"] = "genesis"
                gen_info["performance"] = gen_info.get("elite_performance", 0.0)
            
            gen_analysis.append(gen_info)
        
        result = {
            "evolutionary_summary": evolutionary_summary,
            "generation_analysis": gen_analysis,
            "elite_progression": elite_prog,
            "candidate_success": cand_success,
            "performance_trends": perf_trends
        }
        
        # Print summary
        print("--- Enhanced Medusa Experiment Analysis ---")
        print(json.dumps(result, indent=2, default=str))
        
        # Enhanced plotting
        if len(df) > 0 and 'profitability' in df.columns and 'generation' in df.columns:
            sns.set_theme(style="whitegrid")
            fig, axes = plt.subplots(3, 1, figsize=(12, 15), sharex=True)
            fig.suptitle('Project Medusa: Enhanced Evolutionary Performance Over Generations', fontsize=16)
            
            # Plot 1: Elite vs Candidate Profitability
            elite_plot = df[df['type'] == 'elite']
            cand_plot = df[df['type'] == 'candidate']
            sns.lineplot(ax=axes[0], data=elite_plot, x='generation', y='profitability', marker='o', label='Elite', color='green')
            sns.lineplot(ax=axes[0], data=cand_plot, x='generation', y='profitability', marker='s', label='Candidate', color='orange')
            axes[0].set_ylabel('Profitability ($)')
            axes[0].set_title('Elite vs Candidate Profitability Evolution')
            axes[0].legend()
            axes[0].axhline(0, color='r', linestyle='--', linewidth=0.8)
            
            # Plot 2: Error Rate by Type
            if 'error_rate' in df.columns:
                sns.lineplot(ax=axes[1], data=df, x='generation', y='error_rate', hue='type', marker='o')
                axes[1].set_ylabel('Error Rate (%)')
                axes[1].set_title('Error Rate Evolution by Agent Type')
                axes[1].legend(title='Type')
            
            # Plot 3: Overall Trend with Regression Line
            x_all = df['generation'].values
            y_all = df['profitability'].values
            z = np.polyfit(x_all, y_all, 1)
            p = np.poly1d(z)
            axes[2].plot(x_all, y_all, 'o', label='Data')
            axes[2].plot(x_all, p(x_all), "--", label=f'Trend (slope={z[0]:.2f})')
            axes[2].set_xlabel('Generation')
            axes[2].set_ylabel('Profitability ($)')
            axes[2].set_title('Overall Performance Trend')
            axes[2].legend()
            
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            plt.savefig(self.base_dir / "medusa_enhanced_evolution.png", dpi=300, bbox_inches='tight')
            print(f"\nEnhanced visualization saved to 'medusa_enhanced_evolution.png' in {self.base_dir}")
            plt.close()  # Prevent display in non-interactive env
        
        self.logger.info("Medusa analysis completed successfully")
        return result


def analyze_medusa_run():
    """Entry point for running the analyzer as a module."""
    analyzer = MedusaAnalyzer()
    return analyzer.analyze_medusa_run()


if __name__ == "__main__":
    result = analyze_medusa_run()
