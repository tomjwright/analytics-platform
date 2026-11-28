-- TODO(ticket 04): the Type 1 Customer dimension: one current row per Customer.
-- - customer_key: a surrogate key. For the tracer, md5(customer_unique_id) is fine; ticket 07
--   replaces it with the surrogate_key() macro and makes this dimension SCD Type 2.
-- - Then customer_unique_id (the natural key), zip_code_prefix, city, state, updated_at.
-- Type 1 means a move overwrites the old address: no history. What does that cost an analyst?
select
    md5(customer_unique_id) as customer_key,
    customer_unique_id,
    zip_code_prefix,
    upper(city) as city,
    state,
    updated_at
from {{ ref('stg_customers') }}
