"""What Collibra documents about the Insights tables.

Source: the "Entity relationship diagram" and "Insights tables" pages of the Collibra
Product Resource Center. Columns are listed in docs/insights/data-dictionary.md; the code
discovers them from the Parquet files instead of hardcoding them.
"""

# The eight tables every setup guide loads (one folder each in the snapshot ZIP).
CORE_TABLES: dict[str, str] = {
    "community": "Community hierarchy (one row per community per ancestor level).",
    "domain": "Domains.",
    "asset": "All assets, including assets of custom asset types.",
    "asset_tag": "Tags attached to assets.",
    "attribute": "Attribute values of assets (or of complex relations).",
    "relation": "Binary relations between assets, stored once per direction.",
    "complex_relation": "Complex (n-ary) relations, one row per relation leg.",
    "responsibility": "Responsibilities (Owner, Steward, ...) assigned to assets, or global.",
}

# Documented but not part of the eight-table setup guides; may be absent from a snapshot.
OPTIONAL_TABLES: dict[str, str] = {
    "view_events": "Usage Analytics view events: who viewed which resource, when, on which page.",
}

DOCUMENTED_TABLES: dict[str, str] = {**CORE_TABLES, **OPTIONAL_TABLES}


def table_depth(parts: tuple[str, ...]) -> int:
    """Index of the first Hive partition folder (``key=value``); ``len(parts)`` if there is none."""
    return next((i for i, p in enumerate(parts) if "=" in p), len(parts))


def table_name(parent_parts: tuple[str, ...]) -> str | None:
    """Table a Parquet file belongs to: the folder just above its first partition folder."""
    depth = table_depth(parent_parts)
    return parent_parts[depth - 1] if depth else None
