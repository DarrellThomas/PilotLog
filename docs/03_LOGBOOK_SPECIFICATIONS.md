# PilotLog — Project Specifications

**Purpose:** This document contains the WHAT — the detailed requirements, features, and acceptance criteria for the PilotLog system.

---

## Document Control

| Field | Value |
|-------|-------|
| Project Name | PilotLog |
| Version | 0.1.0 |
| Status | Draft |
| Last Updated | 2025-01-24 |
| Author | Darrell + Claude |

---

## 1. EXECUTIVE SUMMARY

### 1.1 Problem Statement

A 35-year flying career spans multiple employers (civilian, USAF, Southwest Airlines), each with different record formats. Existing logbook solutions are either paper-based, clunky spreadsheets, or cloud-dependent commercial apps that don't offer the visualization and query capabilities a data-driven pilot wants. There's no "Bloomberg terminal for your logbook."

### 1.2 Solution Overview

PilotLog is a local-first web application that consolidates flight records from multiple sources into a single queryable database, providing rich visualizations (route maps, rolling totals, trend gauges) and flexible querying (by crew, tail, airport, date range, aircraft type). Designed for single-user local operation first, with architecture to support multi-user deployment for SWAPA pilots later.

### 1.3 Success Metrics

| Metric | Current State | Target | Measurement |
|--------|--------------|--------|-------------|
| Time to answer "how much did I fly with X?" | Minutes (manual search) | < 5 seconds | Query response time |
| Logbook sources consolidated | 0 | 3 (SWA, USAF, civilian) | Import success |
| Query flexibility | Limited (grep/Excel) | Any combination of filters | Feature completion |
| Visualization | None | Route map + gauges + charts | Feature completion |

---

## 2. SCOPE

### 2.1 In Scope (Phase 1-5)

- [x] Import SWA CSV files (all years)
- [ ] SQLite database with complete schema
- [ ] REST API for all queries
- [ ] Route map visualization with intensity
- [ ] Date range filtering
- [ ] Rolling 7/30/60/90/365 day totals
- [ ] Query by: crew, tail, aircraft type, airport, route
- [ ] Statistics dashboard
- [ ] Dark mode UI

### 2.2 Out of Scope (Phase 1-5)

- [ ] Multi-user authentication
- [ ] Cloud deployment
- [ ] Mobile native app
- [ ] Real-time flight tracking integration
- [ ] Automatic import from airline systems

### 2.3 Future Considerations (Phase 6+)

- [ ] USAF data import
- [ ] Civilian data import
- [ ] Multi-user web deployment for SWAPA
- [ ] Docker/executable distribution
- [ ] PDF export for FAA/insurance
- [ ] Integration with ForeFlight or LogTen Pro

---

## 3. USER STORIES

### 3.1 User Persona

**Persona: Darrell (Primary User)**
- Role: Southwest Airlines Captain, former USAF F-16 pilot
- Goals: Consolidate 35 years of flight records, visualize career patterns, quickly answer questions about flight history
- Pain Points: Data scattered across formats, no good visualization tools, commercial apps are cloud-dependent
- Technical Level: High (runs own AI lab, comfortable with CLI and code)

**Persona: SWAPA Pilot (Future User)**
- Role: Southwest Airlines pilot (various experience levels)
- Goals: Track own flight time, visualize routes, monitor rolling limits
- Pain Points: Same as above, but less technical
- Technical Level: Medium (can follow instructions, prefers GUI)

### 3.2 User Stories

#### Epic 1: Data Import

| ID | User Story | Priority | Status |
|----|-----------|----------|--------|
| US-001 | As a pilot, I want to import my SWA CSV files so that my flight history is in the system | P0 | Pending |
| US-002 | As a pilot, I want to see a summary after import showing flights imported, errors, and totals | P0 | Pending |
| US-003 | As a pilot, I want to re-import a file without creating duplicates | P1 | Pending |
| US-004 | As a pilot, I want to import USAF flight records (future) | P2 | Pending |
| US-005 | As a pilot, I want to import civilian flight records (future) | P2 | Pending |

