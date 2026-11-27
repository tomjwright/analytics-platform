{#
    Decides the schema each model is built in. dbt's default glues the target schema
    and the model's +schema together everywhere, e.g. `default_silver` in prod.

    TODO(ticket 04): override it so that
    - dev (target.name == 'dev') gives dbt_<you>_silver: target.schema, "_", the custom schema;
    - staging and prod give just silver / gold: the custom schema on its own;
    - a model with no +schema (custom_schema_name is none) falls back to target.schema.
    Docs: https://docs.getdbt.com/docs/build/custom-schemas

    TODO(ticket 05): the `ci` target builds like dev, in its own prefixed schemas:
    ci_pr_<n>_silver, where target.schema is ci_pr_<n>.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}

        {{ default_schema }}

{%- elif target.name == 'dev' -%}

        {{ default_schema }}_{{ custom_schema_name | trim }}

{%- elif target.name == 'ci' -%}

        {{ default_schema }}_{{ custom_schema_name | trim }}

{%- else -%}

        {{ custom_schema_name | trim }}
        
    {%- endif -%}
{%- endmacro %}
