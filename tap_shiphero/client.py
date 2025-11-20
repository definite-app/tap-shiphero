"""GraphQL client handling, including ShipHeroStream base class."""

from __future__ import annotations

import decimal
import json
import typing as t
from datetime import datetime, timedelta
from importlib import resources

import requests  # noqa: TC002
from singer_sdk.exceptions import RetriableAPIError
from singer_sdk.pagination import JSONPathPaginator
from singer_sdk.streams import GraphQLStream
from singer_sdk.tap_base import Tap

if t.TYPE_CHECKING:
    from singer_sdk.helpers.types import Context


# GraphQL queries directory
GQL_QUERIES_DIR = resources.files("tap_shiphero") / "gql_queries"


class ShipHeroGraphQLPaginator(JSONPathPaginator):
    """Custom paginator for ShipHero GraphQL cursor-based pagination."""

    def __init__(self, stream_name: str, jsonpath_expr: str | None = None) -> None:
        """Initialize paginator with JSONPath to extract cursor from response."""
        if jsonpath_expr is None:
            jsonpath_expr = f"$.data.{stream_name}.data.pageInfo.endCursor"
        super().__init__(jsonpath_expr)
        self.stream_name = stream_name

    def has_more(self, response: requests.Response) -> bool:
        """Check if there are more pages based on hasNextPage."""
        try:
            data = response.json()
            page_info = data["data"][self.stream_name]["data"]["pageInfo"]
            return page_info.get("hasNextPage", False)
        except (KeyError, TypeError, json.JSONDecodeError):
            # If we can't find the expected structure, assume no more pages
            return False


class ShipHeroRateLimitError(RetriableAPIError):
    """Custom exception for ShipHero rate limiting."""


