import asyncio
import json
import math
import time

import websockets


# Each route is a cubic Bezier curve. This keeps vehicles centered in their
# lanes while allowing a smooth tangent (and therefore a smooth heading) on turns.
ROUTES = {
    "straight": {
        "points": [(-55, -10), (-20, -10), (20, -10), (55, -10)],
        "turn_signal": "none",
    },
    "left": {
        "points": [(10, -55), (10, -16), (-16, 10), (-55, 10)],
        "turn_signal": "left",
    },
    "right": {
        # Keep the turn within the paved northeast corner: approach, tight
        # quarter-turn, then exit in the northbound lane (x = 10).
        "segments": [
            [(55, 10), (45, 10), (25, 10), (13, 10)],
            [(13, 10), (11.34, 10), (10, 11.34), (10, 13)],
            [(10, 13), (10, 25), (10, 45), (10, 55)],
        ],
        "turn_signal": "right",
    },
    "southbound": {
        "points": [(-10, 55), (-10, 20), (-10, -20), (-10, -55)],
        "turn_signal": "none",
    },
}

# A simple RSU signal plan. Only compatible movements receive a green phase.
# This is the first collision-avoidance layer; a later V2X upgrade can replace
# it with per-vehicle reservations through the intersection.
SIGNAL_PLAN = (
    ("horizontal", 8.0),
    ("all_red", 1.5),
    ("protected_left", 7.0),
    ("all_red", 1.5),
    ("vertical", 8.0),
    ("all_red", 1.5),
)
MOVEMENT_PHASE = {
    "straight": "horizontal",
    "right": "horizontal",
    "left": "protected_left",
    "southbound": "vertical",
}
PERMITTED_MOVEMENTS = {
    "horizontal": ["eastbound straight", "westbound right"],
    "protected_left": ["northbound left"],
    "vertical": ["southbound straight"],
    "all_red": [],
}
STOP_PROGRESS = 0.31


def bezier_point(points, t):
    """Return a point and its direction vector at progress t (0 through 1)."""
    p0, p1, p2, p3 = points
    u = 1 - t
    x = (u ** 3 * p0[0] + 3 * u ** 2 * t * p1[0] +
         3 * u * t ** 2 * p2[0] + t ** 3 * p3[0])
    y = (u ** 3 * p0[1] + 3 * u ** 2 * t * p1[1] +
         3 * u * t ** 2 * p2[1] + t ** 3 * p3[1])
    dx = (3 * u ** 2 * (p1[0] - p0[0]) +
          6 * u * t * (p2[0] - p1[0]) +
          3 * t ** 2 * (p3[0] - p2[0]))
    dy = (3 * u ** 2 * (p1[1] - p0[1]) +
          6 * u * t * (p2[1] - p1[1]) +
          3 * t ** 2 * (p3[1] - p2[1]))
    return x, y, dx, dy


def route_length(points):
    """Approximate curve length so all routes take a comparable amount of time."""
    length = 0
    last_x, last_y, _, _ = bezier_point(points, 0)
    for step in range(1, 101):
        x, y, _, _ = bezier_point(points, step / 100)
        length += math.hypot(x - last_x, y - last_y)
        last_x, last_y = x, y
    return length


def route_position(segments, progress):
    """Return the position on a single- or multi-segment Bezier route."""
    lengths = [route_length(segment) for segment in segments]
    total_length = sum(lengths)
    distance = progress * total_length
    traversed = 0

    for segment, length in zip(segments, lengths):
        if distance <= traversed + length:
            local_progress = (distance - traversed) / length
            return bezier_point(segment, local_progress), total_length
        traversed += length

    return bezier_point(segments[-1], 1), total_length


def target_speed(progress, maneuver):
    """Vehicles slow down before and through a turn, then gently speed back up."""
    if maneuver in ("left", "right") and 0.26 <= progress <= 0.68:
        return 4.2
    return 10.0