**US-001 Acceptance Criteria:**
- [ ] Given a valid SWA CSV file, when I import it, then all flight records are added to the database
- [ ] Given multiple CSV files, when I import them, then they are merged chronologically
- [ ] Given a file with the old format (no tail number), when I import it, then it succeeds with null tail

**US-002 Acceptance Criteria:**
- [ ] Given an import operation, when it completes, then I see: total rows processed, successful imports, skipped rows, total new block time added

#### Epic 2: Route Map Visualization

| ID | User Story | Priority | Status |
|----|-----------|----------|--------|
| US-010 | As a pilot, I want to see a map of all routes I've flown | P0 | Pending |
| US-011 | As a pilot, I want route lines to be brighter/thicker based on frequency | P0 | Pending |
| US-012 | As a pilot, I want to filter the map by date range | P0 | Pending |
| US-013 | As a pilot, I want to filter the map by year (quick select) | P1 | Pending |
| US-014 | As a pilot, I want to click a route and see details (count, first/last date, aircraft) | P1 | Pending |
| US-015 | As a pilot, I want to see an animation of routes being drawn chronologically | P2 | Pending |

**US-010 Acceptance Criteria:**
- [ ] Given flight data exists, when I view the map, then I see great circle lines connecting all city pairs
- [ ] Given flights to 125 airports, when I view the map, then all airports are represented

**US-011 Acceptance Criteria:**
- [ ] Given KHOU-KDEN flown 50 times and KHOU-PHNL flown 5 times, when I view the map, then KHOU-KDEN line is visually more prominent

#### Epic 3: Rolling Totals & Gauges

