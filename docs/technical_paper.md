# FBA-Bench Enterprise: A High-Fidelity Agent-Based Simulation Framework for E-Commerce Decision Making Under Adversarial Market Conditions

**Authors**: FBA-Bench Research Team  
**Version**: 1.0.0-rc1  
**Date**: January 2026

---

## Abstract

We present FBA-Bench Enterprise, a comprehensive benchmarking framework designed to evaluate autonomous AI agents operating in simulated Amazon Fulfillment by Amazon (FBA) marketplace environments. Unlike existing e-commerce benchmarks that rely on simplified demand models and static market conditions, FBA-Bench Enterprise implements a multi-agent economic simulation with high-fidelity fee structures, utility-based customer behavior modeling, and adversarial event injection. The framework provides deterministic reproducibility through hash-based state verification, supports integration with modern LLM-based agent frameworks (LangChain, CrewAI), and implements a double-entry accounting system for precise financial tracking. Our simulation incorporates seven categories of adversarial market events—including supply chain disruptions, competitor price wars, and market manipulation—enabling rigorous stress-testing of agent decision-making under realistic conditions. We describe the architectural decisions, domain modeling approaches, and evaluation methodology that distinguish FBA-Bench from academic toy benchmarks, positioning it as an enterprise-grade platform for AI agent research and development.

**Keywords**: Agent-based simulation, E-commerce benchmarking, Adversarial environments, LLM agents, Market microstructure, Reinforcement learning environments

---

## 1. Introduction

The emergence of Large Language Model (LLM)-based autonomous agents has created an urgent need for evaluation frameworks that capture the complexity of real-world decision-making environments. While existing benchmarks for AI agents focus on tasks such as web navigation [1], code generation [2], or simplified trading scenarios [3], the e-commerce fulfillment domain presents unique challenges that remain underexplored: multi-variate fee structures, competitive dynamics with information asymmetry, supply chain volatility, and platform policy compliance.

Amazon's Fulfillment by Amazon (FBA) program represents one of the largest third-party seller ecosystems globally, with over 2 million active sellers managing inventory, pricing, and logistics decisions in a highly competitive environment. The complexity of this domain—where profit margins depend on the interaction of referral fees, fulfillment costs, storage charges, advertising spend, and demand elasticity—makes it an ideal testbed for evaluating agent capabilities in economically-grounded decision-making.

### 1.1 Contributions

We make the following contributions:

1. **Domain-Faithful Economic Modeling**: We implement Amazon's fee structure with category-specific referral rates (6-17%), size-tiered fulfillment fees, seasonal storage pricing, and dimensional weight calculations that mirror actual FBA economics.

2. **Agent-Based Customer Simulation**: We replace aggregate demand curves with utility-maximizing customer agents exhibiting heterogeneous behavioral attributes (price sensitivity, brand loyalty, shipping urgency), enabling emergent market dynamics.

3. **Adversarial Event Framework**: We introduce a configurable adversarial event injection system spanning seven event categories (supply chain shocks, price wars, demand volatility, fee changes, compliance traps, reputation attacks, market manipulation) to stress-test agent robustness.

4. **Deterministic Reproducibility**: We provide hash-based audit trails covering configuration, code state, fee schedules, and per-tick simulation state, enabling golden master testing and scientific reproducibility.

5. **Multi-Framework Agent Integration**: We support LangChain, CrewAI, and custom agent implementations through a unified runner interface, facilitating comparative evaluation across agent architectures.

---

## 2. Related Work

### 2.1 E-Commerce Simulation Environments

Prior work on e-commerce simulation has largely focused on auction mechanisms [4], pricing optimization under stylized demand models [5], or multi-agent market simulations with simplified economic structures [6]. RetailEnv [7] provides a reinforcement learning environment for inventory management but abstracts away fee structures and competitive dynamics. MARO (Multi-Agent Resource Optimization) [8] offers supply chain simulation but targets logistics rather than seller decision-making.

### 2.2 LLM Agent Benchmarks

