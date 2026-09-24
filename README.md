# V2X Fleet Live Intersection Simulator

A live vehicle-to-everything (V2X) intersection simulation. The React dashboard displays vehicles and traffic signals while a Python backend simulates vehicle telemetry.

## What you need

- [Python 3](https://www.python.org/downloads/)
- [Node.js](https://nodejs.org/) (includes npm)
- Git

## Run the project

First, clone the repository and enter the project folder:

```bash
git clone https://github.com/Jmsomi10/v2x-simulator.git
cd v2x-simulator
```

Open **two Terminal windows**. Keep both terminals running while using the simulator.

### Terminal 1: start the backend and vehicle simulator

```bash
cd backend
python3 -m pip install fastapi "uvicorn[standard]" websockets
python3 -m uvicorn main:app --reload
```

When it is working, the terminal will show vehicle updates such as:

```text
RSU Ingested Data -> Car Car-001: ...
```

### Terminal 2: start the dashboard

```bash
cd frontend
npm install
npm run dev
```

Open the **Local** URL printed by Vite, usually:

```text
http://localhost:5173
```

If port 5173 is already being used, Vite will use a different port, such as `http://localhost:5174`. Open the exact URL it prints.

## Stopping the project

In each terminal, press `Control + C` to stop its server.

## Troubleshooting

### The dashboard says “Waiting for vehicle data...”

Make sure the backend terminal is still running and showing `RSU Ingested Data` messages. Then refresh the dashboard page.

### Backend reports “Address already in use”

Another backend process is using port 8000. Find its process ID:

```bash
lsof -ti:8000
```

Stop the process using the number it prints:

```bash
kill <process-id>
```

Then rerun:

```bash
python3 -m uvicorn main:app --reload
```

## GitHub Pages note

The GitHub Pages deployment can display the frontend, but the live cars require the Python backend to run locally. To see live vehicle data, run both terminals above.
