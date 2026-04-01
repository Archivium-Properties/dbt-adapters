{% macro snowflake__generate_database_name(custom_database_name=none, node=none) -%}
    {%- if custom_database_name is none -%}
         {%- if node is not none and node|attr('database') -%}
            {%- set catalog_relation = adapter.build_catalog_relation(node) -%}
        {%- elif 'config' in target -%}
            {%- set catalog_relation = adapter.build_catalog_relation(target) -%}
        {%- else -%}
            {%- set catalog_relation = none -%}
        {%- endif -%}
        {%- if catalog_relation is not none
            and catalog_relation|attr('catalog_linked_database')-%}
            {{ return(catalog_relation.catalog_linked_database) }}
        {%- else -%}
            {{ target.database }}
        {%- endif -%}
    {%- else -%}
       {{ custom_database_name }}
    {%- endif -%}
{%- endmacro %}

{% macro snowflake__generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}

    {#- When a model targets a different database (e.g., an external-catalog-linked
        database for Glue/Unity Iceberg writes), use the custom schema name directly
        without concatenating the profile's default schema. The schema in such a
        database IS the external catalog namespace and must not be prefixed.

        For models in the default database, use dbt's standard concatenation. -#}
    {%- set model_database = node.config.get('database', none) if node is not none else none -%}
    {%- set targets_different_database = model_database is not none
        and model_database != ''
        and model_database | upper != target.database | upper -%}

    {%- if targets_different_database and custom_schema_name is not none -%}
        {#- Different database: use schema as-is -#}
        {{ custom_schema_name.strip() }}
    {%- elif custom_schema_name is not none -%}
        {#- Standard Snowflake: concatenate default + custom -#}
        {{ default_schema ~ "_" ~ custom_schema_name.strip() }}
    {%- else -%}
        {{ default_schema }}
    {%- endif -%}

{%- endmacro %}
