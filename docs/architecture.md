# Architecture

 Layers

 1. Core Layer
Reusable components:
- ingestion/
- validation/
- logging/
- scheduling/
- storage/
- utils/

2. Module Layer
Organised by category:
- operational/
- intelligence/
- ai_training/

Each module contains:
- ingest.py
- validate.py
- transform.py
- load.py
- run.py

3. Shared Layer
- schemas/
- config/
- common_models/