| ID | User Story | Priority | Status |
|----|-----------|----------|--------|
| US-020 | As a pilot, I want to see my rolling 30/60/90 day flight time | P0 | Pending |
| US-021 | As a pilot, I want to see my rolling 365 day (calendar year) flight time | P0 | Pending |
| US-022 | As a pilot, I want gauges to show limits (FAR 117, contract) with color coding | P1 | Pending |
| US-023 | As a pilot, I want to see "burn rate" projection (at current pace, you'll hit X by date Y) | P2 | Pending |
| US-024 | As a pilot, I want rolling totals calculated as of any selected date, not just today | P2 | Pending |

**US-020 Acceptance Criteria:**
- [ ] Given today's date, when I view the dashboard, then I see accurate totals for last 30, 60, and 90 days
- [ ] Given a date range filter, when I change it, then rolling totals update accordingly

#### Epic 4: Query & Filter

| ID | User Story | Priority | Status |
|----|-----------|----------|--------|
| US-030 | As a pilot, I want to search flights by crew member name | P0 | Pending |
| US-031 | As a pilot, I want to search flights by tail number | P0 | Pending |
| US-032 | As a pilot, I want to search flights by aircraft type | P0 | Pending |
| US-033 | As a pilot, I want to search flights by airport (origin or destination) | P0 | Pending |
| US-034 | As a pilot, I want to search flights by specific route (city pair) | P1 | Pending |
| US-035 | As a pilot, I want to combine multiple filters (e.g., crew X in aircraft type Y) | P1 | Pending |
| US-036 | As a pilot, I want to export query results to CSV | P2 | Pending |

**US-030 Acceptance Criteria:**
- [ ] Given flights with FO DORRIS JAIME, when I search "DORRIS", then all flights with that crew member appear
- [ ] Given search results, when I view them, then I see date, route, block time, and aircraft

#### Epic 5: Statistics Dashboard

| ID | User Story | Priority | Status |
|----|-----------|----------|--------|
| US-040 | As a pilot, I want to see total career statistics (flights, hours, airports, aircraft) | P0 | Pending |
| US-041 | As a pilot, I want to see breakdown by aircraft type | P1 | Pending |
| US-042 | As a pilot, I want to see my most frequent routes | P1 | Pending |
| US-043 | As a pilot, I want to see my most frequent crew members | P1 | Pending |
| US-044 | As a pilot, I want to see year-over-year comparison | P2 | Pending |
| US-045 | As a pilot, I want to see records (longest leg, shortest leg, most flights in a day) | P2 | Pending |

---

## 4. FUNCTIONAL REQUIREMENTS

### 4.1 Feature: SWA CSV Import

**Description:** Parse Southwest Airlines CSV export files and load into database.

**Input Format (SWA CSV):**
```
TotalBlockhrsmins
645:18

TAFB_RadialScale1_MinimumValue,TAFB_RadialScale1_MaximumValue,...
0,1000,645,800,1000

DATE,Flight,dhd,From,Depart,To,Arrive,Block,Tail_Number,A_C_Type,TakeOff,Landing,CoPilot
2025-01-10,WN1052,,KHOU,8:58,KSAN,12:10,312,N8867Q,737-7M8, , ,FO  ZURCA JULIAN *JACKSON* [114706]
```

**Field Mapping:**

| CSV Field | DB Field | Transform |
|-----------|----------|-----------|
| DATE | flight_date | Parse as YYYY-MM-DD |
| Flight | flight_number | Strip "WN" prefix, store as string |
| dhd | is_deadhead | "DH" → true, else false |
| From | origin | Uppercase, validate ICAO |
| Depart | departure_time | Parse HH:MM to minutes since midnight |
| To | destination | Uppercase, validate ICAO |
| Arrive | arrival_time | Parse HH:MM to minutes since midnight |
| Block | block_minutes | Integer (already in minutes) |
| Tail_Number | tail_number | Uppercase, nullable |
| A_C_Type | aircraft_type | Normalize (see below) |
| TakeOff | pic_takeoff | "1" → true, else false |
| Landing | pic_landing | "1" → true, else false |
| CoPilot | crew_name, crew_id | Parse "FO NAME [ID]" format |

**Aircraft Type Normalization:**
| Raw | Normalized |
|-----|------------|
| 737-700 | B737-700 |
| 737-73W | B737-700 |
| 737-73H | B737-700 |
| 737-800 | B737-800 |
| 737-8H4 | B737-800 |
| 737-7M8 | B737-MAX7 |
| 737-7T8 | B737-MAX7 |
| etc. | (maintain lookup table) |

**Processing:**
1. Skip header rows (lines 1-7)
2. Parse each data row
3. Validate required fields (date, from, to)
4. Calculate derived fields
5. Insert into database
6. Track success/failure counts

**Error Handling:**
| Condition | Response |
|-----------|----------|
| Malformed date | Skip row, log error |
| Missing origin/destination | Skip row, log error |
| Missing block time on non-deadhead | Warn, calculate from times if possible |
| Unknown aircraft type | Warn, store raw value |
| Duplicate flight (same date/flight/from/to) | Skip or update based on config |

### 4.2 Feature: Route Map

**Description:** Interactive map showing all routes flown with intensity visualization.

**Inputs:**
| Input | Type | Required | Default |
|-------|------|----------|---------|
| date_from | date | No | Earliest flight |
| date_to | date | No | Latest flight |
| year | integer | No | All years |

**Processing:**
1. Query all unique city pairs in date range
2. Count flights per city pair
3. Look up airport coordinates (static lookup table)
4. Calculate line intensity (log scale of count)
5. Generate GeoJSON for map layer

**Outputs:**
| Output | Type | Description |
|--------|------|-------------|
| routes | GeoJSON | Line features with properties (count, intensity) |
| airports | GeoJSON | Point features with properties (name, count) |

### 4.3 Feature: Rolling Calculations

**Description:** Calculate flight time totals for rolling windows.

**Inputs:**
| Input | Type | Required | Default |
|-------|------|----------|---------|
| as_of_date | date | No | Today |
| windows | int[] | No | [7, 30, 60, 90, 365] |

**Processing:**
1. For each window, sum block_minutes where flight_date > (as_of_date - window_days)
2. Calculate flights count in same windows
3. Optionally calculate legs per day average

**Outputs:**
| Output | Type | Description |
|--------|------|-------------|
| rolling_totals | object | { window_days: { minutes, flights, hours_formatted } } |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

### 5.1 Performance

| Requirement | Specification |
|-------------|--------------|
| Query response | < 200ms for any filter combination |
| Map render | < 2s initial, < 500ms filter update |
| Import speed | > 100 flights/second |
| Database size | < 10MB for 10,000 flights |

### 5.2 Reliability

| Requirement | Specification |
|-------------|--------------|
| Data integrity | No data loss on crash (SQLite WAL mode) |
| Backup | Optional auto-backup before import |
| Recovery | Database is single file, easily copied |

### 5.3 Compatibility

| Requirement | Specification |
|-------------|--------------|
| Browsers | Chrome 90+, Firefox 90+, Safari 14+ |
| OS | Linux (primary), macOS, Windows (via Docker) |
| Python | 3.11+ |
| Node | 18+ (for frontend build) |

---

## 6. DATA SPECIFICATIONS

### 6.1 Database Schema

**Table: flights**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique identifier |
| source | TEXT | NOT NULL | 'swa', 'usaf', 'civilian', 'manual' |
| flight_date | TEXT | NOT NULL | ISO 8601 date |
| flight_number | TEXT | | Airline flight number |
| origin | TEXT | NOT NULL | ICAO airport code |
| destination | TEXT | NOT NULL | ICAO airport code |
| departure_time | INTEGER | | Minutes since midnight (local) |
| arrival_time | INTEGER | | Minutes since midnight (local) |
| block_minutes | INTEGER | NOT NULL DEFAULT 0 | Block time in minutes |
| tail_number | TEXT | | Aircraft registration |
| aircraft_type_raw | TEXT | | Original aircraft type string |
| aircraft_type | TEXT | | Normalized aircraft type |
| is_deadhead | INTEGER | NOT NULL DEFAULT 0 | 1 if deadhead |
| pic_takeoff | INTEGER | NOT NULL DEFAULT 0 | 1 if PIC takeoff |
| pic_landing | INTEGER | NOT NULL DEFAULT 0 | 1 if PIC landing |
| crew_position | TEXT | | 'CA' or 'FO' (parsed from crew field) |
| crew_name | TEXT | | Crew member name |
| crew_id | TEXT | | Crew member employee ID |
| remarks | TEXT | | Free-form notes |
| created_at | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | Record creation time |
| updated_at | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | Last update time |
| import_batch_id | TEXT | | UUID of import batch |

**Indexes:**
- flight_date (most queries filter by date)
- origin, destination (route queries)
- crew_name (crew queries)
- tail_number (tail queries)
- aircraft_type (type queries)

**Table: flight_attributes**

For sparse/source-specific data:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique identifier |
| flight_id | INTEGER | FOREIGN KEY → flights.id | Parent flight |
| attribute_name | TEXT | NOT NULL | Attribute key |
| attribute_value | TEXT | NOT NULL | Attribute value |
| attribute_unit | TEXT | | Optional unit (minutes, count, etc.) |

**Table: airports**

Static lookup data:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| icao | TEXT | PRIMARY KEY | ICAO code |
| iata | TEXT | | IATA code |
| name | TEXT | | Airport name |
| city | TEXT | | City name |
| country | TEXT | | Country code |
| latitude | REAL | | Decimal degrees |
| longitude | REAL | | Decimal degrees |
| timezone | TEXT | | IANA timezone |

**Table: import_batches**

Track import operations:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | UUID |
| source | TEXT | NOT NULL | Import source type |
| filename | TEXT | | Original filename |
| imported_at | TEXT | NOT NULL | Timestamp |
| rows_processed | INTEGER | | Total rows in file |
| rows_imported | INTEGER | | Successfully imported |
| rows_skipped | INTEGER | | Skipped due to errors |
| rows_duplicate | INTEGER | | Skipped as duplicates |

**Table: schema_version**

| Field | Type | Description |
|-------|------|-------------|
| version | INTEGER | Current schema version |
| applied_at | TEXT | When migration was applied |

### 6.2 Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────────┐
│     flights     │───────│  flight_attributes  │
│─────────────────│ 1   * │─────────────────────│
│ id (PK)         │       │ id (PK)             │
│ source          │       │ flight_id (FK)      │
│ flight_date     │       │ attribute_name      │
│ origin ─────────│──┐    │ attribute_value     │
│ destination ────│──│    └─────────────────────┘
│ block_minutes   │  │
│ tail_number     │  │    ┌─────────────────────┐
│ aircraft_type   │  │    │      airports       │
│ crew_name       │  │    │─────────────────────│
│ ...             │  └───▶│ icao (PK)           │
│ import_batch_id │──┐    │ name                │
└─────────────────┘  │    │ latitude            │
                     │    │ longitude           │
┌─────────────────┐  │    └─────────────────────┘
│  import_batches │◀─┘
│─────────────────│
│ id (PK)         │
│ source          │
│ filename        │
│ imported_at     │
│ rows_processed  │
└─────────────────┘
```

---

## 7. API SPECIFICATIONS

### 7.1 Endpoint: GET /api/flights

**Description:** Query flights with filters.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| date_from | date | Filter flights on or after |
| date_to | date | Filter flights on or before |
| origin | string | Filter by origin airport |
| destination | string | Filter by destination airport |
| crew | string | Filter by crew name (partial match) |
| tail | string | Filter by tail number |
| aircraft_type | string | Filter by aircraft type |
| limit | int | Max results (default 100) |
| offset | int | Pagination offset |

**Response (200 OK):**
```json
{
  "flights": [
    {
      "id": 1,
      "flight_date": "2025-01-10",
      "flight_number": "WN1052",
      "origin": "KHOU",
      "destination": "KSAN",
      "block_minutes": 312,
      "block_formatted": "5:12",
      "tail_number": "N8867Q",
      "aircraft_type": "B737-MAX7",
      "crew_name": "ZURCA JULIAN",
      "is_deadhead": false
    }
  ],
  "total": 4388,
  "limit": 100,
  "offset": 0
}
```

### 7.2 Endpoint: GET /api/stats

**Description:** Get aggregate statistics.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| date_from | date | Filter range start |
| date_to | date | Filter range end |

**Response (200 OK):**
```json
{
  "total_flights": 4388,
  "total_block_minutes": 503102,
  "total_block_formatted": "8385:02",
  "unique_airports": 125,
  "unique_aircraft": 874,
  "date_range": {
    "first_flight": "2014-02-19",
    "last_flight": "2025-12-31"
  },
  "by_aircraft_type": [
    { "type": "B737-700", "flights": 2572, "minutes": 280000 },
    { "type": "B737-800", "flights": 288, "minutes": 45000 }
  ],
  "by_year": [
    { "year": 2014, "flights": 278, "minutes": 31525 },
    { "year": 2015, "flights": 413, "minutes": 44209 }
  ]
}
```

### 7.3 Endpoint: GET /api/rolling

**Description:** Get rolling window totals.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| as_of | date | Calculate as of this date (default: today) |

**Response (200 OK):**
```json
{
  "as_of": "2025-01-24",
  "windows": {
    "7": { "flights": 12, "minutes": 1850, "formatted": "30:50" },
    "30": { "flights": 45, "minutes": 7200, "formatted": "120:00" },
    "60": { "flights": 82, "minutes": 13500, "formatted": "225:00" },
    "90": { "flights": 110, "minutes": 18000, "formatted": "300:00" },
    "365": { "flights": 320, "minutes": 64500, "formatted": "1075:00" }
  }
}
```

### 7.4 Endpoint: GET /api/routes

**Description:** Get aggregated route data for map.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| date_from | date | Filter range start |
| date_to | date | Filter range end |

**Response (200 OK):**
```json
{
  "routes": [
    {
      "origin": "KHOU",
      "destination": "KDEN",
      "count": 367,
      "total_minutes": 42000,
      "first_flown": "2014-03-15",
      "last_flown": "2025-01-30"
    }
  ],
  "airports": [
    {
      "icao": "KHOU",
      "name": "Houston Hobby",
      "latitude": 29.6454,
      "longitude": -95.2789,
      "departures": 527,
      "arrivals": 527
    }
  ]
}
```

### 7.5 Endpoint: POST /api/import

**Description:** Import a CSV file.

**Request:**
- Content-Type: multipart/form-data
- Body: file (CSV file)

**Response (200 OK):**
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "2025.csv",
  "rows_processed": 320,
  "rows_imported": 318,
  "rows_skipped": 1,
  "rows_duplicate": 1,
  "errors": [
    { "row": 45, "message": "Invalid date format" }
  ],
  "summary": {
    "new_block_minutes": 38718,
    "new_block_formatted": "645:18",
    "date_range": "2025-01-10 to 2025-12-31"
  }
}
```

### 7.6 Endpoint: GET /api/airports

**Description:** Get airport lookup data.

**Response (200 OK):**
```json
{
  "airports": [
    {
      "icao": "KHOU",
      "iata": "HOU",
      "name": "William P. Hobby Airport",
      "city": "Houston",
      "latitude": 29.6454,
      "longitude": -95.2789
    }
  ]
}
```

---

## 8. USER INTERFACE SPECIFICATIONS

### 8.1 Overall Layout

```
┌────────────────────────────────────────────────────────────────┐
│  PilotLog                          [Import] [Settings]    ☾/☀  │
├────────────────────────────────────────────────────────────────┤
│  [Dashboard] [Map] [Flights] [Stats]                           │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│                      Main Content Area                         │
│                                                                │
│                                                                │
│                                                                │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│  Total: 8,385:02 │ Flights: 4,388 │ Airports: 125 │ Aircraft: 874 │
└────────────────────────────────────────────────────────────────┘
```

### 8.2 Dashboard Screen

**Purpose:** At-a-glance career overview with rolling totals.

```
┌─────────────────────────────────────────────────────────────────┐
│  ROLLING TOTALS                              As of: [2025-01-24]│
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│   │  7-DAY  │  │ 30-DAY  │  │ 60-DAY  │  │ 90-DAY  │           │
│   │  30:50  │  │ 120:00  │  │ 225:00  │  │ 300:00  │           │
│   │ ██████░░│  │ ████░░░░│  │ █████░░░│  │ ██████░░│           │
│   │ 12 flts │  │ 45 flts │  │ 82 flts │  │110 flts │           │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘           │
│                                                                 │
│   ┌────────────────────────────────────┐  ┌──────────────────┐ │
│   │          365-DAY TREND             │  │    THIS YEAR     │ │
│   │     ╭───────────────╮              │  │                  │ │
│   │ hrs │               ╰──            │  │   645:18         │ │
│   │     │      ╭────╮                  │  │   318 flights    │ │
│   │     ╰──────╯    ╰─────             │  │   Goal: 800:00   │ │
│   │     J F M A M J J A S O N D        │  │   ████████░░░░   │ │
│   └────────────────────────────────────┘  └──────────────────┘ │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  QUICK STATS                                                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐│
│  │ Most Flown  │ │ Last Flight │ │ Best Month  │ │ Total PIC  ││
│  │ KHOU-KDEN   │ │ 2025-01-10  │ │ 2018-07     │ │ 4,102 legs ││
│  │ 367 times   │ │ KSAN-KMSY   │ │ 92:30       │ │ 93.5%      ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 8.3 Map Screen

**Purpose:** Visual route map with filtering.

```
┌─────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Date Range: [2014-02-19] to [2025-12-31]  [All] [Year ▼] │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                                                             ││
│  │                    ╱╲                                       ││
│  │           ●═══════●══●                                      ││
│  │          ╱ ╲      ║                                         ││
│  │         ╱   ╲     ║     (Map with route lines)              ││
│  │        ●─────●════●                                         ││
│  │         ╲   ╱    ╱║                                         ││
│  │          ╲ ╱    ╱ ║                                         ││
│  │           ●════●══●                                         ││
│  │                                                             ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Selected: KHOU → KDEN │ 367 flights │ First: 2014-03-15    ││
│  │ Total: 42,000 min │ Avg: 114 min │ Aircraft: 737-700 (85%) ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 8.4 Flights Screen

**Purpose:** Searchable, filterable flight table.

```
┌─────────────────────────────────────────────────────────────────┐
│  FILTERS                                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│
│  │Date Range│ │ Crew     │ │ Tail     │ │ Type     │ │ Airport││
│  │[__]-[__] │ │[_______] │ │[_______] │ │[▼ All  ] │ │[______]││
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘│
│                                          [Search]  [Clear]      │
├─────────────────────────────────────────────────────────────────┤
│  Date       │ Flight │ Route         │ Block │ Tail   │ Crew   │
│─────────────┼────────┼───────────────┼───────┼────────┼────────│
│  2025-01-10 │ WN1052 │ KHOU → KSAN   │ 5:12  │ N8867Q │ ZURCA  │
│  2025-01-10 │ WN2361 │ KSAN → KMSY   │ 5:33  │ N8772M │ ZURCA  │
│  2025-01-11 │ WN470  │ KMSY → KHOU   │ 1:15  │ N8842L │ ZURCA  │
│  2025-01-11 │ WN112  │ KHOU → MROC   │ 5:35  │ N8757L │ ZURCA  │
│  ...        │ ...    │ ...           │ ...   │ ...    │ ...    │
├─────────────────────────────────────────────────────────────────┤
│  Showing 1-100 of 4,388 │ Total Block: 8,385:02 │ [◀ 1 2 3 ▶] │
└─────────────────────────────────────────────────────────────────┘
```

### 8.5 Theme

**Dark Mode (Default):**
- Background: #1a1a2e
- Surface: #16213e
- Primary accent: #0f3460
- Highlight: #e94560
- Text: #eaeaea
- Muted text: #888888
- Success: #00b894
- Warning: #fdcb6e
- Danger: #d63031

**Typography:**
- Headers: Inter or system sans-serif, bold
- Body: Inter or system sans-serif, regular
- Monospace (times, codes): JetBrains Mono or system monospace

---

## 9. TESTING REQUIREMENTS

### 9.1 Test Scenarios

| ID | Scenario | Steps | Expected | Priority |
|----|----------|-------|----------|----------|
| TC-001 | Import valid SWA CSV | Upload 2025.csv | 318 flights imported | P0 |
| TC-002 | Import all years | Upload 12 files | 4,388 flights total | P0 |
| TC-003 | Query by crew name | Search "DORRIS" | Returns all DORRIS flights | P0 |
| TC-004 | Rolling 30-day calculation | View dashboard | Correct total | P0 |
| TC-005 | Route map renders | View map | All routes visible | P0 |
| TC-006 | Date filter works | Set range 2020-01-01 to 2020-12-31 | Only 2020 flights | P0 |
| TC-007 | Re-import same file | Import 2025.csv twice | No duplicates | P1 |
| TC-008 | Handle missing tail number | Import 2014.csv | Imports with null tail | P1 |

### 9.2 Edge Cases

| Case | Input | Expected |
|------|-------|----------|
| Empty date range | date_from > date_to | Empty result, no error |
| No matching flights | crew="NONEXISTENT" | Empty result, no error |
| Single flight | One-row CSV | Imports successfully |
| Future date | as_of="2030-01-01" | Calculate correctly |
| Midnight crossing | Depart 23:00, Arrive 01:00 | Correct block time |

---

## 10. CONSTRAINTS & ASSUMPTIONS

### 10.1 Constraints

| Constraint | Impact | Mitigation |
|------------|--------|------------|
| SQLite single-writer | Can't handle concurrent imports | Queue imports, single user is fine |
| Browser-only UI | No native app | PWA could be added later |
| Local-first | No sync between devices | Export/import database file |

### 10.2 Assumptions

| Assumption | If False |
|------------|----------|
| SWA CSV format is stable | Build format version detection |
| User has Python 3.11+ | Document installation, consider Docker |
| 4K flights fits in memory | Implement pagination/streaming |
| ICAO codes are valid | Add validation/lookup |

---

## 11. GLOSSARY

| Term | Definition |
|------|------------|
| Block time | Time from pushback to parking (chocks to chocks) |
| Deadhead | Positioning flight as passenger, no duty time logged |
| PIC | Pilot in Command |
| ICAO | International Civil Aviation Organization (4-letter airport codes) |
| Rolling window | Sum of values in the N days preceding a given date |
| City pair | Origin-destination combination (e.g., KHOU-KDEN) |
| Leg | Single flight segment |
| FAR 117 | Federal Aviation Regulation governing flight time limits |
| TAFB | Time Away From Base |

---

## 12. APPENDICES

### Appendix A: SWA CSV Sample Data

See `/mnt/user-data/uploads/2025.csv` for complete example.

### Appendix B: Airport Coordinates Source

Use OurAirports data (public domain):
https://ourairports.com/data/

### Appendix C: Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1.0 | 2025-01-24 | Claude + Darrell | Initial specification |

---

*This specification is the contract. Code that doesn't meet spec is incomplete code.*