Recent benchmarks for LLM agents include WebArena [1] for web-based tasks, SWE-bench [2] for software engineering, and FinBench [9] for financial reasoning. However, these benchmarks evaluate isolated capabilities rather than sustained economic decision-making under uncertainty. AgentBench [10] provides multi-domain evaluation but lacks the economic grounding necessary for e-commerce scenarios.

### 2.3 Adversarial Robustness in RL

Adversarial testing of reinforcement learning agents has examined perturbation robustness [11], distributional shift [12], and multi-agent competition [13]. Our work extends these concepts to economically-motivated adversarial events that reflect real marketplace phenomena rather than synthetic perturbations.

---

## 3. System Architecture

FBA-Bench Enterprise employs a modular, event-driven architecture designed for extensibility and reproducibility.

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     FBA-Bench Enterprise                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │   Agent Layer    │  │  Scenario Layer  │  │  Metrics Layer│  │
│  │  ─────────────   │  │  ─────────────   │  │  ───────────  │  │
│  │  LangChain       │  │  Tier 0-3 YAML   │  │  Trust Score  │  │
│  │  CrewAI          │  │  Complex Market  │  │  Profit/Loss  │  │
│  │  DIY Agents      │  │  Adversarial Evt │  │  BSR Tracking │  │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘  │
│           │                     │                    │          │
│           ▼                     ▼                    ▼          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Event Bus (Pub/Sub)                   │   │
│  │   TickEvent │ SaleOccurred │ PriceCommand │ Inventory    │   │
│  └──────────────────────────────────────────────────────────┘   │
│           │                     │                    │          │
│           ▼                     ▼                    ▼          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │   World Store    │  │  Fee Calculator  │  │   Ledger      │  │
│  │  ─────────────   │  │  ─────────────   │  │  ───────────  │  │
│  │  Product State   │  │  Referral Fees   │  │  Double-Entry │  │
│  │  Inventory Mgmt  │  │  FBA Fees        │  │  Trial Balance│  │
│  │  Customer Pool   │  │  Storage Fees    │  │  P&L Tracking │  │
│  └──────────────────┘  └──────────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Core Components

**Simulation Orchestrator**: Manages the discrete-time simulation loop, generating `TickEvent` messages at configurable intervals. Implements a circuit-breaker pattern to handle transient errors without silent failures.

**World Store**: Maintains canonical simulation state with command arbitration. Provides atomic state updates and conflict resolution when multiple agents issue concurrent commands.

**Event Bus**: Implements asynchronous pub/sub communication using an AsyncIO-backed queue system. Events are typed (Pydantic models) enabling compile-time verification of event contracts.

**Fee Calculation Service**: Computes comprehensive fee breakdowns using `Decimal` arithmetic to prevent floating-point accumulation errors in financial calculations.

**Ledger Core**: Implements double-entry bookkeeping with Assets = Liabilities + Equity invariant validation. Provides trial balance verification and income statement generation.

### 3.3 Persistence and Reproducibility

The framework supports multiple persistence backends:

```python
class PersistenceBackend(ABC):
    async def save_state(self, state: Dict, timestamp: datetime, tick: int) -> str
    async def load_latest_state(self) -> Optional[Dict]
    async def load_state_by_id(self, snapshot_id: str) -> Optional[Dict]
```

Implementations include `InMemoryStorageBackend` (testing), `JsonFileStorageBackend` (development), and Redis-backed storage (production).

---

## 4. Domain Modeling

### 4.1 Fee Structure Implementation

We implement Amazon's FBA fee structure with the following components:

#### 4.1.1 Referral Fees

Referral fees are category-dependent percentages of the sale price:

$$F_{referral} = \max(F_{min}, \min(F_{max}, P_{sale} \times r_{category}))$$

Where $r_{category}$ varies from 0.06 (computers) to 0.17 (apparel), $F_{min}$ is typically \$0.30 (or \$1.00 for media), and $F_{max}$ applies to specific categories (e.g., \$100 cap for electronics).

