# tap-shiphero

`tap-shiphero` is a Singer tap for ShipHero's GraphQL API.

Built with the [Meltano Tap SDK](https://sdk.meltano.com) for Singer Taps by the team at [Definite](https://definite.app).

The following is a list of streams that are currently supported:

| Stream Name | Replication Method |
|------------|-------------------|
| orders | INCREMENTAL |
| vendors | FULL_TABLE |
| products | INCREMENTAL |
| purchase_orders | FULL_TABLE |
| shipments | INCREMENTAL |
| returns | INCREMENTAL |

The tap pulls from ShipHero's GraphQL API. Rate limits are pretty strict, especially for the orders stream, so we limit the number of records pulled on each page and paginate through the results, waiting for rate-limit credits to reset when necessary. Number of records pulled per page for each stream can be found in the `gql_queries` folder. You may need to adjust this depending on your use case.

## Configuration

### Accepted Config Options

`refresh_token`: A refresh token for ShipHero. This is used to obtain an access token.

`start_date`: The date to start pulling data from. This is used to filter the data pulled from the source.

A full list of supported settings and capabilities for this
tap is available by running:

```bash
tap-shiphero --about
```

### Configure using environment variables

This Singer tap will automatically import any environment variables within the working directory's
`.env` if the `--config=ENV` is provided, such that config values will be considered if a matching
environment variable is set either in the terminal context or in the `.env` file.

### Source Authentication and Authorization

You can authenticate to Ship Hero API by providing a refresh token which will then be used by the tap to obtain an access token. The access token is used to pull data from the Ship Hero API. You can have multiple access tokens at one time so obtaining a new one each time the tap is run should be fine. This avoids having to manage storing access tokens and monitoring their expiration.

## Usage

You can easily run `tap-shiphero` by itself or in a pipeline using [Meltano](https://meltano.com/).

### Executing the Tap Directly

```bash
tap-shiphero --version
tap-shiphero --help
tap-shiphero --config CONFIG --discover > ./catalog.json
```

## Developer Resources

Follow these instructions to contribute to this project.

### Initialize your Development Environment

Prerequisites:

- Python 3.9+
- [uv](https://docs.astral.sh/uv/)

```bash
uv sync
```

### Create and Run Tests

TODO: Write tests.

Create tests within the `tests` subfolder and
then run:

```bash
uv run pytest
```

You can also test the `tap-shiphero` CLI interface directly using `uv run`:

```bash
uv run tap-shiphero --help
```

### Testing with [Meltano](https://www.meltano.com)

_**Note:** This tap will work in any Singer environment and does not require Meltano.
Examples here are for convenience and to streamline end-to-end orchestration scenarios._


Next, install Meltano (if you haven't already) and any needed plugins:

```bash
# Install meltano
pipx install meltano
# Initialize meltano within this directory
cd tap-shiphero
meltano install
```

Now you can test and orchestrate using Meltano:

```bash
# Test invocation:
meltano invoke tap-shiphero --version

# OR run a test ELT pipeline:
meltano run tap-shiphero target-jsonl
```

### SDK Dev Guide

See the [dev guide](https://sdk.meltano.com/en/latest/dev_guide.html) for more instructions on how to use the SDK to
develop your own taps and targets.
