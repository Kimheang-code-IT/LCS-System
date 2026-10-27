"""Excel Import & Export engine.

A module-aware registry (``registry.py``), backend-driven template generation
(``templates.py``) and the upload → validate → preview → confirm pipeline
(``service.py``). Nothing here reads arbitrary database tables: every importable
module is an explicit, allowlisted entry that reuses its owning module's service
layer for validation and writes, so import follows exactly the business rules
the API enforces.
"""
