"""
telemetry_agent.py
========================================================
Runs ON the Raspberry Pi (or any Linux node).
Collects REAL hardware metrics every second and POSTs
them to the DT-5G Flask server.

Usage:
    python3 telemetry_agent.py --server http://192.168.1.100:5000 --node EDGE-1

Install dependencies:
    pip3 install psutil requests --break-system-packages
"""

import argparse
import time
import json
import socket
import subprocess
import sys
import os
import threading

try:
    import psutil
except ImportError:
    print("Installing psutil...")
    os.system("pip3 install psutil --break-system-packages")
    import psutil

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system("pip3 install requests --break-system-packages")
    import requests


# ── CONFIG ───────────────────────────────────────────────────────────
DEFAULT_SERVER   = "http://127.0.0.1:5000"
DEFAULT_NODE     = "EDGE-1"
SEND_INTERVAL    = 1.0      # seconds between telemetry pushes
PING_TARGET      = "8.8.8.8"
PING_COUNT       = 3
INTERFACE        = None     # auto-detect if None

# Retry logic
MAX_RETRIES      = 3
RETRY_DELAY      = 0.5


# ── METRIC COLLECTORS ────────────────────────────────────────────────

def get_cpu_percent():
    """Returns CPU usage % averaged over 0.5s interval."""
    return round(psutil.cpu_percent(interval=0.5), 2)


def get_memory_percent():
    """Returns RAM usage %."""
    return round(psutil.virtual_memory().percent, 2)


def get_temperature():
    """
    Returns CPU temperature in Celsius.
    Works on Raspberry Pi. Returns None on unsupported hardware.
    """
    # Method 1: Raspberry Pi thermal zone
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000, 1)
    except Exception:
        pass

    # Method 2: psutil sensors (Linux)
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for key in ("cpu_thermal", "coretemp", "k10temp", "acpitz"):
                if key in temps and temps[key]:
                    return round(temps[key][0].current, 1)
    except Exception:
        pass

    return None


def get_network_interface():
    """Auto-detect best network interface (prefer eth0, then wlan0)."""
    global INTERFACE
    if INTERFACE:
        return INTERFACE

    preferred = ["eth0", "wlan0", "wlan1", "ens3", "enp3s0"]
    stats = psutil.net_io_counters(pernic=True)
    for iface in preferred:
        if iface in stats:
            INTERFACE = iface
            return iface

    # Fallback: first non-loopback interface
    for iface in stats:
        if iface != "lo":
            INTERFACE = iface
            return iface

    return None


_last_net_stats = {}
_last_net_time  = {}

def get_throughput_mbps():
    """
    Returns real network throughput in Mbps (bytes/sec × 8 / 1e6).
    Measures delta between two calls.
    """
    iface = get_network_interface()
    if not iface:
        return 0.0

    stats = psutil.net_io_counters(pernic=True)
    if iface not in stats:
        return 0.0

    now   = time.time()
    cur   = stats[iface]
    total = cur.bytes_sent + cur.bytes_recv

    key = iface
    if key in _last_net_stats:
        delta_bytes = total - _last_net_stats[key]
        delta_time  = now   - _last_net_time[key]
        if delta_time > 0:
            mbps = (delta_bytes * 8) / (delta_time * 1e6)
            _last_net_stats[key] = total
            _last_net_time[key]  = now
            return round(max(mbps, 0.0), 3)

    _last_net_stats[key] = total
    _last_net_time[key]  = now
    return 0.0


