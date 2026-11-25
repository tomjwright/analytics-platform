# Glossary

**Customer**: a person who buys on Olist, identified by `customer_unique_id`. Olist's `customer_id` is a new id for every order, so it is an order attribute, not a Customer. _Avoid_: account, client.

**Order**: one checkout by a Customer, with a status and purchase, approval, shipping and delivery timestamps. _Avoid_: transaction.

**Order Item**: one line of an Order: one product from one seller, with price and freight. An Order has one or more Order Items.

**Payment**: one way an Order was paid for (card, boleto, voucher, debit), with an amount and instalments. An Order can have several Payments. _Avoid_: transaction.

**File Drop**: the set of files the chaos generator writes for one ingest date. Customers arrive as a full CSV snapshot; Orders, Order Items and Payments arrive as incremental newline-delimited JSON.

**Quarantined Record**: a Bronze row that fails a Silver rule (null key, unparseable date, negative amount, missing parent). It is kept with its original payload and a reason code, never silently dropped. _Avoid_: rejected, dead letter.
