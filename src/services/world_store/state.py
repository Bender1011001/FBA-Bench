"""
State management module for WorldStore.
Handles canonical product state, supplier catalog, and related queries/mutations.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from money import Money

from .models import ProductState

logger = logging.getLogger(__name__)


class WorldStateManager:
    """
    Manages canonical state for products and suppliers in WorldStore.

    Encapsulates storage, queries, and mutations for product states and supplier catalog.
    Ensures consistency and provides back-compat helpers for tests.
    """

    def __init__(self):
        # Canonical state storage
        self._product_state: Dict[str, ProductState] = {}
        # Supplier catalog (optional, keyed by supplier_id)
        self._supplier_catalog: Dict[str, Any] = {}

    # State Query Interface

    def get_product_price(self, asin: str) -> Optional[Money]:
        """Get canonical price for a product."""
        state = self._product_state.get(asin)
        return state.price if state else None

    def get_product_state(self, asin: str) -> Optional[ProductState]:
        """Get complete product state."""
        return self._product_state.get(asin)

    def get_all_product_states(self) -> Dict[str, ProductState]:
        """Get all product states (read-only copy)."""
        return self._product_state.copy()

    def get_product_inventory_quantity(self, asin: str) -> int:
        """Get current inventory quantity for a product."""
        state = self._product_state.get(asin)
        return state.inventory_quantity if state else 0

    def get_product_cost_basis(self, asin: str) -> Money:
        """Get current cost basis for a product."""
        state = self._product_state.get(asin)
        return state.cost_basis if state else Money.zero()

    # Supplier catalog helpers

    def set_supplier_catalog(self, catalog: list[Dict[str, Any]]) -> None:
        """
        Store supplier catalog in the world store for downstream services.
        Expects a list of dicts that include at minimum supplier_id and lead_time (ticks).
        """
        by_id: Dict[str, Any] = {}
        try:
            for entry in catalog or []:
                sid = str(entry.get("supplier_id", "")).strip()
                if not sid:
                    continue
                by_id[sid] = dict(entry)
        except (TypeError, AttributeError):
            by_id = {}

        self._supplier_catalog = by_id

    def get_supplier_catalog(self) -> Dict[str, Any]:
        """Return the supplier catalog keyed by supplier_id."""
        return getattr(self, "_supplier_catalog", {}) or {}

    def get_supplier_lead_time(self, supplier_id: str) -> Optional[int]:
        """
        Return the lead_time (in ticks) for a supplier if present in the catalog.
        """
        try:
            catalog = self.get_supplier_catalog()
            entry = catalog.get(str(supplier_id))
            if not entry:
                return None
            lt = entry.get("lead_time")
            if lt is None:
                return None
            return max(0, int(lt))
        except (TypeError, AttributeError, ValueError):
            return None

    # Marketing visibility helpers

    def get_marketing_visibility(self, asin: str) -> float:
        """
        Return current marketing visibility multiplier for an ASIN.
        1.0 = neutral baseline, >1.0 increases demand proportionally.
        """
        state = self._product_state.get(asin)
        if not state:
            return 1.0
        try:
            vis = float(state.metadata.get("marketing_visibility", 1.0))
        except (TypeError, AttributeError, ValueError):
            vis = 1.0
        # Bound visibility to a reasonable range [0.1, 5.0] to avoid instabilities
        return max(0.1, min(5.0, vis))

    def set_marketing_visibility(self, asin: str, visibility: float) -> None:
        """
        Set marketing visibility multiplier for an ASIN in canonical state.
        Bounds value to [0.1, 5.0] and updates metadata.
        """
        v = max(0.1, min(5.0, float(visibility)))
        state = self._product_state.get(asin)
        if not state:
            # Initialize a stub product with zero price/inventory if it doesn't exist yet
            self._product_state[asin] = ProductState(
                asin=asin,
                price=Money.zero(),
                inventory_quantity=0,
                cost_basis=Money.zero(),
                last_updated=datetime.now(),
                last_agent_id="system_marketing",
                last_command_id="marketing_visibility_init",
                version=1,
                metadata={"marketing_visibility": v},
            )
            return
        state.metadata["marketing_visibility"] = v
        state.last_updated = datetime.now()

    # Reputation (Customer Service) helpers

    def get_reputation_score(self, asin: str) -> float:
        """
        Return current customer reputation score for an ASIN in [0.0, 1.0].
        Defaults to 0.7 when unknown.
        """
        state = self._product_state.get(asin)
        if not state:
            return 0.7
        try:
            rep = float(state.metadata.get("reputation_score", 0.7))
        except (TypeError, AttributeError, ValueError):
            rep = 0.7
        return max(0.0, min(1.0, rep))

    def set_reputation_score(self, asin: str, score: float) -> None:
        """
        Set reputation score for an ASIN, clamped to [0.0, 1.0].
        Creates product stub if needed.
        """
        s = max(0.0, min(1.0, float(score)))
        state = self._product_state.get(asin)
        if not state:
            self._product_state[asin] = ProductState(
                asin=asin,
                price=Money.zero(),
                inventory_quantity=0,
                cost_basis=Money.zero(),
                last_updated=datetime.now(),
                last_agent_id="system_reputation",
                last_command_id="reputation_init",
                version=1,
                metadata={"reputation_score": s},
            )
            return
        state.metadata["reputation_score"] = s
        state.last_updated = datetime.now()

    # Direct state mutation helpers for tests/fixtures

    def set_product_state(self, product_id: str, state: ProductState) -> None:
        """
        Back-compat helper used by tests to inject a ProductState directly.

        Args:
            product_id: Alias for ASIN used by tests.
            state: ProductState instance to set as canonical.
        """
        try:
            asin = str(getattr(state, "asin", "") or product_id)
        except (TypeError, AttributeError):
            asin = str(product_id)
        # Ensure last_updated is present
        if not getattr(state, "last_updated", None):
            try:
                state.last_updated = datetime.utcnow()
            except (TypeError, AttributeError):
                pass
        self._product_state[asin] = state

    # Administrative Interface

    def initialize_product(
        self,
        asin: str,
        initial_price: Money,
        initial_inventory: int = 0,
        initial_cost_basis: Money = Money.zero(),
    ) -> bool:
        """
        Initialize a product with starting state.

        Used during simulation setup to establish baseline state.
        Returns False if product already exists.
        """
        if asin in self._product_state:
            return False

        self._product_state[asin] = ProductState(
            asin=asin,
            price=initial_price,
            inventory_quantity=initial_inventory,
            cost_basis=initial_cost_basis,
            last_updated=datetime.now(),
            last_agent_id="system",
            last_command_id="initialization",
            version=1,
        )

        logger.info(
            f"Initialized product state: asin={asin}, price={initial_price}, inventory={initial_inventory}, cost={initial_cost_basis}"
        )
        return True

    def load_state_from_dict(self, state_data: Dict[str, Any]) -> None:
        """Load and populate state from a dictionary of serializable states."""
        self._product_state.clear()
        for asin, product_data in state_data.items():
            self._product_state[asin] = ProductState.from_dict(product_data)
        logger.info(
            f"Populated WorldStateManager with {len(self._product_state)} products from dictionary."
        )

    def reset_state(self) -> None:
        """Reset all state - used for testing."""
        self._product_state.clear()
        self._supplier_catalog.clear()
        logger.info("WorldStateManager state reset")