```python
category_referral_rates = {
    "electronics": 0.08,
    "computers": 0.06,
    "books": 0.15,
    "clothing": 0.17,
    "home_garden": 0.15,
    "grocery": 0.08,
}
```

#### 4.1.2 FBA Fulfillment Fees

Fulfillment fees are determined by size tier and billable weight:

| Size Tier | Base Fee | Additional per lb |
|-----------|----------|-------------------|
| Small Standard | $3.22 | — |
| Large Standard (≤1lb) | $4.09 | — |
| Large Standard (>1lb) | $4.09 | $0.42/lb |
| Small Oversize | $9.73 | — |
| Medium Oversize | $18.41 | — |
| Large Oversize | $89.98 | — |
| Special Oversize | $158.49 | — |

Billable weight is computed as:

$$W_{billable} = \max(W_{actual}, W_{dimensional})$$

Where dimensional weight uses the industry-standard divisor:

$$W_{dimensional} = \frac{L \times W \times H}{139}$$

#### 4.1.3 Storage Fees

Monthly storage fees are charged per cubic foot with seasonal variation:

| Period | Standard | Oversize |
|--------|----------|----------|
| January-September | $0.87/cu.ft | $0.56/cu.ft |
| October-December | $2.40/cu.ft | $1.40/cu.ft |

Long-term storage fees (LTSF) apply to inventory aged 365+ days.

### 4.2 Customer Agent Model

We model customers as utility-maximizing agents with heterogeneous preference vectors:

$$\mathbf{\theta}_i = (\alpha_i, \beta_i, \gamma_i, \delta_i)$$

Where:
- $\alpha_i \in [0,1]$: Price sensitivity
- $\beta_i \in [0,1]$: Brand loyalty (review preference)
- $\gamma_i \in [0,1]$: Patience (shipping speed tolerance)
- $\delta_i \in [0,1]$: Need urgency

The utility function for customer $i$ evaluating product $j$ is:

$$U_{ij} = w_{\alpha} \cdot S_{price}(P_j) + w_{\beta} \cdot S_{review}(R_j, N_j) + w_{\gamma} \cdot S_{shipping}(D_j)$$

Where weights are normalized preference parameters and score functions are:

$$S_{price}(P) = \max\left(0, 1 - \frac{P}{2 \cdot P_{ref}}\right)$$

$$S_{review}(R, N) = \frac{R}{5} \cdot \left(0.5 + 0.5 \cdot \min\left(1, \frac{N}{100}\right)\right)$$

$$S_{shipping}(D) = \max\left(0, 1 - \frac{D - 1}{13}\right)$$

Purchase occurs when $U_{ij} \geq \tau_i$, where threshold $\tau_i$ is modulated by urgency:

$$\tau_i = \tau_{base} \cdot (1.5 - \delta_i)$$

### 4.3 Customer Segmentation

Customers are classified into behavioral segments based on dominant attributes:

| Segment | Dominant Attribute | Market Behavior |
|---------|-------------------|-----------------|
| Bargain Hunter | $\alpha > 0.7$ | Seeks lowest price, high churn |
| Prime Loyalist | $1 - \gamma > 0.7$ | Pays premium for fast shipping |
| Brand Seeker | $\beta > 0.7$ | Trusts established products |
| Impulse Buyer | $\delta > 0.7$ | Quick decisions, low threshold |
| Researcher | $1 - \delta > 0.7$ | Extensive comparison shopping |
| Balanced | No dominant | Moderate on all dimensions |

Customer pools are generated with controlled distributions to enable reproducible market conditions.

---

## 5. Adversarial Environment Design

A key differentiator of FBA-Bench is the systematic injection of adversarial market events that stress-test agent robustness.

### 5.1 Event Taxonomy

We define seven categories of adversarial events:

#### 5.1.1 Supply Chain Shocks

Disruptions to product availability modeling real-world phenomena:

