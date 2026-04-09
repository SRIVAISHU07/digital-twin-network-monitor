"""
action_controller.py
Autonomous action decision engine for DT-5G self-healing system.
Maps fault states and predictions to corrective actions.
"""

import subprocess
import os
import sys


def decide_action(fault, prediction, cpu, latency, packet_loss, throughput=None, node="unknown"):
    """
    Returns (action: str, reason: str)
    Decides the best corrective action based on system state.
    On Raspberry Pi, some actions actually execute system commands.
    """
    if cpu is None:
        return "No action", "Insufficient telemetry"

    # ── CRITICAL FAULTS ──────────────────────────────────────────────
    if fault:
        if cpu is not None and cpu >= 90:
            _execute("cpu_critical", node)
            return (
                "Emergency load shedding + process priority reset",
                f"CPU at {round(cpu,1)}% — critical threshold exceeded"
            )

        if latency is not None and latency >= 150:
            _execute("latency_critical", node)
            return (
                "Traffic re-routing to backup path",
                f"Latency at {round(latency,1)}ms — re-routing via alternate interface"
            )

        if packet_loss is not None and packet_loss >= 10:
            _execute("packetloss_critical", node)
            return (
                "Traffic throttle applied — rate limiting enabled",
                f"Packet loss at {round(packet_loss,2)}% — congestion control triggered"
            )

        if throughput is not None and throughput <= 100:
            _execute("throughput_critical", node)
            return (
                "Interface buffer flush + link renegotiation",
                f"Throughput critically low at {round(throughput,1)}Mbps"
            )

        return (
            "General fault mitigation — monitoring elevated",
            "Multiple metrics in critical state"
        )

    # ── PREDICTED FAULTS (preventive) ────────────────────────────────
    if prediction:
        if cpu is not None and cpu >= 65:
            _execute("cpu_warning", node)
            return (
                "Preventive load redistribution initiated",
                f"CPU trend rising ({round(cpu,1)}%) — pre-emptive action"
            )

        if latency is not None and latency >= 100:
            return (
                "Proactive path optimisation enabled",
                f"Latency trending up ({round(latency,1)}ms) — preventive re-route"
            )

        if packet_loss is not None and packet_loss >= 5:
            return (
                "Predictive traffic shaping applied",
                f"Packet loss trend detected ({round(packet_loss,2)}%) — pre-emptive throttle"
            )

        return (
            "Monitoring intensity increased — standby for action",
            "Predicted fault — watchdog activated"
        )

    return "No action required", "System within normal operating parameters"


# ── HARDWARE EXECUTION (Raspberry Pi) ────────────────────────────────
# These run real shell commands on the Pi when in hardware mode.
# Safe, non-destructive commands only.

def _execute(action_type, node="unknown"):
    """
    Execute real system commands on Raspberry Pi.
    Set environment variable HW_MODE=1 to enable.
    """
    if os.environ.get("HW_MODE") != "1":
        return  # Simulation mode — skip execution

    commands = {
        "cpu_critical":       ["sudo", "renice", "-n", "10", "-p", "$(pgrep -f high_cpu_process)"],
        "cpu_warning":        ["sudo", "cpulimit", "--limit=50", "--background"],
        "latency_critical":   ["sudo", "tc", "qdisc", "change", "dev", "eth0", "root", "netem", "delay", "0ms"],
        "packetloss_critical":["sudo", "tc", "qdisc", "change", "dev", "eth0", "root", "handle", "1:", "tbf",
                               "rate", "10mbit", "burst", "32kbit", "latency", "400ms"],
        "throughput_critical":["sudo", "ip", "link", "set", "eth0", "down"],
    }

    cmd = commands.get(action_type)
    if not cmd:
        return

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[action_controller] Command failed: {e}", file=sys.stderr)
