# Logbook Project Principles

**Purpose:** This document extends Universal Principles with logbook-specific guidelines. These principles define HOW we build the pilot logbook system.

---

## Project Identity

**Project Name:** PilotLog  
**Type:** Hybrid (Tool now, Infrastructure later)  
**Primary Domain:** Data Visualization / Personal Analytics Web App  

---

## 1. ARCHITECTURAL DECISIONS

### 1.1 System Boundaries

| Component | Responsibility | Owns Data? |
|-----------|---------------|------------|
| Database (SQLite) | Persistent storage, query engine | Yes |
| Import Pipeline | Parse CSV/Excel → normalize → insert | No |
| API Layer (FastAPI) | Expose data via REST endpoints | No |
| Frontend (Browser) | Visualization, user interaction | No |

### 1.2 Data Flow

```
[CSV/Excel Files] → [Import Scripts] → [SQLite DB] → [FastAPI] → [Browser UI]
                                            ↓
                                    [Export Functions] → [PDF/CSV Reports]
```

### 1.3 External Dependencies

| Dependency | Purpose | Replaceable? |
|------------|---------|--------------|
| SQLite | Local database, zero config | Yes (Postgres for multi-user) |
| FastAPI | Python API framework | Yes (Flask, Starlette) |
| Deck.gl or Leaflet | Map visualization | Yes (Mapbox, OpenLayers) |
| Svelte or React | Frontend framework | Yes (either works) |
| Pandas | Data import/manipulation | Yes (polars, native Python) |

**Rationale:** All choices prioritize local-first operation, portability, and minimal external dependencies. No cloud services required for core functionality.

---

## 2. TECHNOLOGY STACK PRINCIPLES

### 2.1 Language/Framework

- **Backend:** Python 3.11+
- **Frontend:** Svelte (lighter weight) or React (more ecosystem)
- **Database:** SQLite (Phase 1), PostgreSQL-ready (Phase 6)
- **Rationale:** Python for rapid development and data manipulation strengths. SQLite for zero-config local operation.

### 2.2 Project-Specific Conventions

- **File naming:** snake_case for Python, kebab-case for frontend components
- **Directory structure:** See Section 8.1
- **Import ordering:** stdlib → third-party → local (enforced by isort)
- **Configuration:** Environment variables + config.py with sensible defaults

### 2.3 Dependency Management

- **Backend:** pip + requirements.txt (or Poetry if complexity warrants)
- **Frontend:** npm + package-lock.json
- **Version pinning:** Exact versions in production, ranges in development
- **Update cadence:** Security updates immediately, features quarterly

---

## 3. DOMAIN-SPECIFIC RULES

### 3.1 Aviation Data Invariants

These must never be violated:

- [ ] All times stored in minutes (integer) for calculations, formatted for display
- [ ] All dates stored as ISO 8601 (YYYY-MM-DD)
- [ ] All airports stored as ICAO codes (4 characters, uppercase)
- [ ] Block time = Arrive - Depart (calculated, not stored redundantly)
- [ ] Deadhead legs have zero block time
- [ ] Total time calculations must be exact (no floating point drift)

### 3.2 Data Validation