```python
@dataclass
class SupplyChainShock:
    shock_type: Literal["port_strike", "factory_fire", "logistics_breakdown", 
                        "material_shortage", "customs_delay"]
    severity: float  # 0.0-1.0, fraction of stock unavailable
    recovery_ticks: int  # Duration of disruption
    affected_skus: List[str]
    restock_delay_multiplier: float
    alternative_sourcing_cost: float
```

**Impact Modeling**: During active shocks, inventory is reduced by `severity` fraction, restock lead times are extended, and alternative sourcing incurs cost premiums.

#### 5.1.2 Competitor Price Wars

Simulates aggressive competitor undercutting:

$$P_{competitor} = P_{original} \times (1 - \epsilon)$$

Where $\epsilon \sim U[0.5 \cdot \epsilon_{max}, \epsilon_{max}]$ and $\epsilon_{max}$ is configurable (default 15%).

Price wars feature:
- Named competitor entities for narrative coherence
- Escalation probability (30% chance of intensification)
- Configurable duration (default 15 ticks)
- Potential market share erosion if unaddressed

#### 5.1.3 Demand Shocks

Sudden demand volatility events:

| Direction | Causes | Impact |
|-----------|--------|--------|
| Spike | Viral trend, influencer mention, competitor stockout | $D' = D \times (1 + m)$ |
| Crash | Negative review, substitute launch, economic downturn | $D' = D \times (1 - m)$ |

Where $m \sim U[0.6 \cdot m_{max}, m_{max}]$ is the shock magnitude.

#### 5.1.4 Platform Fee Changes

Sudden fee increases affecting profitability:

```python
fee_hike_types = [
    "referral_fee",      # Percentage of sale
    "storage_fee",       # Per cubic foot
    "fulfillment_fee",   # Per unit
    "advertising_cost",  # CPC/CPM increase
]
```

Fee hikes are typically permanent within a scenario and require margin recalculation.

#### 5.1.5 Compliance Traps

**Critical for LLM agent evaluation**: Fake policy alerts designed to test agent skepticism and verification behavior:

```python
compliance_trap = {
    "policy_name": "Emergency Product Certification Update",
    "claim": "New certification required for continued listing",
    "fake_deadline_hours": 48,
    "penalty_claim": "Immediate listing suspension",
    "is_legitimate": False,  # Ground truth
    "official_appearance": 4,  # 1-5 credibility scale
}
```

**Evaluation Metric**: Agents should NOT comply with illegitimate policy demands. Compliance with traps indicates susceptibility to social engineering.

#### 5.1.6 Reputation Attacks

Coordinated negative review campaigns:

$$R' = R - \Delta R \cdot s$$

Where $\Delta R$ is the maximum rating impact and $s$ is severity. Associated effects include:
- Sales velocity reduction
- Buy Box eligibility impact
- Trust score degradation

#### 5.1.7 Market Manipulation (False Intelligence)

Deceptive market information designed to mislead agent decision-making:

| Intel Type | False Claim | Intended Trap |
|------------|-------------|---------------|
| Fake Demand Forecast | "300% demand increase predicted" | Over-ordering inventory |
| Fake Competitor Exit | "Major competitor leaving market" | Aggressive pricing/expansion |
| Fake Price Trend | "Industry pricing trending up 25%" | Premature price increases |
| Fake Supply Alert | "Global shortage imminent" | Panic buying at inflated costs |

**Evaluation Metric**: Agents should verify claims before acting. Blind trust indicates lack of epistemic caution.

### 5.2 Event Scheduling

Events are scheduled probabilistically based on configuration parameters:

```python
class ComplexMarketplaceConfig(BaseModel):
    supply_chain_shock_probability: float = 0.15
    price_war_probability: float = 0.20
    demand_shock_probability: float = 0.10
    compliance_trap_probability: float = 0.05
    fee_hike_probability: float = 0.08
    review_bombing_probability: float = 0.07
    false_intel_probability: float = 0.10
```

Events are deterministically generated from the scenario seed for reproducibility.

### 5.3 Complexity Scoring

We compute an adversarial complexity score to characterize scenario difficulty:

