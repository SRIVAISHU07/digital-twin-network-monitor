"""
fault_predictor.py
Sliding-window trend analysis for early fault prediction.
Uses linear regression over recent history to detect rising slopes.
"""

WINDOW = 10   # samples used for trend analysis
SLOPE_THRESHOLDS = {
    "cpu":         {"warning": 0.4, "critical": 0.8},   # % per sample
    "latency":     {"warning": 1.5, "critical": 3.0},   # ms per sample
    "packet_loss": {"warning": 0.2, "critical": 0.5},   # % per sample
}


def _linear_slope(values):
    """Returns slope of best-fit line (rise per sample). Returns 0 if insufficient data."""
    n = len(values)
    if n < 3:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    num   = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n))
    denom = sum((xs[i] - mean_x) ** 2 for i in range(n))
    if denom == 0:
        return 0.0
    return num / denom


def _confidence(slope, warn_thresh, crit_thresh):
    """Maps slope magnitude to a 0–100 confidence score."""
    if slope <= 0:
        return 0
    if slope >= crit_thresh:
        return min(int(85 + (slope - crit_thresh) / crit_thresh * 10), 97)
    if slope >= warn_thresh:
        ratio = (slope - warn_thresh) / (crit_thresh - warn_thresh)
        return int(45 + ratio * 40)
    return 0


def predict_fault(cpu_history, latency_history, packet_loss_history):
    """
    Returns (prediction: bool, reason: str, confidence: float 0-100)
    """
    results = []

    checks = [
        ("cpu",         cpu_history,         SLOPE_THRESHOLDS["cpu"]),
        ("latency",     latency_history,      SLOPE_THRESHOLDS["latency"]),
        ("packet_loss", packet_loss_history,  SLOPE_THRESHOLDS["packet_loss"]),
    ]

    for metric, hist, thresh in checks:
        if not hist or len(hist) < 3:
            continue
        window = [v for v in hist[-WINDOW:] if v is not None]
        if len(window) < 3:
            continue
        slope = _linear_slope(window)
        conf  = _confidence(slope, thresh["warning"], thresh["critical"])
        if conf > 0:
            direction = "rising" if slope > 0 else "falling"
            results.append({
                "metric": metric,
                "slope":  round(slope, 3),
                "conf":   conf,
                "reason": f"{metric} {direction} at {round(slope,2)}/sample — {conf}% confidence of fault"
            })

    if not results:
        return False, "No adverse trends detected", 0

    # Pick highest-confidence signal
    best = max(results, key=lambda r: r["conf"])

    if best["conf"] >= 50:
        return True, best["reason"], float(best["conf"])

    return False, best["reason"], float(best["conf"])
