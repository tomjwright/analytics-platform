# Bronze ingestion uses Auto Loader in a job task, not a Lakeflow pipeline

Bronze is loaded by Auto Loader (`cloudFiles`) in a Python job task run with `availableNow`, not by a Lakeflow Declarative Pipeline or dbt. This keeps every ingestion mechanic visible (file discovery, checkpoints, schema inference and evolution, `_rescued_data`) for learning, avoids Free Edition's limit of one active pipeline per type, and leaves dbt owning Silver and Gold.
