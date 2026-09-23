import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

from mock_vehicle import main as run_vehicle_simulator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run the bundled vehicle publisher while the local simulator is up."""
    simulator_task = asyncio.create_task(run_vehicle_simulator())
    try:
        yield
    finally:
        simulator_task.cancel()
        with suppress(asyncio.CancelledError):
            await simulator_task


app = FastAPI(lifespan=lifespan)

class IntersectionManager:
    def __init__(self):
        self.dashboard_connections: list[WebSocket] = []
        self.vehicle_states = {}

    async def connect_dashboard(self, websocket: WebSocket):
        await websocket.accept()
        self.dashboard_connections.append(websocket)

    def disconnect_dashboard(self, websocket: WebSocket):
        if websocket in self.dashboard_connections:
            self.dashboard_connections.remove(websocket)

    async def update_vehicle(self, vehicle_id: str, data: dict):
        self.vehicle_states[vehicle_id] = data

    # 1. ADD THIS NEW METHOD TO BROADCAST TO ALL CLIENTS
    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.dashboard_connections:
            try:
                await connection.send_text(message)
            except (WebSocketDisconnect, RuntimeError):
                disconnected.append(connection)
        for connection in disconnected:
            self.disconnect_dashboard(connection)

manager = IntersectionManager()

@app.websocket("/v2x-fleet")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    vehicle_id = None
    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            
            vehicle_id = data.get("vehicle_id")
            await manager.update_vehicle(vehicle_id, data)
            
            print(f"📡 RSU Ingested Data -> Car {vehicle_id}: {data['position']}")
            
            # 2. ADD THIS LINE TO SEND THE DATA TO REACT
            await manager.broadcast(raw_data)
            
    except WebSocketDisconnect:
        if vehicle_id in manager.vehicle_states:
            del manager.vehicle_states[vehicle_id]
        print(f"❌ Car {vehicle_id} disconnected from network.")


@app.websocket("/v2x-dashboard")
async def dashboard_endpoint(websocket: WebSocket):
    await manager.connect_dashboard(websocket)
    # A dashboard opened after vehicles have connected should immediately show
    # their most recently received positions rather than waiting for a new tick.
    for vehicle_state in manager.vehicle_states.values():
        await websocket.send_text(json.dumps(vehicle_state))
    try:
        while True:
            # Keep the client connected; vehicle telemetry flows only outward.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)