def get_latency_ms(target=PING_TARGET):
    """
    Returns real network latency in ms by pinging target.
    Falls back to a fast socket-based method if ping fails.
    """
    # Method 1: ping command
    try:
        result = subprocess.run(
            ["ping", "-c", str(PING_COUNT), "-W", "1", target],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "avg" in line or "rtt" in line:
                # Parse: rtt min/avg/max/mdev = 12.3/14.5/16.7/1.2 ms
                parts = line.split("/")
                if len(parts) >= 5:
                    return round(float(parts[4]), 2)
                # Also handle: ... = 12.3/14.5/16.7/1.2 ms
                for p in parts:
                    try:
                        val = float(p.strip().split()[-1].replace("ms",""))
                        if 0 < val < 10000:
                            return round(val, 2)
                    except Exception:
                        pass
    except Exception:
        pass

    # Method 2: TCP socket timing to 8.8.8.8:53
    try:
        import socket as _socket
        t0 = time.time()
        sock = _socket.create_connection((target, 53), timeout=2)
        sock.close()
        return round((time.time() - t0) * 1000, 2)
    except Exception:
        pass

    return None


def get_packet_loss_percent(target=PING_TARGET):
    """
    Returns real packet loss % by pinging target.
    """
    try:
        result = subprocess.run(
            ["ping", "-c", "5", "-W", "1", target],
            capture_output=True, text=True, timeout=8
        )
        for line in result.stdout.splitlines():
            if "packet loss" in line:
                for token in line.split():
                    if "%" in token:
                        return round(float(token.replace("%", "")), 2)
    except Exception:
        pass
    return 0.0


def get_disk_usage_percent():
    return round(psutil.disk_usage("/").percent, 2)


def get_uptime_seconds():
    return int(time.time() - psutil.boot_time())


# ── BUILD TELEMETRY PAYLOAD ──────────────────────────────────────────

def collect_telemetry(node_name):
    """Collect all hardware metrics and return as dict."""
    cpu        = get_cpu_percent()
    latency    = get_latency_ms()
    throughput = get_throughput_mbps()
    # Run packet loss in background (it takes ~5 seconds), cache result
    packet_loss = _packet_loss_cache.get("value", 0.0)

    return {
        "node":         node_name,
        "cpu":          cpu,
        "latency":      latency,
        "throughput":   throughput,
        "packet_loss":  packet_loss,
        "memory":       get_memory_percent(),
        "temperature":  get_temperature(),
        "disk":         get_disk_usage_percent(),
        "uptime":       get_uptime_seconds(),
        "interface":    get_network_interface() or "unknown",
        "hostname":     socket.gethostname(),
    }


# ── BACKGROUND PACKET LOSS POLLER ───────────────────────────────────
# Packet loss measurement takes 5 seconds, so run in background thread.

_packet_loss_cache = {"value": 0.0}

def _packet_loss_worker():
    while True:
        try:
            val = get_packet_loss_percent()
            _packet_loss_cache["value"] = val
        except Exception:
            pass
        time.sleep(5)

threading.Thread(target=_packet_loss_worker, daemon=True).start()


# ── SEND TO SERVER ───────────────────────────────────────────────────

def send_telemetry(server_url, payload):
    """POST telemetry to DT-5G server with retry logic."""
    url = server_url.rstrip("/") + "/api/telemetry"
    headers = {"Content-Type": "application/json"}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(url, data=json.dumps(payload), headers=headers, timeout=3)
            if resp.status_code == 200:
                return True, resp.json()
            else:
                print(f"[WARNING] Server returned {resp.status_code}", file=sys.stderr)
        except requests.exceptions.ConnectionError:
            if attempt == 1:
                print(f"[ERROR] Cannot connect to {url} — is the server running?", file=sys.stderr)
        except requests.exceptions.Timeout:
            print(f"[WARNING] Request timed out (attempt {attempt})", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] {e}", file=sys.stderr)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    return False, None


# ── MAIN LOOP ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="DT-5G Telemetry Agent")
    parser.add_argument("--server", default=DEFAULT_SERVER,
                        help=f"Server URL (default: {DEFAULT_SERVER})")
    parser.add_argument("--node",   default=DEFAULT_NODE,
                        help=f"Node name (default: {DEFAULT_NODE})")
    parser.add_argument("--interval", type=float, default=SEND_INTERVAL,
                        help=f"Send interval in seconds (default: {SEND_INTERVAL})")
    parser.add_argument("--verbose", action="store_true",
                        help="Print each telemetry payload")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════╗
║   DT-5G Telemetry Agent v2.0             ║
╠══════════════════════════════════════════╣
║  Node     : {args.node:<30}║
║  Server   : {args.server:<30}║
║  Interval : {args.interval}s{' '*27}║
╚══════════════════════════════════════════╝
    """)

    iface = get_network_interface()
    print(f"[INFO] Network interface detected: {iface}")
    print(f"[INFO] Hostname: {socket.gethostname()}")
    temp = get_temperature()
    if temp:
        print(f"[INFO] CPU temperature: {temp}°C")
    print(f"[INFO] Starting telemetry loop...\n")

    sent_count  = 0
    error_count = 0

    while True:
        loop_start = time.time()

        try:
            payload = collect_telemetry(args.node)

            if args.verbose:
                print(f"[{time.strftime('%H:%M:%S')}] CPU:{payload['cpu']}% "
                      f"LAT:{payload['latency']}ms "
                      f"TP:{payload['throughput']}Mbps "
                      f"PL:{payload['packet_loss']}% "
                      f"TEMP:{payload['temperature']}°C")

            ok, resp = send_telemetry(args.server, payload)

            if ok:
                sent_count += 1
                if not args.verbose and sent_count % 10 == 0:
                    print(f"[{time.strftime('%H:%M:%S')}] {sent_count} samples sent | "
                          f"CPU:{payload['cpu']}% LAT:{payload['latency']}ms "
                          f"TP:{payload['throughput']}Mbps PL:{payload['packet_loss']}%")
            else:
                error_count += 1
                if error_count % 5 == 0:
                    print(f"[WARNING] {error_count} consecutive errors — check server")

        except KeyboardInterrupt:
            print(f"\n[INFO] Agent stopped. Sent {sent_count} samples.")
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Telemetry collection failed: {e}", file=sys.stderr)

        # Sleep precisely to maintain interval
        elapsed = time.time() - loop_start
        sleep_time = max(0, args.interval - elapsed)
        time.sleep(sleep_time)


if __name__ == "__main__":
    main()
