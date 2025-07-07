"""Stream type classes for tap-shiphero."""

from __future__ import annotations

import typing as t
from datetime import datetime, timedelta
from importlib import resources

from tap_shiphero.client import ShipHeroStream

# Schema files directory
SCHEMAS_DIR = resources.files(__package__) / "schemas"


class OrdersStream(ShipHeroStream):
    """Define custom stream for ShipHero orders."""

    name = "orders"
    primary_keys: t.ClassVar[list[str]] = ["id"]
    replication_key = "updated_at"
    is_sorted = False  # ShipHero API sorting doesn't work globally across pages https://community.shiphero.com/t/warehouse-products-sort/809/19

    # Use JSON Schema definition from file:
    schema_filepath = SCHEMAS_DIR / "orders.json"


class ProductsStream(ShipHeroStream):
    """Define custom stream for ShipHero products."""

    name = "products"
    primary_keys: t.ClassVar[list[str]] = ["id"]
    replication_key = "updated_at"
    is_sorted = False  # ShipHero API sorting doesn't work globally across pages

    # Use JSON Schema definition from file:
    schema_filepath = SCHEMAS_DIR / "products.json"


class VendorsStream(ShipHeroStream):
    """Define custom stream for ShipHero vendors."""

    name = "vendors"
    primary_keys: t.ClassVar[list[str]] = ["id"]
    replication_key = None

    # Use JSON Schema definition from file:
    schema_filepath = SCHEMAS_DIR / "vendors.json"


class ShipmentsStream(ShipHeroStream):
    """Define custom stream for ShipHero shipments."""

    name = "shipments"
    primary_keys: t.ClassVar[list[str]] = ["id"]
    replication_key = "created_date"
    is_sorted = False
    schema_filepath = SCHEMAS_DIR / "shipments.json"

    def _get_end_date(self) -> str:
        """Get end date as current date + 1 day in ISO format."""
        end_date = datetime.now() + timedelta(days=1)
        return end_date.strftime("%Y-%m-%d")

    def _get_start_date(self) -> str:
        """Get start date based on replication state."""
        starting_timestamp = self.get_starting_timestamp(self.context)
        if starting_timestamp:
            return starting_timestamp.strftime("%Y-%m-%d")

        start_date = self.config.get("start_date")
        if start_date:
            return start_date

        raise ValueError(
            "No start_date configured and no previous bookmark found. "
            "Please set 'start_date' in your tap configuration for initial sync."
        )

    @property
    def query(self) -> str:
        """Build GraphQL query with date range filtering."""
        base_query = self._get_base_query()

        # Handle cursor for pagination
        cursor = getattr(self, "_current_cursor", None)

        if cursor:
            # Replace $cursor with actual cursor value
            query = base_query.replace("$cursor", f'"{cursor}"')
        else:
            # For first page, remove the after parameter entirely
            query = base_query.replace(", after: $cursor", "")

        # Get date range
        start_date = self._get_start_date()
        end_date = self._get_end_date()

        # Replace date parameters
        query = query.replace("$date_from", f'"{start_date}"')
        query = query.replace("$date_to", f'"{end_date}"')

        self.logger.info(f"Querying shipments from {start_date} to {end_date}")

        return query



class ReturnsStream(ShipHeroStream):
    name = "returns"
    primary_keys: t.ClassVar[list[str]] = ["id"]
    replication_key = "created_at"
    schema_filepath = SCHEMAS_DIR / "returns.json"


class PurchaseOrdersStream(ShipHeroStream):
    name = "purchase_orders"
    primary_keys: t.ClassVar[list[str]] = ["id"]
    replication_key = None
    schema_filepath = SCHEMAS_DIR / "purchase_orders.json"