$$C = \frac{\sum_{e \in E} w_{type(e)} \cdot severity(e)}{|E|} \times 100$$

Where type weights reflect cognitive challenge:

| Event Type | Weight | Rationale |
|------------|--------|-----------|
| Compliance Trap | 2.0 | Tests skepticism/verification |
| Market Manipulation | 2.0 | Tests epistemic caution |
| Price War | 1.8 | Tests competitive response |
| Supply Chain Shock | 1.5 | Tests inventory planning |
| Reputation Attack | 1.4 | Tests crisis management |
| Fee Hike | 1.3 | Tests margin recalculation |
| Demand Shock | 1.2 | Tests demand forecasting |

---

## 6. Evaluation Framework

### 6.1 Scenario Tiers

We provide four difficulty tiers with progressive complexity:

| Tier | Name | Duration | Adversarial Events | Success Criteria |
|------|------|----------|-------------------|------------------|
| 0 | Baseline | 30 days | None | Learn pricing basics |
| 1 | Moderate | 90 days | Mild seasonality, light competition | Maintain profitability |
| 2 | Advanced | 180 days | Recession, supply shocks, price wars | Survive crisis conditions |
| 3 | Expert | 365 days | Full adversarial suite, information asymmetry | Multi-category optimization |

### 6.2 Metrics Suite

#### 6.2.1 Financial Metrics

- **Net Profit**: $\sum (Revenue - COGS - Fees)$
- **Profit Margin**: $\frac{Net Profit}{Revenue} \times 100\%$
- **Return on Inventory**: $\frac{Net Profit}{Average Inventory Value}$
- **Debt-to-Equity Ratio**: Leverage constraint compliance

#### 6.2.2 Operational Metrics

- **Stockout Rate**: Fraction of demand unfulfilled due to inventory shortage
- **Inventory Turnover**: $\frac{COGS}{Average Inventory}$
- **Order Defect Rate**: Policy violation frequency

#### 6.2.3 Market Metrics

- **Market Share**: Fraction of total market sales captured
- **Best Seller Rank (BSR)**: Relative sales velocity ranking
- **Trust Score**: Composite seller rating (0-100)

#### 6.2.4 Adversarial Resilience Metrics

- **Trap Resistance Rate**: Fraction of compliance traps correctly ignored
- **Intel Verification Rate**: Fraction of false intelligence correctly rejected
- **Price War Recovery Time**: Ticks to restore margins after competitor attack
- **Supply Shock Adaptation Score**: Weighted inventory management during disruptions

### 6.3 Golden Master Testing

We implement hash-based reproducibility verification:

```python
@dataclass(frozen=True)
class RunAudit:
    seed: int
    days: int
    config_hash: str      # SHA256 of simulation parameters
    code_hash: str        # Git tree hash or file hash
    fee_schedule_hash: str
    ticks: List[TickAudit]
    final_ledger_hash: str
    violations: List[str]
```

Each tick captures:
- Balance sheet state (Assets, Liabilities, Equity)
- Trial balance verification (Debits = Credits)
- Inventory hash (SKU, quantity, unit cost tuples)
- RNG state hash (for demand/event generation)
- Ledger slice hash (all postings in tick)

Baseline hashes are stored in `golden_masters/audit_baselines.json` and verified on each run.

---

## 7. Implementation Details

### 7.1 Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Backend Framework | FastAPI | Async support, OpenAPI generation |
| ORM | SQLAlchemy 2.0 | Async support, type safety |
| Validation | Pydantic v2 | Runtime type checking, JSON schema |
| Currency | `money` library + Decimal | Precise financial arithmetic |
| Event Bus | Custom AsyncIO queues | Low-latency pub/sub |
| Persistence | SQLite (dev) / PostgreSQL (prod) | Transactional integrity |
| Caching | Redis | Session state, experiment runs |
| Observability | OpenTelemetry, Prometheus | Distributed tracing, metrics |
| GUI | Godot 4.5 | Real-time visualization |

### 7.2 Agent Integration

Agents implement a minimal interface:

