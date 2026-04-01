"""Tests for external-catalog-linked database identifier handling.

Architecture:
  dbt's interface (public):  UPPERCASE identifiers — standard Snowflake normalization
  Snowflake's interface (SQL): lowercase quoted identifiers for catalog-linked databases

The adapter is the translation layer:
  - Returns UPPERCASE to dbt (relation matching, caching, schema resolution)
  - Emits lowercase quoted SQL to Snowflake for catalog-linked databases

These tests verify behavior at BOTH interfaces.

Fixes: https://github.com/dbt-labs/dbt-adapters/issues/1473
       https://github.com/dbt-labs/dbt-adapters/issues/1427
"""

from dbt.adapters.snowflake.relation import SnowflakeRelation


class TestDbtInterface:
    """dbt sees UPPERCASE. No ApproximateMatchError, no case surprises."""

    def test_uppercase_relation_matches_uppercase_search(self):
        """dbt stores uppercase, searches uppercase — must always match."""
        relation = SnowflakeRelation.create(
            database="MY_LAKEHOUSE_DB",
            schema="MY_GOLD_SCHEMA",
            identifier="MY_REPORT_TABLE",
        )
        assert relation.matches(
            database="MY_LAKEHOUSE_DB",
            schema="MY_GOLD_SCHEMA",
            identifier="MY_REPORT_TABLE",
        )

    def test_cached_quoted_relation_matches_uppercase_search(self):
        """A cached relation with quote_policy=True and lowercase values must
        match an uppercase search. This is the scenario that triggers
        ApproximateMatchError: list_relations returns lowercase (from catalog),
        but get_relation searches with uppercase."""
        cached = SnowflakeRelation.create(
            database="MY_LAKEHOUSE_DB",
            schema="my_gold_schema",
            identifier="my_report_table",
            quote_policy={"schema": True, "identifier": True, "database": False},
        )
        assert cached.matches(
            database="MY_LAKEHOUSE_DB",
            schema="MY_GOLD_SCHEMA",
            identifier="MY_REPORT_TABLE",
        )

    def test_unquoted_lowercase_relation_matches_uppercase_search(self):
        """Relations from INFORMATION_SCHEMA (quote_policy=False, lowercase)
        must match uppercase search — standard Snowflake case-insensitivity."""
        discovered = SnowflakeRelation.create(
            database="MY_DB",
            schema="gold",
            identifier="report_table",
        )
        assert discovered.matches(
            database="MY_DB",
            schema="GOLD",
            identifier="REPORT_TABLE",
        )

    def test_quote_for_catalog_linked_with_none_schema(self):
        """Models with no schema should not crash."""
        relation = SnowflakeRelation.create(
            database="MY_DB",
            identifier="MY_TABLE",
        )
        sql_relation = relation.quote_for_catalog_linked_database()
        assert "my_table" in sql_relation.render().lower()

    def test_standard_snowflake_unchanged(self):
        """Standard (non-catalog-linked) relations work exactly as before."""
        relation = SnowflakeRelation.create(
            database="MY_DB",
            schema="GOLD",
            identifier="REPORT_TABLE",
        )
        assert relation.matches(
            database="MY_DB",
            schema="GOLD",
            identifier="REPORT_TABLE",
        )
        assert relation.render() == "MY_DB.GOLD.REPORT_TABLE"

    def test_original_relation_not_mutated(self):
        """quote_for_catalog_linked_database returns a new object, doesn't mutate."""
        relation = SnowflakeRelation.create(
            database="MY_LAKEHOUSE_DB",
            schema="MY_SCHEMA",
            identifier="MY_TABLE",
        )
        sql_relation = relation.quote_for_catalog_linked_database()
        assert relation.quote_policy.schema is False
        assert relation.quote_policy.identifier is False
        assert relation.schema == "MY_SCHEMA"


class TestSnowflakeInterface:
    """Snowflake receives lowercase quoted SQL for catalog-linked databases."""

    def test_uppercase_relation_renders_as_lowercase_quoted(self):
        """The core contract: dbt has UPPERCASE, Snowflake gets lowercase quoted."""
        relation = SnowflakeRelation.create(
            database="MY_LAKEHOUSE_DB",
            schema="MY_GOLD_SCHEMA",
            identifier="MY_REPORT_TABLE",
        )
        sql_relation = relation.quote_for_catalog_linked_database()

        rendered = sql_relation.render()
        assert '"my_gold_schema"' in rendered
        assert '"my_report_table"' in rendered
        assert "MY_GOLD_SCHEMA" not in rendered
        assert "MY_REPORT_TABLE" not in rendered

    def test_full_rendering(self):
        """Full SQL rendering for a catalog-linked database relation."""
        relation = SnowflakeRelation.create(
            database="MY_LAKEHOUSE_DB",
            schema="MY_SILVER_SCHEMA",
            identifier="MY_SILVER_TABLE",
        )
        sql_relation = relation.quote_for_catalog_linked_database()
        assert (
            sql_relation.render()
            == 'MY_LAKEHOUSE_DB."my_silver_schema"."my_silver_table"'
        )

    def test_without_identifier_for_schema_operations(self):
        """CREATE SCHEMA uses without_identifier() — lowercase must survive."""
        relation = SnowflakeRelation.create(
            database="MY_LAKEHOUSE_DB",
            schema="MY_GOLD_SCHEMA",
            identifier="MY_TABLE",
        )
        sql_relation = relation.quote_for_catalog_linked_database()
        schema_only = sql_relation.without_identifier()
        assert schema_only.render() == 'MY_LAKEHOUSE_DB."my_gold_schema"'

    def test_always_lowercases_regardless_of_input_case(self):
        """Method always lowercases — it's only called for catalog-linked targets."""
        relation = SnowflakeRelation.create(
            database="MY_DB",
            schema="GOLD",
            identifier="MY_TABLE",
        )
        sql_relation = relation.quote_for_catalog_linked_database()
        assert sql_relation.render() == 'MY_DB."gold"."my_table"'
