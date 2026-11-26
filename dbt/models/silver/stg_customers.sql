-- TODO(ticket 04): one row per Customer, cleaned and standardised.
-- 1. Standardise: trim and lower-case text; left-pad zip_code_prefix to 5 digits (Olist
--    dropped the leading zero: 1001 is really 01001); cast updated_at to a date.
-- 2. Drop rows Silver can't trust: no customer_unique_id, or a zip or date that won't parse.
--    try_cast / try_to_date return null instead of failing. (Ticket 08 quarantines these instead.)
-- 3. Deduplicate on customer_unique_id, keeping the latest updated_at, then the latest
--    _ingested_at, then the greatest _source_file. row_number() over (partition by ... order by ...)
--    and `qualify` keep one row per Customer.
with cleaned as (
    select
        trim(customer_unique_id) as customer_unique_id,
        case
            when trim(zip_code_prefix) rlike '^[0-9]{1,5}$'
                then lpad(trim(zip_code_prefix), 5, '0')
        end as zip_code_prefix,
        trim(lower(city)) as city,
        trim(upper(state)) as state,
        try_to_date(updated_at) as updated_at,
        _ingested_at,
        trim(_source_file) as _source_file
    from {{ source('bronze', 'customers') }}
),

remove_errors as (
    select * from cleaned
    where
        updated_at is not null
        and nullif(customer_unique_id, '') is not null
        and zip_code_prefix is not null
),

deduplicated as (
    select * from remove_errors
    qualify row_number() over (
        partition by customer_unique_id
        order by updated_at desc, _ingested_at desc, _source_file desc
    ) = 1
)

select * from deduplicated
