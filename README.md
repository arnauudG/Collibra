# collibra-toolkit

A reusable Python toolkit for discovering what Collibra offers and which business capabilities it enables. It is built in two layers:

* a **generic client** for the Collibra REST API (authentication, typed errors, retries, pagination) that knows nothing about any particular use;
* **initiatives**, each a self-contained package on top of the client, with its own commands and documentation.

It is for learning and advising, not for running a data platform.

## Initiatives

| Initiative | What it does | Start here |
|---|---|---|
| **Insights Data Access** | Downloads Collibra's nightly metadata snapshots, takes them apart, models them as a star schema, and maps which business questions and decisions they support | [docs/insights/README.md](docs/insights/README.md) |

New initiatives are added alongside it without touching the generic layer (see *Adding an initiative*).

## Install

```bash
python3 -m venv ~/.venvs/collibra && . ~/.venvs/collibra/bin/activate   # keep the venv outside iCloud-synced folders
pip install -e .                  # the generic client only
pip install -e ".[insights]"      # plus an initiative's dependencies (here: DuckDB)
pip install -e ".[dev]"           # everything, plus the test tools
```

## Connect

Credentials come from environment variables, never from command-line arguments. OAuth with an *integration* application registered by a Collibra administrator is recommended:

```bash
export COLLIBRA_URL=https://<your-env>.collibra.com
export COLLIBRA_CLIENT_ID=<client id>
read -s COLLIBRA_CLIENT_SECRET     # on its own line; type or paste, then Enter (nothing is echoed)
export COLLIBRA_CLIENT_SECRET
# alternatives: COLLIBRA_TOKEN, or COLLIBRA_USER + COLLIBRA_PASSWORD

collibra-toolkit ping              # reachability, response shape, pagination, and which auth method was used
collibra-toolkit -h                # lists the installed initiatives; `collibra-toolkit <initiative> -h` for their commands
```

```python
from collibra_toolkit import CollibraClient

client = CollibraClient.from_env()
for community in client.paginate("/communities"):   # any REST API v2 path
    print(community["name"])
```

Details (authentication methods, retries, errors, verification status): [docs/client/README.md](docs/client/README.md).

## Layout: each level holds only what it needs

```
src/collibra_toolkit/
  client/          THE GENERIC LAYER: knows no initiative; needs only `requests`
                   retry -> errors -> auth -> pagination -> core (CollibraClient) -> health
  cli/             `collibra-toolkit`: generic commands; initiatives are discovered by entry point
  _lazy.py         lazy exports, so importing one layer never loads another
  <initiative>/    one folder per initiative (today: insights/), composing the client
tests/             mirrors src/; shared HTTP fakes in tests/support/
docs/              mirrors src/: docs/client/, docs/<initiative>/
```

**Rules, enforced by `tests/test_architecture.py`:** the generic layer never imports an initiative (the generic CLI *discovers* them); third-party dependencies stay in the layer that needs them (`requests` only in `client/`); each layer imports only the layers listed for it. Each initiative declares its heavy dependencies as an extra, so the client installs light.

## Adding an initiative

1. Create `src/collibra_toolkit/<name>/` with a client class that **takes a `CollibraClient`** (composition, not inheritance) and calls `client.request`, `client.get_json` or `client.paginate`. Split it into layers; keep each third-party dependency in the layer that needs it.
2. Add a `cli.py` whose `main(argv)` is wrapped with `collibra_toolkit.cli.util.run`, and register it in `pyproject.toml`:
   ```toml
   [project.entry-points."collibra_toolkit.initiatives"]
   <name> = "collibra_toolkit.<name>.cli:main"
   ```
   `collibra-toolkit <name> …` then works with no change to generic code.
3. Add its rules to `ALLOWED` in `tests/test_architecture.py`, mirrored tests under `tests/<name>/`, and a `docs/<name>/README.md` entry page. Add a row to the *Initiatives* table above.
4. Anything useful to more than one initiative belongs in the generic layer.

## Conventions and status

* Documentation states what is **verified**, **documented by Collibra** or **inferred**.
* Downloaded data and diagnostic outputs are git-ignored: they contain instance data.
* The generic client is verified live on one instance (basic auth, OAuth client credentials, pagination); static tokens and retries against a real 429/5xx are unit-tested only. Each initiative states its own status on its entry page.
