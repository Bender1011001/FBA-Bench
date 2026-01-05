"""
Command arbitration module for WorldStore.
Handles SetPriceCommand processing, conflict resolution, and state application.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

from money import Money

from fba_events.bus import EventBus
from fba_events.pricing import ProductPriceUpdated, SetPriceCommand

from .models import CommandArbitrationResult, SimpleArbitrationResult
from .state import WorldStateManager

logger = logging.getLogger(__name__)


class CommandArbitrator:
    """
    Manages command arbitration and processing for WorldStore.

    Handles validation, conflict resolution, and application of price commands.
    Tracks per-tick state and statistics.
    """

    def __init__(self, event_bus: EventBus, state_manager: WorldStateManager):
        # Command processing state for enhanced conflict resolution
        self._pending_commands_by_asin_this_tick: Dict[str, List[SetPriceCommand]] = {}
        self._processed_command_ids_this_tick: set[str] = (
            set()
        )  # To avoid re-processing exact duplicates within a tick
        self._command_history: List[SetPriceCommand] = []

        # Arbitration configuration
        self.max_price_change_per_tick = 0.50  # Max 50% price change per tick
        self.min_price_threshold = Money(100)  # Minimum price $1.00
        self.max_price_threshold = Money(100000)  # Maximum price $1000.00

        # Statistics
        self.commands_processed = 0
        self.commands_rejected = 0
        self.conflicts_arbitrated = 0  # Counts when a command is rejected due to a prior accepted one for same ASIN in the tick

        self.event_bus = event_bus
        self.state_manager = state_manager

        logger.info("CommandArbitrator initialized")

    def reset_tick_state(self) -> None:
        """Clear per-tick command tracking at the beginning of each new tick."""
        self._pending_commands_by_asin_this_tick.clear()
        self._processed_command_ids_this_tick.clear()

    async def handle_set_price_command(self, event: SetPriceCommand) -> None:
        """
        Process SetPriceCommand from agents.

        Performs arbitration, validation, and state updates.
        Publishes ProductPriceUpdated on successful changes.
        """
        try:
            logger.debug(
                f"Processing SetPriceCommand: agent={event.agent_id}, asin={event.asin}, price={event.new_price}, command_id={event.event_id}"
            )

            if event.event_id in self._processed_command_ids_this_tick:
                logger.warning(
                    f"Duplicate SetPriceCommand ignored: command_id={event.event_id} from agent={event.agent_id} for asin={event.asin}"
                )
                self.commands_rejected += 1
                return

            # Arbitrate the command
            result = await self._arbitrate_price_command(event)

            if result.accepted:
                # Apply the state change
                await self._apply_price_change(event, result)
                self.commands_processed += 1
                # Mark this command as processed for this tick
                self._processed_command_ids_this_tick.add(event.event_id)
                # Add to pending commands for this ASIN for this tick to block subsequent ones
                if event.asin not in self._pending_commands_by_asin_this_tick:
                    self._pending_commands_by_asin_this_tick[event.asin] = []
                self._pending_commands_by_asin_this_tick[event.asin].append(event)

                logger.info(
                    f"SetPriceCommand accepted: agent={event.agent_id}, asin={event.asin}, new_price={result.final_price}, command_id={event.event_id}"
                )
            else:
                # Reject the command
                self.commands_rejected += 1
                if (
                    "already accepted for this ASIN in the current tick"
                    in result.reason
                ):
                    self.conflicts_arbitrated += 1
                logger.warning(
                    f"SetPriceCommand rejected: agent={event.agent_id}, asin={event.asin}, reason={result.reason}, command_id={event.event_id}"
                )

            # Record in history
            self._command_history.append(event)

        except (TypeError, AttributeError, RuntimeError, ValueError) as e:
            logger.error(
                f"Error processing SetPriceCommand {event.event_id}: {e}", exc_info=True
            )
            self.commands_rejected += 1

    async def _arbitrate_price_command(
        self, command: SetPriceCommand
    ) -> CommandArbitrationResult:
        """
        Arbitrate a price change command with enhanced conflict resolution.

        Validation rules:
        1. Price must be within global min/max thresholds
        2. Price change cannot exceed max_price_change_per_tick
        3. Product must exist or be initializable

        Conflict resolution:
        - If another command for the same ASIN has already been accepted in this tick, reject.
        - Commands for the same ASIN within the same tick are processed in order of arrival (timestamp/event_id).
        """

        # Rule 1: Validate price bounds
        if command.new_price < self.min_price_threshold:
            return CommandArbitrationResult(
                accepted=False,
                reason=f"Price {command.new_price} below minimum threshold {self.min_price_threshold}",
            )

        if command.new_price > self.max_price_threshold:
            return CommandArbitrationResult(
                accepted=False,
                reason=f"Price {command.new_price} above maximum threshold {self.max_price_threshold}",
            )

        current_state = self.state_manager.get_product_state(command.asin)

        if current_state:
            # Rule 2: Validate price change magnitude
            current_price = current_state.price
            # Avoid division by zero if current_price is zero, though unlikely for Money type unless explicitly set.
            if current_price.cents > 0:
                price_change_ratio = abs(
                    (command.new_price.cents / current_price.cents) - 1.0
                )
                if price_change_ratio > self.max_price_change_per_tick:
                    return CommandArbitrationResult(
                        accepted=False,
                        reason=f"Price change {price_change_ratio:.2%} exceeds maximum {self.max_price_change_per_tick:.2%} per tick",
                    )

            # Rule 3: Enhanced Conflict Resolution
            # Check if a command for this ASIN has already been processed and accepted in this tick
            if self._pending_commands_by_asin_this_tick.get(command.asin):
                # There's at least one pending/accepted command for this ASIN this tick.
                # The current design processes sequentially, so if it's in the list, it's been accepted.
                # We reject subsequent ones for the same ASIN in the same tick.
                # The `handle_set_price_command` adds to this list *after* successful arbitration and application.
                # So, if it's already here, it means another command for this ASIN was processed first.
                # This check effectively means "only one price change per ASIN per tick".
                # If more fine-grained ordering (e.g., by timestamp) is needed beyond "first come, first served"
                # by the async event loop, the logic here would need to queue and sort.
                # For now, this simple check prevents multiple updates to the same ASIN within one tick.
                # The `handle_set_price_command` adds to `_pending_commands_by_asin_this_tick` *after* success.
                # So, if we find it here during a new call, it means a previous one succeeded.
                # This check is now effectively: "has a command for this ASIN already been accepted in this tick?"
                # The list `_pending_commands_by_asin_this_tick[command.asin]` holds commands that were accepted.
                if self._pending_commands_by_asin_this_tick[
                    command.asin
                ]:  # If the list is not empty
                    return CommandArbitrationResult(
                        accepted=False,
                        reason=f"Another price command for ASIN {command.asin} was already accepted for this tick.",
                    )
        else:
            # Product doesn't exist - initialize with command price
            logger.info(
                f"Initializing new product state: asin={command.asin}, price={command.new_price}"
            )

        # Command accepted
        return CommandArbitrationResult(
            accepted=True,
            reason="Command validated and accepted",
            final_price=command.new_price,
            arbitration_notes=f"Processed by CommandArbitrator at {datetime.now().isoformat()}",
        )

    async def _apply_price_change(
        self, command: SetPriceCommand, result: CommandArbitrationResult
    ) -> None:
        """
        Apply validated price change to canonical state and publish update event.
        """
        asin = command.asin
        new_price = result.final_price
        current_state = self.state_manager.get_product_state(asin)

        previous_price = (
            current_state.price if current_state else Money(2000)
        )  # Default $20.00

        if current_state:
            current_state.price = new_price
            current_state.last_updated = datetime.now()
            current_state.last_agent_id = command.agent_id
            current_state.last_command_id = command.event_id
            current_state.version += 1
        else:
            existing_inventory = 0
            existing_cost_basis = Money.zero()
            # Check if a stub was created by inventory update before price was set
            if asin in self.state_manager.get_all_product_states():
                stub_state = self.state_manager.get_product_state(asin)
                if stub_state:
                    existing_inventory = stub_state.inventory_quantity
                    existing_cost_basis = stub_state.cost_basis

            new_state = ProductState(
                asin=asin,
                price=new_price,
                inventory_quantity=existing_inventory,
                cost_basis=existing_cost_basis,
                last_updated=datetime.now(),
                last_agent_id=command.agent_id,
                last_command_id=command.event_id,
                version=1,
            )
            self.state_manager.set_product_state(asin, new_state)

        update_event = ProductPriceUpdated(
            event_id=str(uuid4()),
            timestamp=datetime.now(),
            asin=asin,
            new_price=new_price,
            previous_price=previous_price,
            agent_id=command.agent_id,
            command_id=command.event_id,
            arbitration_notes=result.arbitration_notes,
        )

        await self.event_bus.publish(update_event)
        logger.info(f"Published ProductPriceUpdated: asin={asin}, price={new_price}")

    def arbitrate_commands(
        self, commands: List[Dict[str, Any]]
    ) -> SimpleArbitrationResult:
        """
        Back-compat simple arbitration for dict-based commands.

        Strategy:
          - Choose the command with the highest 'timestamp' value.
          - Return SimpleArbitrationResult(winning_command=..., reason="timestamp").
        """
        try:
            cmds = list(commands or [])
        except (TypeError, AttributeError):
            cmds = []
        if not cmds:
            return SimpleArbitrationResult(winning_command={}, reason="empty")

        def _key(c: Dict[str, Any]) -> float:
            try:
                return float(c.get("timestamp", 0.0))
            except (TypeError, AttributeError, ValueError):
                return 0.0

        winner = max(cmds, key=_key)
        return SimpleArbitrationResult(winning_command=winner, reason="timestamp")

    def get_statistics(self) -> Dict[str, Any]:
        """Get arbitration operational statistics."""
        return {
            "commands_processed": self.commands_processed,
            "commands_rejected": self.commands_rejected,
            "conflicts_arbitrated": self.conflicts_arbitrated,
            "command_history_size": len(self._command_history),
        }

    def reset(self):
        """Reset arbitration state for testing."""
        self.reset_tick_state()
        self._command_history.clear()
        self.commands_processed = 0
        self.commands_rejected = 0
        self.conflicts_arbitrated = 0
