"""Every ```sql block in docs/cookbook.md must bind and run against the fixture model."""

import re
from pathlib import Path

import pytest
from test_model import snap  # noqa: F401  (fixture)

from collibra_insights.model import build_model

COOKBOOK = Path(__file__).resolve().parents[1] / "docs" / "cookbook.md"
BLOCKS = re.findall(r"```sql\n(.*?)```", COOKBOOK.read_text(), flags=re.S)


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
