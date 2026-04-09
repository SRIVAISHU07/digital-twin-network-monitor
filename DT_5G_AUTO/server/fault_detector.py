"""
fault_detector.py
Threshold-based fault detection for DT-5G system.
"""

THRESHOLDS = {
    "cpu":         {"warning": 65, "critical": 80},
    "latency":     {"warning": 100, "critical": 150},   # ms
    "packet_loss": {"warning": 5,   "critical": 10},    # %
    "throughput":  {"warning": 200, "critical": 100},   # Mbps (inverted — low is bad)
}


def detect_fault(cpu, latency, packet_loss, throughput=None):
    """
    Returns (fault: bool, reason: str, severity: str)
    severity: 'normal' | 'warning' | 'critical'
    """
    if cpu is None or latency is None or packet_loss is None:
        return False, "Insufficient data", "normal"

    faults   = []
    warnings = []

    # CPU
    if cpu >= THRESHOLDS["cpu"]["critical"]:
        faults.append(f"CPU critical: {round(cpu,1)}% (threshold {THRESHOLDS['cpu']['critical']}%)")
    elif cpu >= THRESHOLDS["cpu"]["warning"]:
        warnings.append(f"CPU elevated: {round(cpu,1)}%")

    # Latency
    if latency >= THRESHOLDS["latency"]["critical"]:
        faults.append(f"Latency critical: {round(latency,1)}ms (threshold {THRESHOLDS['latency']['critical']}ms)")
    elif latency >= THRESHOLDS["latency"]["warning"]:
        warnings.append(f"Latency elevated: {round(latency,1)}ms")

    # Packet loss
    if packet_loss >= THRESHOLDS["packet_loss"]["critical"]:
        faults.append(f"Packet loss critical: {round(packet_loss,2)}% (threshold {THRESHOLDS['packet_loss']['critical']}%)")
    elif packet_loss >= THRESHOLDS["packet_loss"]["warning"]:
        warnings.append(f"Packet loss elevated: {round(packet_loss,2)}%")

    # Throughput (low = bad)
    if throughput is not None:
        if throughput <= THRESHOLDS["throughput"]["critical"]:
            faults.append(f"Throughput critically low: {round(throughput,1)}Mbps")
        elif throughput <= THRESHOLDS["throughput"]["warning"]:
            warnings.append(f"Throughput low: {round(throughput,1)}Mbps")

    if faults:
        return True, " | ".join(faults), "critical"
    if warnings:
        return False, " | ".join(warnings), "warning"
    return False, "All metrics within normal range", "normal"
