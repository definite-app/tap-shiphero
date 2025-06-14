"""ShipHero tap class."""

from __future__ import annotations

import requests
from singer_sdk import Tap
from singer_sdk import typing as th  # JSON schema typing helpers

# TODO: Import your custom stream types here:
from tap_shiphero import streams


class TapShipHero(Tap):
    """ShipHero tap class."""

    name = "tap-shiphero"

    config_jsonschema = th.PropertiesList(
        th.Property(
            "refresh_token",
            th.StringType(nullable=False),
            required=True,
            secret=True,  # Flag config as protected.
            title="Refresh Token",
            description="The refresh token to authenticate against the API service",
        ),
        th.Property(
            "start_date",
            th.DateTimeType(nullable=False),
            required=True,
            description="The earliest record date to sync",
        ),
        th.Property(
            "user_agent",
            th.StringType(nullable=True),
            description=(
                "A custom User-Agent header to send with each request. Default is "
                "'<tap_name>/<tap_version>'"
            ),
        ),
    ).to_dict()

    def _get_access_token(self) -> str:
        """Get access token using refresh token.

        Returns:
            The access token string.

        Raises:
            Exception: If unable to get access token.
        """
        refresh_url = "https://public-api.shiphero.com/auth/refresh"
        refresh_token = self.config.get("refresh_token")

        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "refresh_token": refresh_token
        }

        try:
            response = requests.post(refresh_url, headers=headers, json=data)
            response.raise_for_status()

            response_data = response.json()
            access_token = response_data.get("access_token")

            if not access_token:
                raise Exception("No access_token found in refresh response")

            self.logger.info("Successfully obtained access token")
            return access_token

        except requests.RequestException as e:
            raise Exception(f"Failed to refresh access token: {e}")
        except Exception as e:
            raise Exception(f"Error getting access token: {e}")

    def discover_streams(self) -> list[streams.ShipHeroStream]:
        """Return a list of discovered streams.

        Returns:
            A list of discovered streams.
        """
        # Get access token once and pass to all streams
        access_token = self._get_access_token()

        return [
            streams.OrdersStream(self, access_token=access_token),
            streams.ProductsStream(self, access_token=access_token),
            streams.VendorsStream(self, access_token=access_token),
            streams.ShipmentsStream(self, access_token=access_token),
            streams.ReturnsStream(self, access_token=access_token),
            streams.PurchaseOrdersStream(self, access_token=access_token),
        ]


if __name__ == "__main__":
    TapShipHero.cli()