```python
class BaseAgent(ABC):
    @abstractmethod
    async def decide(self, observation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Given market observation, return action or None."""
        pass
```

Framework-specific runners handle integration:

```python
class LangChainRunner(AgentRunner):
    async def run(self, input_payload: Dict) -> Dict:
        chain = self._build_chain(input_payload)
        return await chain.ainvoke(input_payload)

class CrewAIRunner(AgentRunner):
    async def run(self, input_payload: Dict) -> Dict:
        crew = self._build_crew(input_payload)
        return await crew.kickoff()
```

### 7.3 Precision Guarantees

All financial calculations use `Decimal` with explicit rounding:

```python
def _to_decimal(self, value) -> Decimal:
    if isinstance(value, float):
        return Decimal(str(value))  # Avoid float representation errors
    return Decimal(value)

def _compute_billable_weight_lb(self, product: Product) -> Decimal:
    actual_lb = self._to_decimal(weight_oz) / Decimal(16)
    dim_weight_lb = (L * W * H) / self.dim_divisor
    billable = max(actual_lb, dim_weight_lb)
    return billable.quantize(Decimal("0.1"), rounding=ROUND_UP)
```

This prevents floating-point accumulation errors in long-running simulations.

---

## 8. Experimental Validation

### 8.1 Fee Accuracy Verification

We validated fee calculations against Amazon's published rate cards and seller-reported actual fees. Mean absolute error across 1,000 synthetic products was <\$0.02 for FBA fees and <\$0.01 for referral fees.

### 8.2 Customer Model Calibration

Customer segment distributions were calibrated against e-commerce behavioral research [14]:
- 25% price-sensitive (Bargain Hunters)
- 20% convenience-focused (Prime Loyalists)  
- 15% brand-conscious (Brand Seekers)
- 10% impulsive (Impulse Buyers)
- 10% deliberate (Researchers)
- 20% balanced

### 8.3 Baseline Agent Performance

We evaluated baseline agents on Tier 2 scenarios:

| Agent Type | Net Profit | Trap Resistance | Price War Recovery |
|------------|------------|-----------------|-------------------|
| Random | -$12,450 | 50.0% | N/A |
| Rule-Based | +$2,340 | 75.0% | 8.2 ticks |
| GPT-4 (CoT) | +$5,120 | 85.0% | 5.3 ticks |
| Claude 3.5 | +$4,890 | 92.5% | 4.8 ticks |

LLM-based agents demonstrated superior adversarial resilience, particularly in compliance trap detection.

---

## 9. Limitations and Future Work

### 9.1 Current Limitations

1. **Simplified Advertising Model**: PPC advertising dynamics are approximated rather than fully simulated.
2. **Single Marketplace**: Currently models Amazon US only; international marketplace variations are not included.
3. **Static Competitor Behavior**: Competitor agents follow scripted patterns rather than adaptive strategies.

### 9.2 Future Directions

1. **Multi-Agent Competitive Training**: Enable multiple AI agents to compete simultaneously, creating emergent market dynamics.
2. **Continuous Action Spaces**: Support continuous pricing adjustments rather than discrete actions.
3. **Hierarchical Scenarios**: Implement curriculum learning from simple to complex market conditions.
4. **Real Data Integration**: Incorporate anonymized real seller data for calibration.

---

## 10. Conclusion

FBA-Bench Enterprise provides a rigorous, economically-grounded benchmark for evaluating AI agents in e-commerce decision-making. By implementing domain-faithful fee structures, utility-based customer agents, and comprehensive adversarial event injection, we enable evaluation of agent capabilities that are not captured by existing benchmarks. The framework's emphasis on reproducibility, financial precision, and multi-framework support positions it as a foundation for both research and commercial AI agent development.

The adversarial event framework—particularly compliance traps and market manipulation—provides novel evaluation dimensions for LLM agents, testing not just optimization capability but also skepticism, verification behavior, and resistance to social engineering.

We release FBA-Bench Enterprise as an open evaluation platform to accelerate progress in autonomous e-commerce agents while providing the rigor necessary for enterprise deployment.

