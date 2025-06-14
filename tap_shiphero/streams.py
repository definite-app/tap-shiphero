"""Stream type classes for tap-shiphero."""

from __future__ import annotations

import typing as t
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

    def get_child_context(self, record: dict, context) -> dict:
        """Return a context dictionary for child streams."""
        return {
            "order_id": record["id"],
        }


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
    is_sorted = False
    parent_stream_type = OrdersStream

    # Use JSON Schema definition from file:
    schema_filepath = SCHEMAS_DIR / "shipments.json"

    @property
    def query(self) -> str:
        """Build GraphQL query with parent stream context."""
        base_query = self._get_base_query()

        # Get order_id from parent stream context
        order_id = self.context.get("order_id") if self.context else None

        # Handle cursor for pagination
        cursor = getattr(self, "_current_cursor", None)

        if cursor:
            # Replace $cursor with actual cursor value
            query = base_query.replace("$cursor", f'"{cursor}"')
        else:
            # For first page, remove the after parameter entirely
            query = base_query.replace(", after: $cursor", "")

        # Replace $order_id with actual order ID from parent stream
        if order_id:
            query = query.replace("$order_id", f'"{order_id}"')
        else:
            # If no order_id, this shouldn't happen for child streams
            raise ValueError("No order_id provided in context for shipments stream")

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
