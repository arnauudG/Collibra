"""The documentation is executable: every cookbook recipe runs, and use-case links are valid."""

import re
from pathlib import Path

import pytest

from collibra_toolkit.insights.model import build_model

COOKBOOK = Path(__file__).resolve().parents[2] / "docs" / "insights" / "cookbook.md"
BLOCKS = re.findall(r"```sql\n(.*?)```", COOKBOOK.read_text(), flags=re.S)
DICTIONARY = COOKBOOK.parent / "data-dictionary.md"
JOINS = re.findall(r"```sql\n(.*?)```", DICTIONARY.read_text(), flags=re.S)


def test_cookbook_has_recipes():
    assert len(BLOCKS) >= 15


@pytest.mark.parametrize("sql", BLOCKS, ids=[f"recipe_{i + 1}" for i in range(len(BLOCKS))])
def test_recipe_runs(snap, sql):  # noqa: F811
    build_model(snap)
    snap.sql(sql).fetchall()  # raises on any binder / syntax / runtime error


def test_recipes_return_sensible_rows_on_fixture(snap):  # noqa: F811
    build_model(snap)
    inventory = snap.sql(BLOCKS[0]).fetchall()
    assert inventory == [("Term", "Approved", 2)]
    tree = snap.sql(BLOCKS[2]).fetchall()
    assert tree == [("Root", 2, "Parent > Root")]


def _slug(heading: str) -> str:
    """GitHub-style heading anchor."""
    return re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


def test_use_case_links_point_at_real_recipes():
    anchors = {_slug(h) for h in re.findall(r"^### (.+)$", COOKBOOK.read_text(), flags=re.M)}
    page = (COOKBOOK.parent / "use-cases.md").read_text()
    links = re.findall(r"\(cookbook\.md#([^)]+)\)", page)
    assert len(links) >= 20
    missing = [a for a in links if a not in anchors]
    assert not missing, f"stale recipe links: {missing}"


def test_dictionary_has_worked_joins():
    assert len(JOINS) >= 6


@pytest.mark.parametrize("sql", JOINS, ids=[f"join_{i + 1}" for i in range(len(JOINS))])
def test_dictionary_join_runs_on_the_raw_tables(snap, sql):
    snap.sql(sql).fetchall()


def test_dictionary_joins_return_the_expected_rows(snap):
    path = snap.sql(JOINS[0]).fetchall()
    assert ("n", "Dom", "Root") in path                      # asset > domain > community, one row per asset
    assert len(path) == 2                                    # the community filter prevents one row per level
    assert snap.sql(JOINS[2]).fetchall() == [("r1", "n", "n")]  # one direction only
