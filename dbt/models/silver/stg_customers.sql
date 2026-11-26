-- TODO(ticket 04): one row per Customer, cleaned and standardised.
-- 1. Standardise: trim and lower-case text; left-pad zip_code_prefix to 5 digits (Olist
--    dropped the leading zero: 1001 is really 01001); cast updated_at to a date.
-- 2. Drop rows Silver can't trust: no customer_unique_id, or a zip or date that won't parse.
--    try_cast / try_to_date return null instead of failing. (Ticket 08 quarantines these instead.)
-- 3. Deduplicate on customer_unique_id, keeping the latest updated_at, then the latest
--    _ingested_at, then the greatest _source_file. row_number() over (partition by ... order by ...)
--    and `qualify` keep one row per Customer.
select *
from {{ source('bronze', 'customers') }}
