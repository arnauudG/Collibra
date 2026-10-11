# Collibra toolkit: documentation

A small, reusable Python toolkit for working with Collibra. It is organised in layers so each initiative reuses the same client and nothing else.

| Layer | Package | Documentation |
|---|---|---|
| **Generic client**: auth, requests, typed errors, pagination | `collibra_toolkit` | [client.md](client.md) |
| **Insights Data Access**: download snapshots, explore, model, query | `collibra_toolkit.insights` | [insights/README.md](insights/README.md) |
| *Your next initiative* | `collibra_toolkit.<name>` | see below |

## Layout

```
src/collibra_toolkit/
  client.py            generic CollibraClient + typed errors      <- reusable by every initiative
  health.py            ping()
  cli.py, cli_util.py  `collibra-toolkit`, shared CLI plumbing
  insights/            one folder per initiative
    client.py          InsightsClient (composes CollibraClient)
    snapshot.py model.py investigate.py tables.py cli.py
tests/                 generic tests; tests/insights/ for Insights
docs/                  this page, client.md; docs/insights/ for Insights
```

## Adding an initiative

1. Create `src/collibra_toolkit/<name>/` with its own `client.py` that **takes a `CollibraClient`** (composition, not inheritance) and calls `client.request`, `client.get_json` or `client.paginate`.
2. Give it a CLI (`<name>/cli.py`, using `cli_util.run`) and register a script in `pyproject.toml`; add a branch in `collibra_toolkit/cli.py` so `collibra-toolkit <name> …` works.
3. Add `tests/<name>/` (use `tests/fakes.py` for HTTP) and `docs/<name>/` with a README index.
4. Put anything useful to more than one initiative **into the generic layer**, not into the initiative.

## Conventions

* Credentials come from `COLLIBRA_URL` plus `COLLIBRA_USER`/`COLLIBRA_PASSWORD` or `COLLIBRA_TOKEN`; never from command-line arguments.
* Documentation states what is **verified**, **documented by Collibra** or **inferred**.
* Exports contain personal data; downloaded data is git-ignored.
