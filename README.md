# digital-twin-network-monitor
Digital Twin–driven autonomous network monitoring system with real-time telemetry, fault detection, and self-healing using Python, Flask, and Raspberry Pi

# Digital Twin–Driven Autonomous Network Monitoring System

Real-time network monitoring system using a Digital Twin framework for
autonomous fault detection, early failure prediction, and self-healing —
built with Python, Flask, and Raspberry Pi 4.

## What it does
- Creates a virtual Digital Twin representation of a live network/system
- Collects real-time telemetry: CPU usage, latency, throughput, packet loss
- Detects faults using threshold-based logic (CPU > 80%, latency > 150ms)
- Predicts failures early using sliding-window trend analysis
- Triggers autonomous corrective actions without human intervention
- Displays live system state on a web dashboard

## Tech Stack
| Layer | Technology |
|---|---|
| Backend | Python, Flask (REST API) |
| Data Analysis | Pandas |
| Visualization | Matplotlib, HTML Dashboard |
| Hardware | Raspberry Pi 4 |
| Communication | HTTP / REST API |

## Project Structure
```
server/
  app.py               # Flask REST API server + Digital Twin core
  action_controller.py # Autonomous corrective action logic
  fault_detector.py    # Threshold-based fault detection
  fault_predictor.py   # Trend-based early failure prediction
telemetry/
  telemetry_agent.py   # Real-time metric collection agent
Dt5g_dashboard.html    # Live monitoring dashboard
```

## How to Run
```bash
# Install dependencies
pip install -r requirements.txt

# Start the Digital Twin server
python server/app.py

# In a new terminal, start the telemetry agent
python telemetry/telemetry_agent.py

# Open dashboard
Open Dt5g_dashboard.html in your browser
```

## Key Outcomes
- Continuous autonomous system monitoring
- Early detection of performance degradation
- Automated fault mitigation without manual intervention
- Applicable to: IoT monitoring, data centers, smart manufacturing

---
**Sri Vaishnavi Kumar** | ECE Undergraduate, RMK College of Engineering and Technology  
Patent holder | IEEE Xplore author | SIH National Finalist × 2
