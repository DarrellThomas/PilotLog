# PilotLog

**Version 0.1**

A local-first pilot logbook application for tracking flight time, visualizing routes, and monitoring FAR 117 rolling limits.

## Features

- Import Southwest Airlines CSV flight records
- Interactive route map with great circle arcs
- Rolling totals: 7-Day, 672-Hour, 60-Day, 90-Day, 365-Day
- FAR 117 limit warnings (672-hour and 365-day)
- Career statistics dashboard
- Query flights by crew, tail number, aircraft type, airport, and date range
- Dark mode UI

---

## Installation Guide (for Non-Technical Users)

### Step 1: Install Required Software

You'll need two programs installed on your computer:

**Python** (version 3.11 or newer)
- Go to https://www.python.org/downloads/
- Download and run the installer
- **Important**: Check the box that says "Add Python to PATH" during installation

**Node.js** (version 18 or newer)
- Go to https://nodejs.org/
- Download the "LTS" version and run the installer

To verify they're installed, open a terminal (Command Prompt on Windows, Terminal on Mac) and type:
```
python3 --version
node --version
```

### Step 2: Download PilotLog

Open a terminal and run:
```bash
git clone https://github.com/DarrellThomas/PilotLog.git
cd PilotLog
```

If you don't have git installed:
- **Mac**: Install Xcode Command Line Tools by running `xcode-select --install`
- **Windows**: Download from https://git-scm.com/download/win

### Step 3: Set Up the Backend

Run these commands one at a time:

```bash
# Create a virtual environment
python3 -m venv venv

# Activate it (Mac/Linux)
source venv/bin/activate

# OR on Windows:
# venv\Scripts\activate

# Install the application
pip install -e .

# Load airport data (required for the map)
python scripts/load_airports.py
```

### Step 4: Set Up the Frontend

```bash
cd src/frontend
npm install
cd ../..
```

### Step 5: Start the Application

You need two terminal windows:

**Terminal 1 - Backend:**
```bash
cd PilotLog
source venv/bin/activate
python -m pilotlog
```
You should see: `Uvicorn running on http://0.0.0.0:8000`

**Terminal 2 - Frontend:**
```bash
cd PilotLog/src/frontend
npm run dev
```
You should see: `Local: http://localhost:5173/`

### Step 6: Open in Browser

Go to http://localhost:5173 in your web browser.

---

## Using PilotLog

### Importing Your Flight Data

1. Export your flight data from CWA as a CSV file
2. In PilotLog, click the **Import** tab
3. Select your CSV file
4. The app will show how many flights were imported

### Understanding the Dashboard

- **7-Day**: Flight time in the last 7 calendar days
- **672-Hour**: Flight time in the last 28 days (FAR 117 limit: 100 hours)
- **60-Day / 90-Day**: Flight time in these windows (no FAR limit)
- **365-Day**: Flight time in the last year (FAR 117 limit: 1,000 hours)

When you're within 5% of a FAR 117 limit, the numbers turn red.

### Map View

- Blue arcs show your flight routes
- Brighter lines = more flights on that route
- Larger circles = more visits to that airport
- Use the date filters to view specific time periods

---

## Troubleshooting

**"python3 not found"**
- Make sure Python is installed and added to PATH
- On Windows, try `python` instead of `python3`

**"npm not found"**
- Make sure Node.js is installed
- Close and reopen your terminal after installing

**Map shows no routes**
- Run `python scripts/load_airports.py` to load airport coordinates
- Make sure you've imported flight data

**Port already in use**
- Another program is using port 8000 or 5173
- Close other applications or restart your computer

---

## Data Storage

Your flight data is stored locally at:
- **Mac/Linux**: `~/.pilotlog/logbook.db`
- **Windows**: `C:\Users\YourName\.pilotlog\logbook.db`

---

## Project Structure

```
PilotLog/
├── src/
│   ├── pilotlog/           # Python backend
│   │   ├── api/            # REST API
│   │   ├── database/       # Database models
│   │   └── importers/      # CSV parsers
│   └── frontend/           # Svelte web interface
├── scripts/                # Utility scripts
└── tests/                  # Test suite
```

## License

MIT