class ShipHeroStream(GraphQLStream):
    """ShipHero stream class."""

    # ShipHero GraphQL error codes
    RATE_LIMIT_ERROR_CODE = 30

    def __init__(self, tap: Tap, access_token: str, **kwargs) -> None:
        """Initialize the stream with access token."""
        super().__init__(tap, **kwargs)
        self.access_token = access_token

    @property
    def url_base(self) -> str:
        """Return the API URL root, configurable via tap settings."""
        return "https://public-api.shiphero.com/graphql"

    @property
    def http_headers(self) -> dict:
        """Return the http headers needed.

        Returns:
            A dictionary of HTTP headers.
        """
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _get_base_query(self) -> str:
        """Load base GraphQL query from file."""
        query_file = GQL_QUERIES_DIR / f"{self.name}.graphql"
        return query_file.read_text(encoding="utf-8")

    @property
    def query(self) -> str:
        """Build GraphQL query with cursor pagination."""
        base_query = self._get_base_query()

        # Handle cursor for pagination
        cursor = getattr(self, "_current_cursor", None)

        starting_time = self.get_starting_timestamp(self.context)

        if cursor:
            # Replace $cursor with actual cursor value
            query = base_query.replace("$cursor", f'"{cursor}"')
        else:
            # For first page, remove the after parameter entirely
            query = base_query.replace(", after: $cursor", "")

        if self.replication_key:
            # Replace $updated_from with actual starting timestamp if incremental
            # Non-incremental streams don't have $updated_from in GQL query
            query = query.replace("$updated_from", f'"{starting_time}"')

        return query

    def get_new_paginator(self) -> ShipHeroGraphQLPaginator:
        """Return a new paginator instance."""
        return ShipHeroGraphQLPaginator(self.name)

    def prepare_request_payload(
        self,
        context: t.Mapping[str, t.Any] | None,
        next_page_token: t.Any | None,
    ) -> dict | None:
        """Prepare the GraphQL request payload with cursor."""
        # Store the cursor for use in the query property
        self._current_cursor = next_page_token
        # For GraphQL, we return the query as the payload
        return {"query": self.query}

    def backoff_max_tries(self) -> int:
        """Return the maximum number of retry attempts.

        Returns:
            Maximum number of retries for rate limiting.
        """
        return 5  # Allow up to 5 retries for rate limiting

    def validate_response(self, response: requests.Response) -> None:
        """Validate HTTP response and raise retriable errors for rate limiting.

        Args:
            response: A `requests.Response` object.

        Raises:
            ShipHeroRateLimitError: If the response indicates rate limiting.
        """
        # Call parent validation first
        super().validate_response(response)

        # Check for GraphQL errors indicating rate limiting
        try:
            response_json = response.json()
            if "errors" in response_json:
                for error in response_json["errors"]:
                    if error.get("code") == self.RATE_LIMIT_ERROR_CODE:
                        error_msg = error.get("message", "Rate limit exceeded")
                        extensions = error.get("extensions", {})

                        self.logger.warning(
                            f"ShipHero rate limit hit: {error_msg}. "
                            f"Required credits: {extensions.get('required_credits')}, "
                            f"Remaining credits: {extensions.get('remaining_credits')}, "
                            f"Time remaining: {extensions.get('time_remaining')}"
                        )

                        rate_limit_msg = f"ShipHero rate limit: {error_msg}"
                        raise ShipHeroRateLimitError(rate_limit_msg, response=response)
        except (json.JSONDecodeError, KeyError):
            # If we can't parse the response, let the parent handle it
            pass

    def parse_response(self, response: requests.Response) -> t.Iterable[dict]:
        """Parse the response and return an iterator of result records.

        Args:
            response: The HTTP ``requests.Response`` object.

        Yields:
            Each record from the source.
        """
        resp_json = response.json(parse_float=decimal.Decimal)

        # The paginator's has_more() method handles empty responses,
        # so we can focus on parsing valid responses here
        try:
            # The line_item_pick query is named "picks_per_day" in the response
            # See: https://developer.shiphero.com/examples/#lineitemspick
            entity_name = self.name if self.name != "line_item_pick" else "picks_per_day"
            yield from resp_json["data"][entity_name]["data"]["edges"]
        except (KeyError, TypeError):
            # Check for GraphQL errors and raise exception instead of just logging
            if "errors" in resp_json:
                error_messages = [
                    error.get("message", "Unknown GraphQL error")
                    for error in resp_json["errors"]
                ]
                raise RetriableAPIError(
                    f"GraphQL errors in response: {'; '.join(error_messages)}",
                    response=response,
                )
            else:
                self.logger.info("No data found in expected response structure")
            # If the response structure is unexpected, yield nothing
            # The paginator will handle stopping pagination
            return

    def post_process(
        self,
        row: dict,
        context: Context | None = None,  # noqa: ARG002
    ) -> dict | None:
        """As needed, append or transform raw data to match expected structure.

        Args:
            row: An individual record from the stream.
            context: The stream context.

        Returns:
            The updated record dictionary, or ``None`` to skip the record.
        """
        return row["node"]

    def backoff_jitter(self, value: float) -> float:
        """Return the jitter amount for backoff.

        Since ShipHero provides exact wait times, we disable jitter
        to wait exactly as long as they specify.

        Args:
            value: Base amount to wait in seconds.

        Returns:
            The same value without jitter added.
        """
        return value

    def backoff_wait_generator(self) -> t.Generator[float, None, None]:
        """Return a backoff wait generator that uses ShipHero's time_remaining.

        Returns:
            A backoff wait generator function.
        """

        def _backoff_from_shiphero_error(retriable_api_error: RetriableAPIError) -> int:
            """Extract wait time from ShipHero GraphQL error response."""
            try:
                if (
                    hasattr(retriable_api_error, "response")
                    and retriable_api_error.response
                ):
                    response_json = retriable_api_error.response.json()
                    if "errors" in response_json:
                        for error in response_json["errors"]:
                            if error.get("code") == self.RATE_LIMIT_ERROR_CODE:
                                time_remaining = error.get(
                                    "time_remaining", None
                                )  # is a string like "10 seconds"
                                if time_remaining:
                                    # time_remaining is typically in seconds
                                    wait_time = int(time_remaining.split(" ")[0]) + 1
                                    self.logger.info(
                                        f"Using ShipHero suggested wait time: {wait_time} seconds"
                                    )
                                    return wait_time
            except (json.JSONDecodeError, KeyError, ValueError, AttributeError):
                pass

            # Fallback to default wait time if we can't extract from response
            default_wait = 5  # 5s default
            self.logger.info(
                f"Could not extract wait time from response, using default: {default_wait} seconds"
            )
            return default_wait

        return self.backoff_runtime(value=_backoff_from_shiphero_error)

class ShipHeroDateRangeStream(ShipHeroStream):
    """ShipHero stream class for GQL endpoints that require date range filtering."""

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

        self.logger.info(f"Querying {self.name} from {start_date} to {end_date}")

        return query