def current_spat():
    """Return the SPaT information broadcast by the intersection RSU."""
    cycle_length = sum(duration for _, duration in SIGNAL_PLAN)
    cycle_time = time.monotonic() % cycle_length
    elapsed = 0
    for phase, duration in SIGNAL_PLAN:
        elapsed += duration
        if cycle_time < elapsed:
            return {
                "intersection_id": "RSU-INTERSECTION-001",
                "signal_phase": phase,
                "time_to_change_seconds": round(elapsed - cycle_time, 1),
                "permitted_movements": PERMITTED_MOVEMENTS[phase],
            }
    return {
        "intersection_id": "RSU-INTERSECTION-001",
        "signal_phase": SIGNAL_PLAN[0][0],
        "time_to_change_seconds": SIGNAL_PLAN[0][1],
        "permitted_movements": PERMITTED_MOVEMENTS[SIGNAL_PLAN[0][0]],
    }


async def simulate_car(vehicle_id, vehicle_type, maneuver, starting_progress=0.0):
    uri = "ws://localhost:8000/v2x-fleet"
    route = ROUTES[maneuver]
    segments = route["segments"] if "segments" in route else [route["points"]]
    _, length = route_position(segments, 0)
    progress = starting_progress
    current_speed = 10.0
    tick_seconds = 0.1

    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ [{vehicle_id}] Connected to the V2X Intersection!")

            while True:
                spat = current_spat()
                signal_phase = spat["signal_phase"]
                has_green = signal_phase == MOVEMENT_PHASE[maneuver]
                # Once a vehicle has crossed the stop bar it must clear the
                # intersection, even if the phase changes behind it.
                may_proceed = has_green or progress > STOP_PROGRESS
                desired_speed = target_speed(progress, maneuver)

                # On red, start slowing well before the stop bar. The progress
                # clamp below guarantees a vehicle cannot cross it on red.
                if not may_proceed and progress < STOP_PROGRESS:
                    distance_to_stop = (STOP_PROGRESS - progress) * length
                    desired_speed = min(desired_speed, distance_to_stop * 1.4)
                elif not may_proceed:
                    desired_speed = 0
                speed_change = desired_speed - current_speed
                # Braking is stronger than acceleration, but both remain gradual.
                max_change = (4.5 if speed_change < 0 else 1.8) * tick_seconds
                current_speed += max(-max_change, min(max_change, speed_change))
                braking = speed_change < -0.1

                next_progress = progress + (current_speed * tick_seconds / length)
                if not may_proceed and progress < STOP_PROGRESS <= next_progress:
                    progress = STOP_PROGRESS
                    current_speed = 0
                else:
                    progress = next_progress % 1.0
                (x, y, dx, dy), _ = route_position(segments, progress)
                heading_degrees = math.degrees(math.atan2(dy, dx)) % 360
                signal_active = 0.18 <= progress <= 0.76

                payload = {
                    "vehicle_id": vehicle_id,
                    "position": {"x": round(x, 2), "y": round(y, 2)},
                    "speed_mph": round(current_speed * 4.5, 1),
                    "heading_degrees": round(heading_degrees, 1),
                    "vehicle_type": vehicle_type,
                    "maneuver": maneuver,
                    "braking": braking,
                    "turn_signal": route["turn_signal"] if signal_active else "none",
                    # V2I message from the roadside unit (RSU).
                    "spat": spat,
                    # Retained temporarily for compatibility with existing clients.
                    "signal_phase": signal_phase,
                }

                await websocket.send(json.dumps(payload))
                await asyncio.sleep(tick_seconds)

    except ConnectionRefusedError:
        print(f"⚠️ [{vehicle_id}] Connection refused.")


async def main():
    await asyncio.gather(
        simulate_car("Car-001", "sedan", "straight", 0.04),
        simulate_car("Car-002", "suv", "left", 0.11),
        simulate_car("Car-003", "bus", "right", 0.18),
        simulate_car("Car-004", "emergency", "southbound", 0.24),
    )


if __name__ == "__main__":
    asyncio.run(main())
