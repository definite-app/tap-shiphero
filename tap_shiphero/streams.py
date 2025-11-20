"""Stream type classes for tap-shiphero."""

from __future__ import annotations

import typing as t
from importlib import resources

from tap_shiphero.client import ShipHeroDateRangeStream, ShipHeroStream

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

class ReturnsStream(ShipHeroStream):
    name = "returns"
    primary_keys: t.ClassVar[list[str]] = ["id"]
    replication_key = "created_at"
    schema_filepath = SCHEMAS_DIR / "returns.json"


class PurchaseOrdersStream(ShipHeroStream):
    name = "purchase_orders"
    primary_keys: t.ClassVar[list[str]] = ["id"]
    replication_key = None # full table refresh
    schema_filepath = SCHEMAS_DIR / "purchase_orders.json"


class ShipmentsStream(ShipHeroDateRangeStream):
    """Define custom stream for ShipHero shipments. Uses date range filtering."""

    name = "shipments"
    primary_keys: t.ClassVar[list[str]] = ["id"]
    replication_key = "created_date"
    is_sorted = False
    schema_filepath = SCHEMAS_DIR / "shipments.json"

class LineItemPicksStream(ShipHeroDateRangeStream):
    name = "line_item_pick"
    primary_keys: t.ClassVar[list[str]] = ["id"]
    replication_key = "created_at"
    is_sorted = False
    schema_filepath = SCHEMAS_DIR / "line_item_pick.json"