- **Input validation:** At import time, reject malformed rows with clear error messages
- **Airport codes:** Validate against known ICAO codes (warn on unknown, don't reject)
- **Dates:** Must parse unambiguously; reject ambiguous formats
- **Times:** Accept HH:MM or integer minutes; normalize to minutes internally

### 3.3 Data Source Integrity

- **Preserve original data:** Store raw imported values alongside normalized values
- **Track data provenance:** Every flight record knows its source (SWA, USAF, civilian, manual)
- **No destructive imports:** Re-importing a file should be idempotent or prompt for conflict resolution

### 3.4 Security Principles

- **Local-first:** No data leaves the machine without explicit user action
- **No authentication needed (Phase 1):** Single user, localhost only
- **Future multi-user:** OAuth or simple auth, never roll custom crypto

---

## 4. TESTING STRATEGY

### 4.1 Test Pyramid

```
        /\
       /  \     E2E: Full import → query → display flow
      /----\
     /      \   Integration: API endpoints, DB queries
    /--------\
   /          \  Unit: Import parsers, time calculations, data validators
  /------------\
```

### 4.2 What Must Be Tested

- [ ] All import parsers (SWA CSV, future USAF, future civilian)
- [ ] Time calculation functions (rolling windows, totals)
- [ ] API endpoints return correct data shapes
- [ ] Date range filtering logic
- [ ] Edge cases: empty data, single flight, year boundaries

### 4.3 What May Skip Tests

- Generated OpenAPI schema (auto-generated)
- Simple Pydantic models (dataclass-like, no logic)
- Frontend styling (visual verification sufficient)

### 4.4 Test Data Strategy

- **Fixtures:** Sample CSV files with known values in `/tests/fixtures/`
- **Factories:** Python functions to generate flight records with specific attributes
- **Golden files:** Expected outputs for import operations

---

## 5. ERROR HANDLING STRATEGY

### 5.1 Error Categories

| Category | Handling | Example |
|----------|----------|---------|
| Import Error | Log + skip row + continue + summary report | Malformed date in CSV |
| Query Error | Return empty result + warning | Invalid date range |
| System Error | Log + graceful degradation | DB file locked |
| User Error | Helpful message in UI | No file selected |

### 5.2 Logging Principles

- **Log levels:** DEBUG for import details, INFO for operations, WARN for data issues, ERROR for failures
- **Structured logging:** JSON format for machine parsing
- **Sensitive data:** Never log full crew names in production (use employee IDs)
- **Location:** `~/.pilotlog/logs/` or configurable

### 5.3 Recovery Strategies

- **Import failures:** Partial imports allowed, summary shows successes/failures
- **DB corruption:** Backup before any write operation (optional, configurable)
- **No retry needed:** Local operations, no network dependencies

---

## 6. PERFORMANCE PRINCIPLES

### 6.1 Response Time Budgets

| Operation | Target | Max Acceptable |
|-----------|--------|----------------|
| Page load | 500ms | 2s |
| Filter/query | 100ms | 500ms |
| Map render | 1s | 3s |
| Full data import | 5s | 30s |

### 6.2 Resource Constraints

- **Memory:** Should run comfortably with 500MB (4,000 flights is small data)
- **Disk:** Database < 50MB for 10,000 flights
- **CPU:** Import can be slow; UI must stay responsive

### 6.3 Caching Strategy

- **What to cache:** Computed aggregations (rolling totals, route frequencies)
- **Cache invalidation:** On any data import or modification
- **TTLs:** Not needed for local single-user

---

## 7. DEPLOYMENT & OPERATIONS

### 7.1 Phase 1: Local Only

- **Run:** `python -m pilotlog` or `./run.sh`
- **Access:** `http://localhost:8000`
- **Data location:** `~/.pilotlog/` or current directory

### 7.2 Phase 6: Portable Distribution

**Option A: Docker**
```bash
docker run -v ~/logbook-data:/data -p 8000:8000 pilotlog
```

**Option B: Single Executable (PyInstaller)**
```bash
./pilotlog-linux-x64
```

### 7.3 Configuration

All config via environment variables with sensible defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| PILOTLOG_DB_PATH | ~/.pilotlog/logbook.db | Database location |
| PILOTLOG_PORT | 8000 | API server port |
| PILOTLOG_LOG_LEVEL | INFO | Logging verbosity |

---

## 8. AGENT MAINTAINABILITY

> "If the agent builds it, the agent can maintain it."

### 8.1 Directory Structure

```
pilotlog/
├── README.md
├── docs/
│   ├── 01_UNIVERSAL_PRINCIPLES.md
│   ├── 02_LOGBOOK_PRINCIPLES.md
│   └── 03_LOGBOOK_SPECIFICATIONS.md
├── src/
│   ├── pilotlog/
│   │   ├── __init__.py
│   │   ├── main.py              # Entry point
│   │   ├── config.py            # Configuration
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── models.py        # SQLAlchemy/Pydantic models
│   │   │   ├── schema.sql       # Raw SQL schema (reference)
│   │   │   └── queries.py       # Query functions
│   │   ├── importers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # Base importer class
│   │   │   ├── swa_csv.py       # Southwest CSV importer
│   │   │   ├── usaf.py          # USAF importer (future)
│   │   │   └── civilian.py      # Civilian importer (future)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py        # FastAPI routes
│   │   │   └── schemas.py       # Request/response schemas
│   │   └── calculations/
│   │       ├── __init__.py
│   │       ├── rolling.py       # Rolling window calculations
│   │       └── aggregations.py  # Totals, groupings
│   └── frontend/
│       ├── package.json
│       ├── src/
│       │   ├── App.svelte
│       │   ├── components/
│       │   │   ├── Dashboard.svelte
│       │   │   ├── RouteMap.svelte
│       │   │   ├── FlightTable.svelte
│       │   │   └── Gauges.svelte
│       │   └── lib/
│       │       └── api.js       # API client
│       └── public/
├── tests/
│   ├── fixtures/
│   │   └── sample_swa.csv
│   ├── test_importers.py
│   ├── test_calculations.py
│   └── test_api.py
└── scripts/
    ├── import_swa.py           # CLI import tool
    └── run_dev.sh              # Development server
```

### 8.2 Documentation Requirements

- [ ] README with setup and run instructions
- [ ] This principles document (you're reading it)
- [ ] Specifications document (03_LOGBOOK_SPECIFICATIONS.md)
- [ ] Inline docstrings for all public functions
- [ ] OpenAPI auto-generated from FastAPI

### 8.3 Decision Log

Major decisions and rationale:

| Decision | Rationale | Date |
|----------|-----------|------|
| SQLite over Postgres | Local-first, zero config, portable | 2025-01-24 |
| FastAPI over Flask | Auto OpenAPI docs, async support, modern | 2025-01-24 |
| Minutes as integer for time | Avoid floating point drift, easy math | 2025-01-24 |
| Flexible attributes table | Handle sparse data across 35-year career | 2025-01-24 |

---

## 9. SCHEMA EVOLUTION STRATEGY

Since data sources vary and requirements will evolve:

### 9.1 Migration Approach

- **Tool:** Alembic (SQLAlchemy migrations) or raw SQL scripts
- **Versioning:** Schema version stored in DB metadata table
- **Backward compatibility:** Old data must work with new schema
- **Process:** 
  1. Backup database
  2. Run migration
  3. Verify integrity
  4. Update schema version

### 9.2 Adding New Data Sources

When adding USAF or civilian data:

1. Create new importer in `importers/`
2. Map source fields to core schema
3. Add source-specific attributes to flexible attributes table
4. Update tests with new fixtures
5. Document field mappings

### 9.3 Adding New Fields

If a new field is needed (e.g., "night time"):

- **If universal:** Add column to flights table via migration
- **If source-specific:** Add to flight_attributes table (no migration needed)

---

## 10. PROJECT-SPECIFIC CODE SMELLS

Watch for these anti-patterns:

- [ ] Hardcoded date formats (use constants or config)
- [ ] String concatenation for SQL (use parameterized queries)
- [ ] Floating point for time calculations (use integer minutes)
- [ ] Mixing local and UTC times (pick one, document it)
- [ ] Airport codes without validation (at least warn)
- [ ] Import logic in API routes (keep separated)
- [ ] Frontend calling DB directly (always go through API)

---

## 11. DEFINITION OF DONE

A feature is complete when:

- [ ] Code follows Universal Principles
- [ ] Code follows these Project Principles
- [ ] Unit tests written and passing
- [ ] Manual testing performed
- [ ] Works with real SWA data (not just test fixtures)
- [ ] No console errors in browser
- [ ] Documented if user-facing

---

## Quick Reference

**Local-first:** No cloud dependencies for core functionality.

**Data integrity:** Times in minutes, dates in ISO 8601, airports in ICAO.

**Extensible:** New data sources = new importer module, same schema.

**Portable:** SQLite now, Postgres later. Browser UI, no native app needed.

---

*Last Updated: 2025-01-24*  
*Maintainer: Claude + Darrell*
