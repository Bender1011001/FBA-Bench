from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def _clamp01(x: Any, default: float = 0.5) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float(default)
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if not t.startswith("```"):
        return t
    # Remove leading ```lang and trailing ```
    t = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """
    Best-effort extraction of a JSON object from an LLM response.

    Returns a dict on success, else None.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    t = _strip_code_fences(text)
    # Fast path: whole string is JSON
    try:
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass

    # Fallback: find a {...} substring
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = t[start : end + 1]
    try:
        obj = json.loads(candidate)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _parse_money_like(v: Any) -> Optional[float]:
    """
    Convert common money-ish representations to float dollars, best-effort.
    Accepts:
    - numbers
    - strings like "$12.34" or "12.34"
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace("$", "").replace(",", "")
        try:
            return float(s)
        except ValueError:
            return None
    # Money objects usually stringify to "$12.34"
    try:
        return _parse_money_like(str(v))
    except Exception:
        return None


def build_day_digest_text(
    events: Sequence[Dict[str, Any]],
    agent_tool_calls: Sequence[Dict[str, Any]],
    *,
    max_event_lines: int = 20,
) -> str:
    """
    Build a compact, LLM-friendly daily digest from tick-scoped event summaries.
    """
    counts: Dict[str, int] = {}
    units_sold = 0
    revenue = 0.0
    profit = 0.0

    for ev in events or []:
        et = str(ev.get("event_type", "") or "")
        counts[et] = counts.get(et, 0) + 1
        if et == "SaleOccurred":
            data = ev.get("data") or {}
            try:
                units_sold += int(data.get("units_sold", 0) or 0)
            except (TypeError, ValueError):
                pass
            r = _parse_money_like(data.get("total_revenue"))
            p = _parse_money_like(data.get("total_profit"))
            if r is not None:
                revenue += r
            if p is not None:
                profit += p

    # Tool calls summary
    tool_counts: Dict[str, int] = {}
    for tc in agent_tool_calls or []:
        name = str(tc.get("tool_name") or "")
        if not name:
            continue
        tool_counts[name] = tool_counts.get(name, 0) + 1

    lines: List[str] = []
    lines.append("DAILY DIGEST (auto):")
    if units_sold or revenue or profit:
        lines.append(
            f"- Sales: units_sold={units_sold} revenue=${revenue:.2f} profit=${profit:.2f}"
        )
    if counts:
        # Keep a few common event types first, then the rest
        preferred = [
            "SetPriceCommand",
            "ProductPriceUpdated",
            "SaleOccurred",
            "InventoryUpdate",
            "PlaceOrderCommand",
            "AgentDecisionEvent",
        ]
        parts: List[str] = []
        for k in preferred:
            if k in counts:
                parts.append(f"{k}={counts[k]}")
        for k, v in sorted(counts.items()):
            if k in preferred:
                continue
            parts.append(f"{k}={v}")
        lines.append("- Events: " + ", ".join(parts[:16]))
    if tool_counts:
        lines.append(
            "- Your actions: " + ", ".join(f"{k}={v}" for k, v in sorted(tool_counts.items()))
        )

    # Notable events (last N)
    if events:
        lines.append("")
        lines.append("NOTABLE EVENTS (most recent last):")
        for ev in list(events)[-max_event_lines:]:
            et = str(ev.get("event_type", "") or "")
            data = ev.get("data") or {}
            asin = data.get("asin") or data.get("product_id")
            bits: List[str] = []
            if asin:
                bits.append(f"asin={asin}")
            if et == "SaleOccurred":
                bits.append(f"units_sold={data.get('units_sold')}")
                bits.append(f"revenue={data.get('total_revenue')}")
                bits.append(f"profit={data.get('total_profit')}")
            elif et in ("SetPriceCommand", "ProductPriceUpdated"):
                bits.append(f"new_price={data.get('new_price')}")
                bits.append(f"prev_price={data.get('previous_price')}")
            elif et == "InventoryUpdate":
                bits.append(f"new_qty={data.get('new_quantity')}")
                bits.append(f"prev_qty={data.get('previous_quantity')}")
                bits.append(f"reason={data.get('change_reason')}")
            elif et == "PlaceOrderCommand":
                bits.append(f"qty={data.get('quantity')}")
                bits.append(f"max_price={data.get('max_price')}")
                bits.append(f"supplier={data.get('supplier_id')}")

            if not bits:
                # Keep it short, but include something
                try:
                    bits.append(json.dumps(data)[:160])
                except Exception:
                    bits.append(str(data)[:160])
            lines.append(f"- {et}: " + " ".join(str(b) for b in bits if b))

    return "\n".join(lines).strip()


@dataclass
class MemoryItem:
    id: str
    text: str
    importance: float = 0.5
    tags: List[str] = field(default_factory=list)
    created_tick: int = 0
    last_reviewed_tick: int = 0


