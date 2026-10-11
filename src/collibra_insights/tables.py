"""What Collibra documents about the Insights tables.

Source: "Insights tables" and "Set up Insights on GCP" in the Collibra Product
Resource Center. The docs name the tables and say what they hold, but do NOT
publish column lists; those ship in the Marketplace SQL scripts and in the
Parquet files themselves. So we describe tables here and discover columns at
runtime (see ``Snapshot.describe``) instead of hardcoding them.
"""

# folder name inside the snapshot ZIP -> what it holds
DOCUMENTED_TABLES: dict[str, str] = {
    "community": "Community hierarchy.",
    "domain": "All domains.",
    "asset": "All assets, including assets of custom asset types.",
    "asset_tag": "All asset tags.",
    "attribute": "Attributes of those assets (Definition, Description, custom attribute types).",
    "relation": "Binary relations between assets (e.g. 'categorizes' / 'is categorized by'), incl. custom types.",
    "complex_relation": "Complex (n-ary) relations.",
    "responsibility": "Responsibilities (Owner, Stakeholder, ...) for a given resource.",
}

# Documented as a table, but its folder name is not published; found at runtime.
USAGE_ANALYTICS_NOTE = "Usage Analytics view events (page views by users); folder name not documented."
