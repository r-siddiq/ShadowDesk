"""
Log Reader Utility
Reads and streams logs for System Pulse
"""

import logging
import os
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

# Default log file paths to check
LOG_PATHS = [
    "/tmp/trading.log",
    "C:\\Users\\*\\AppData\\Local\\Temp\\trading.log",
    "logs/trading.log",
    "/var/log/trading.log",
]


def find_log_file() -> Optional[str]:
    """Find the log file"""
    for path in LOG_PATHS:
        if "*" in path:
            # Handle wildcard paths
            import glob

            matches = glob.glob(path)
            if matches and os.path.exists(matches[0]):
                return matches[0]
        elif os.path.exists(path):
            return path
    return None


def read_last_lines(log_file: str, num_lines: int = 10) -> List[str]:
    """Read last N lines from log file"""
    try:
        if not os.path.exists(log_file):
            return [f"[{datetime.now().strftime('%H:%M:%S')}] Log file not found: {log_file}"]

        with open(log_file, "r") as f:
            lines = f.readlines()
            last_lines = lines[-num_lines:] if len(lines) > num_lines else lines
            return [line.strip() for line in last_lines if line.strip()]
    except Exception as e:
        return [f"[{datetime.now().strftime('%H:%M:%S')}] Error reading logs: {e}"]


def generate_mock_logs() -> List[str]:
    """Generate mock logs when no log file exists"""
    import random

    actions = [
        "Checking signals for",
        "Signal generated for",
        "Order submitted:",
        "Order filled @",
        "Position opened:",
        "Position closed:",
        "Stop loss triggered:",
        "Checking market status...",
        "Fetching latest data for",
        "Model prediction completed for",
    ]

    symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META"]

    logs = []
    for _ in range(8):
        action = random.choice(actions)
        symbol = random.choice(symbols)
        timestamp = datetime.now().strftime("%H:%M:%S")

        if "signal" in action.lower():
            signal = random.choice(["BUY", "SELL", "HOLD"])
            confidence = random.randint(55, 85)
            logs.append(f"{timestamp}  {action} {symbol}: {signal} ({confidence}%)")
        elif "order" in action.lower() or "position" in action.lower():
            price = round(random.uniform(100, 500), 2)
            qty = random.randint(1, 20)
            logs.append(f"{timestamp}  {action} {symbol} x{qty} @ ${price}")
        else:
            logs.append(f"{timestamp}  {action} {symbol}")

    return logs


def get_logs(num_lines: int = 10, use_mock: bool = True) -> List[str]:
    """Get last N log lines"""
    log_file = find_log_file()

    if log_file:
        return read_last_lines(log_file, num_lines)
    elif use_mock:
        return generate_mock_logs()
    else:
        return [f"[{datetime.now().strftime('%H:%M:%S')}] No log file found"]