class LongTermMemoryStore:
    def __init__(
        self,
        *,
        max_items: int = 50,
        prompt_items: int = 10,
        max_chars_per_item: int = 400,
    ) -> None:
        self.max_items = max(1, int(max_items))
        self.prompt_items = max(0, int(prompt_items))
        self.max_chars_per_item = max(40, int(max_chars_per_item))
        self.items: List[MemoryItem] = []
        self.last_consolidated_tick: int = -1

    def render_for_prompt(self) -> str:
        if self.prompt_items <= 0 or not self.items:
            return ""
        # Sort most important first, then most recently reviewed/created.
        items = sorted(
            self.items,
            key=lambda m: (float(m.importance), int(m.last_reviewed_tick), int(m.created_tick)),
            reverse=True,
        )[: self.prompt_items]
        lines = ["LONG-TERM MEMORY (selected):"]
        for m in items:
            lines.append(f"- {m.text}")
        return "\n".join(lines).strip()

    def _dedupe_text(self, text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return True
        for m in self.items:
            if (m.text or "").strip().lower() == t:
                return True
        return False

    def apply_reflection(
        self,
        *,
        tick: int,
        promote: Sequence[Dict[str, Any]],
        forget_ids: Sequence[str],
        max_additions: int,
        max_forgets: int,
    ) -> Tuple[int, int]:
        """
        Apply reflection decisions. Returns (added, removed).
        """
        added = 0
        removed = 0

        # Forget first (free capacity)
        forget_set = [str(i) for i in (forget_ids or []) if str(i).strip()]
        if max_forgets >= 0:
            forget_set = forget_set[: int(max_forgets)]
        if forget_set:
            keep: List[MemoryItem] = []
            for m in self.items:
                if m.id in forget_set:
                    removed += 1
                else:
                    keep.append(m)
            self.items = keep

        # Promote new items
        promos = list(promote or [])
        if max_additions >= 0:
            promos = promos[: int(max_additions)]
        for p in promos:
            if not isinstance(p, dict):
                continue
            text = str(p.get("text") or "").strip()
            if not text:
                continue
            if self._dedupe_text(text):
                continue
            text = text[: self.max_chars_per_item].strip()
            imp = _clamp01(p.get("importance"), default=0.7)
            tags_raw = p.get("tags") or []
            tags: List[str] = []
            if isinstance(tags_raw, list):
                tags = [str(t).strip() for t in tags_raw if str(t).strip()]

            mid = f"mem_{uuid.uuid4().hex[:10]}"
            self.items.append(
                MemoryItem(
                    id=mid,
                    text=text,
                    importance=float(imp),
                    tags=tags,
                    created_tick=int(tick),
                    last_reviewed_tick=int(tick),
                )
            )
            added += 1

        # Enforce capacity (drop lowest-importance oldest)
        if len(self.items) > self.max_items:
            self.items.sort(
                key=lambda m: (float(m.importance), int(m.last_reviewed_tick), int(m.created_tick))
            )
            overflow = len(self.items) - self.max_items
            if overflow > 0:
                self.items = self.items[overflow:]
                removed += overflow

        self.last_consolidated_tick = int(tick)
        return added, removed

    def serialize_for_reflection(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": m.id,
                "text": m.text,
                "importance": float(m.importance),
                "tags": list(m.tags),
                "created_tick": int(m.created_tick),
                "last_reviewed_tick": int(m.last_reviewed_tick),
            }
            for m in self.items
        ]


def build_reflection_prompt(
    *,
    agent_id: str,
    tick: int,
    digest_text: str,
    existing_memories: Sequence[Dict[str, Any]],
    max_items: int,
    max_additions: int,
    max_forgets: int,
) -> str:
    """
    Create a single text prompt requesting a JSON reflection decision.
    """
    safe_existing = list(existing_memories or [])
    existing_json = json.dumps(safe_existing, indent=2)

    return (
        "You are the agent's long-term memory consolidation module.\n"
        "After each simulation day, you must decide what to store in long-term memory and what to forget.\n\n"
        f"AGENT_ID: {agent_id}\n"
        f"DAY_TICK: {int(tick)}\n\n"
        "INPUT:\n"
        f"{digest_text}\n\n"
        "CURRENT LONG-TERM MEMORY (id, importance, tags, text):\n"
        f"{existing_json}\n\n"
        "CONSTRAINTS:\n"
        f"- Max total long-term memories after update: {int(max_items)}\n"
        f"- Max new memories to add today: {int(max_additions)}\n"
        f"- Max memories to forget today: {int(max_forgets)}\n"
        "- New memories should be short, durable, and actionable (strategic rules, stable facts, learned patterns).\n"
        "- Avoid duplicates. If a new memory conflicts with an old one, prefer updating by forgetting the old one and adding a corrected one.\n\n"
        "OUTPUT FORMAT (JSON ONLY):\n"
        "{\n"
        '  "promote": [\n'
        '    {"text": "string", "importance": 0.0, "tags": ["tag1","tag2"]}\n'
        "  ],\n"
        '  "forget": ["mem_id_1", "mem_id_2"]\n'
        "}\n"
    )


__all__ = [
    "LongTermMemoryStore",
    "build_day_digest_text",
    "build_reflection_prompt",
    "extract_json_object",
]

