import { useState, useEffect } from 'react'
import './App.css'

// Vehicles are drawn facing north by default.
// Simulator headings: 0° = east, 90° = north.
const vehicleRotation = (headingDegrees = 0) => 90 - headingDegrees;

const phaseLabels = {
  horizontal: 'Horizontal traffic green',
  protected_left: 'Protected left turn green',
  vertical: 'Vertical traffic green',
  all_red: 'All-red clearance',
};

function App() {
  const [vehicles, setVehicles] = useState({});
  const [signalPhase, setSignalPhase] = useState('horizontal');
  const [spat, setSpat] = useState(null);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/v2x-dashboard");

    ws.onopen = () => {
      console.log("Connected to V2X Intersection Manager!");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      setVehicles(prevVehicles => ({
        ...prevVehicles,
        [data.vehicle_id]: data
      }));
      if (data.spat) {
        setSpat(data.spat);
        setSignalPhase(data.spat.signal_phase);
      } else {
        setSignalPhase(data.signal_phase || 'horizontal');
      }
    };

    return () => ws.close();
  }, []);

  const mapCoordToPixel = (val) => {
    return ((val + 50) / 100) * 600;
  };

  return (
    <div className="dashboard-container">
      <h1>V2X Fleet Live Intersection Simulator</h1>

      <div className="intersection-map">
        {spat && (
          <aside className="spat-panel" aria-live="polite">
            <span className="spat-eyebrow">RSU · SPaT broadcast</span>
            <strong>{phaseLabels[spat.signal_phase]}</strong>
            <span>Changes in {spat.time_to_change_seconds.toFixed(1)} s</span>
            <span className="spat-movements">
              {spat.permitted_movements.length > 0
                ? `Allowed: ${spat.permitted_movements.join(' · ')}`
                : 'Allowed: all vehicles stop'}
            </span>
          </aside>
        )}
        <div className="sidewalk sidewalk--north" />
        <div className="sidewalk sidewalk--south" />
        <div className="sidewalk sidewalk--west" />
        <div className="sidewalk sidewalk--east" />
        <div className="building building--northwest"><span className="tree" /></div>
        <div className="building building--northeast"><span className="tree" /></div>
        <div className="building building--southwest"><span className="tree" /></div>
        <div className="building building--southeast"><span className="tree" /></div>
        <div className="road-vertical"></div>
        <div className="road-horizontal"></div>
        <div className="center-intersection"></div>
        <div className="crosswalk crosswalk--north" />
        <div className="crosswalk crosswalk--south" />
        <div className="crosswalk crosswalk--west" />
        <div className="crosswalk crosswalk--east" />
        <div className="stop-bar stop-bar--north" />
        <div className="stop-bar stop-bar--south" />
        <div className="stop-bar stop-bar--west" />
        <div className="stop-bar stop-bar--east" />
        <div className="road-arrow road-arrow--eastbound">→</div>
        <div className="road-arrow road-arrow--westbound">←</div>
        <div className="road-arrow road-arrow--northbound">↑</div>
        <div className="road-arrow road-arrow--southbound">↓</div>
        <div className="traffic-light traffic-light--north"><i className={`light light--red ${signalPhase === 'horizontal' || signalPhase === 'all_red' ? 'is-on' : ''}`} /><i className="light light--yellow" /><i className={`light light--green ${signalPhase === 'vertical' ? 'is-on' : ''}`} /></div>
        <div className="traffic-light traffic-light--south"><i className={`light light--red ${signalPhase === 'horizontal' || signalPhase === 'all_red' ? 'is-on' : ''}`} /><i className="light light--yellow" /><i className={`light light--green ${signalPhase === 'vertical' || signalPhase === 'protected_left' ? 'is-on' : ''}`} /></div>
        <div className="traffic-light traffic-light--west traffic-light--horizontal"><i className={`light light--red ${signalPhase !== 'horizontal' ? 'is-on' : ''}`} /><i className="light light--yellow" /><i className={`light light--green ${signalPhase === 'horizontal' ? 'is-on' : ''}`} /></div>
        <div className="traffic-light traffic-light--east traffic-light--horizontal"><i className={`light light--red ${signalPhase !== 'horizontal' ? 'is-on' : ''}`} /><i className="light light--yellow" /><i className={`light light--green ${signalPhase === 'horizontal' ? 'is-on' : ''}`} /></div>

        {Object.keys(vehicles).length === 0 && (
          <p style={{ position: 'absolute', top: '20px', left: '20px', zIndex: 100 }}>
            Waiting for vehicle data...
          </p>
        )}

        {Object.keys(vehicles).map(id => {
          const car = vehicles[id];
          const leftPosition = mapCoordToPixel(car.position.x);
          const topPosition = mapCoordToPixel(-car.position.y);
          const vehicleType = car.vehicle_type || 'sedan';

          return (
            <div
              key={id}
              className="vehicle-marker"
              style={{ left: `${leftPosition}px`, top: `${topPosition}px` }}
            >
              <div
                className={`vehicle vehicle--${vehicleType} ${car.braking ? 'vehicle--braking' : ''} vehicle--signal-${car.turn_signal || 'none'}`}
                style={{ transform: `rotate(${vehicleRotation(car.heading_degrees)}deg)` }}
                title={`${id} · ${vehicleType} · ${car.speed_mph} mph`}
              >
                <span className="vehicle-wheel vehicle-wheel--front-left" />
                <span className="vehicle-wheel vehicle-wheel--front-right" />
                <span className="vehicle-wheel vehicle-wheel--rear-left" />
                <span className="vehicle-wheel vehicle-wheel--rear-right" />

                <span className="vehicle-body">
                  <span className="vehicle-windshield" />
                  <span className="vehicle-roof" />
                  <span className="vehicle-brake-light vehicle-brake-light--left" />
                  <span className="vehicle-brake-light vehicle-brake-light--right" />
                  <span className="vehicle-turn-light vehicle-turn-light--left" />
                  <span className="vehicle-turn-light vehicle-turn-light--right" />
                  {vehicleType === 'emergency' && <span className="vehicle-lightbar" />}
                </span>
              </div>

              <div className="car-label">
                {id} · {car.speed_mph} mph
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default App