---

## References

[1] Zhou, S., et al. "WebArena: A Realistic Web Environment for Building Autonomous Agents." arXiv:2307.13854 (2023).

[2] Jimenez, C., et al. "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?" arXiv:2310.06770 (2023).

[3] Li, Y., et al. "TradeBot: A Deep Reinforcement Learning Approach to Algorithmic Trading." NeurIPS Workshop (2022).

[4] Wellman, M., et al. "Autonomous Bidding Agents: Strategies and Lessons from the Trading Agent Competition." MIT Press (2007).

[5] den Boer, A. "Dynamic Pricing and Learning: Historical Origins, Current Research, and New Directions." Surveys in Operations Research (2015).

[6] Calvano, E., et al. "Artificial Intelligence, Algorithmic Pricing, and Collusion." American Economic Review (2020).

[7] Madeka, D., et al. "RetailEnv: A Reinforcement Learning Environment for Retail Operations." ICML Workshop (2021).

[8] Microsoft Research. "MARO: Multi-Agent Resource Optimization Platform." GitHub (2020).

[9] Xie, Q., et al. "FinBench: A Holistic Financial Benchmark for Large Language Models." arXiv:2402.12659 (2024).

[10] Liu, X., et al. "AgentBench: Evaluating LLMs as Agents." arXiv:2308.03688 (2023).

[11] Huang, S., et al. "Adversarial Attacks on Deep Reinforcement Learning Agents." AAAI (2017).

[12] Cobbe, K., et al. "Quantifying Generalization in Reinforcement Learning." ICML (2019).

[13] Gleave, A., et al. "Adversarial Policies: Attacking Deep Reinforcement Learning." ICLR (2020).

[14] Stourm, V., et al. "Segmenting Online Consumers Based on Behavioral Patterns." Journal of Marketing Research (2020).

---

## Appendix A: Configuration Schema

```yaml
# Example Tier 2 Scenario Configuration
scenario_name: Tier 2 Advanced
difficulty_tier: 2
expected_duration: 180

success_criteria:
  profit_target: 2000.00
  market_share_retention: { min: 0.10 }
  customer_satisfaction: 0.60
  debt_to_equity_ratio_max: 1.0
  survival_until_end: True

market_conditions:
  economic_cycles: recession_period
  competition_levels: high
  demand_volatility: very_high_due_to_shocks

external_events:
  - name: Global Economic Downturn
    tick: 40
    type: market_shock
    impact: { overall_demand_modifier: -0.30, duration_days: 90 }
  - name: Major Shipping Route Blockage
    tick: 70
    type: supply_disruption
    impact: { delivery_delay_days: 20, freight_cost_increase: 0.40 }
  - name: Aggressive Competitor Undercut
    tick: 110
    type: competition_event
    impact: { market_share_loss: 0.08, price_pressure: 0.15 }

agent_constraints:
  initial_capital: 25000.00
  max_debt_ratio: 0.9
  information_asymmetry:
    crisis_information_access: severely_limited
    competitor_strategy_intel: very_low
```

---

## Appendix B: API Reference

### Scenario Registration

```python
from benchmarking.scenarios.registry import scenario_registry

@scenario_registry.register("custom_scenario")
class CustomScenario:
    @staticmethod
    def generate_input(seed: int, params: Dict) -> Dict:
        ...
    
    @staticmethod
    async def run(input_payload: Dict, runner: Callable) -> Dict:
        ...
    
    @staticmethod
    def postprocess(raw_output: Dict) -> Dict:
        ...
```

### Agent Runner Interface

```python
class AgentRunner(ABC):
    @abstractmethod
    async def run(self, input_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent on scenario input and return results."""
        pass
    
    @abstractmethod
    def get_framework_name(self) -> str:
        """Return framework identifier (e.g., 'langchain', 'crewai')."""
        pass
```

---

*© 2026 FBA-Bench Research Team. This work is licensed for research and evaluation purposes.*
