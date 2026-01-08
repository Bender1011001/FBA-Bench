from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# ---- Realtime / Simulation Snapshot ----

SimStatus = Literal["idle", "running", "stopped"]


class AgentSnapshot(BaseModel):
    slug: str = Field(..., description="Agent identifier")
    display_name: str = Field(..., description="Human friendly name")
    state: str = Field(..., description="Agent state string")
    last_reasoning: Optional[str] = Field(None, description="Last chain-of-thought reasoning")
    last_tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Recent tool uses")
    llm_usage: Dict[str, Any] = Field(default_factory=dict, description="Token usage stats")
    financials: Dict[str, float] = Field(default_factory=dict, description="Cash, inventory value, net profit")
    recent_events: List[Dict[str, Any]] = Field(default_factory=list, description="Recent relevant events")

    class Config:
        extra = "ignore"


class KpiSnapshot(BaseModel):
    revenue: float = Field(..., ge=0.0, description="Total revenue (float)")
    profit: float = Field(..., description="Total profit (float)")
    units_sold: int = Field(..., ge=0, description="Total units sold")

    @classmethod
    def from_financials(cls, fin: Dict[str, Any]) -> "KpiSnapshot":
        return cls(
            revenue=float(fin.get("total_revenue", 0.0) or 0.0),
            profit=float(fin.get("total_profit", 0.0) or 0.0),
            units_sold=int(fin.get("total_units_sold", 0) or 0),
        )


class CompetitorSnapshot(BaseModel):
    asin: str
    price: str
    bsr: Optional[int]
    sales_velocity: Optional[int]
    inventory: int = 0
    is_out_of_stock: bool = False

    class Config:
        extra = "ignore"


class SimulationSnapshot(BaseModel):
    status: SimStatus = Field(..., description="Simulation status")
    tick: int = Field(..., ge=0)
    kpis: KpiSnapshot
    agents: List[AgentSnapshot] = Field(default_factory=list)
    competitors: List[CompetitorSnapshot] = Field(default_factory=list, description="Competitor landscape")
    timestamp: datetime = Field(..., description="UTC ISO timestamp")

    @classmethod
    def from_dashboard_data(cls, raw: Dict[str, Any], status: str) -> "SimulationSnapshot":
        if not raw:
            return cls._default(status)
            
        # Map KPIs
        fin = raw.get("financial_summary", {}) or {}
        kpis = KpiSnapshot.from_financials(fin)

        # Map Agents
        agents_raw = raw.get("agents", {}) or {}
        agents_list = []
        
        # Normalize dict vs list input
        items = []
        if isinstance(agents_raw, dict):
             items = [(slug, meta) for slug, meta in agents_raw.items()]
        elif isinstance(agents_raw, list):
             items = [(str(a.get("slug", "agent")), a) for a in agents_raw]

        for slug, meta in items:
            if not isinstance(meta, dict):
                meta = {}
            agents_list.append(
                AgentSnapshot(
                    slug=str(slug),
                    display_name=str(meta.get("display_name", slug)),
                    state=str(meta.get("state", "unknown")),
                    last_reasoning=str(meta.get("last_reasoning", "")),
                    last_tool_calls=meta.get("last_tool_calls", []),
                    llm_usage=meta.get("llm_usage", {}),
                    financials=meta.get("financials", {}),
                    recent_events=meta.get("recent_events", []),
                )
            )

        # Map Competitors
        comps_raw = raw.get("competitors", {}) or {}
        comps_list = []
        if isinstance(comps_raw, dict):
            for asin, cdata in comps_raw.items():
                comps_list.append(CompetitorSnapshot(
                    asin=str(asin),
                    price=str(cdata.get("price", "0.00")),
                    bsr=cdata.get("bsr"),
                    sales_velocity=cdata.get("sales_velocity"),
                    inventory=int(cdata.get("inventory", 0)),
                    is_out_of_stock=bool(cdata.get("is_out_of_stock", False))
                ))

        return cls(
            status=status,
            tick=int(raw.get("current_tick", 0)),
            kpis=kpis,
            agents=agents_list,
            competitors=comps_list,
            timestamp=datetime.now(timezone.utc),
        )

    @classmethod
    def _default(cls, status: str = "idle") -> "SimulationSnapshot":
        from datetime import datetime, timezone
        return cls(
            status=status,
            tick=0,
            kpis=KpiSnapshot(revenue=0.0, profit=0.0, units_sold=0),
            agents=[],
            competitors=[],
            timestamp=datetime.now(timezone.utc),
        )


# ---- Realtime / Recent Events ----


class RecentEventsResponse(BaseModel):
    events: List[Dict[str, Any]] = Field(default_factory=list)
    event_type: Optional[str] = Field(
        None, description="Filter applied (sales|commands|...)"
    )
    limit: int = Field(..., ge=1, le=100)
    total_returned: int = Field(..., ge=0)
    timestamp: datetime
    filtered: bool
    since_tick: Optional[int] = Field(None, ge=0)
