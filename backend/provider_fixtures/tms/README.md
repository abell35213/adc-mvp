# TMS provider fixtures

These JSON files are minimal sample TMS payloads representing what the
``app.services.tms_sync_service`` worker receives from a vendor TMS via
the ODBC connector.

The shapes intentionally mirror the column allowlists in:

* ``app/db/repo/dispatch_instructions.py``
* ``app/db/repo/weigh_station_reports.py``
* ``app/db/repo/loading_dock_reports.py``

Each row carries an ``external_id`` — the upsert key used by
``upsert_from_tms`` to keep the row idempotent across syncs. Manually
entered rows have ``external_id IS NULL`` and are never overwritten by
the sync worker.

Files:

* `dispatch_instructions.json` — two trips, one with `forced_dispatch_flag`
  to demonstrate the brief's compliance callout.
* `weigh_station_reports.json` — one over-weight cited ticket and one
  passing ticket.
* `loading_dock_reports.json` — one improperly-loaded report and one clean
  load.
