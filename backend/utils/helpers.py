# WHAT DOES THIS FILE DO: Utility helper functions for logging and formatting

# ================== IMPORTS ==================
import logging
import sys
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any

from config import LOG_LEVEL
# ================== IMPORTS ==================


# =========== VARIABLES : logging ===========
logger = logging.getLogger("white_label")
# =========== VARIABLES : logging ===========


# =========== UTILITY FUNCTIONS ===========
# ROLE: Normalize Azure OpenAI endpoint by removing trailing slashes and version paths
def normalize_azure_endpoint(endpoint: str) -> str:
    ''' Clean endpoint string - remove trailing slash and /openai/v1 suffix '''

    # FLOW-1: Strip leading/trailing whitespace from endpoint
    endpoint = endpoint.strip()

    # FLOW-2: Remove trailing slash if present
    if endpoint.endswith("/"):
        endpoint = endpoint[:-1]

    # FLOW-3: Remove /openai/v1 suffix if present (Azure OpenAI standard path)
    if endpoint.lower().endswith("/openai/v1"):
        endpoint = endpoint[: -len("/openai/v1")]

    return endpoint


# ROLE: Calculate elapsed time between two timestamps in seconds
def _secs(start: float, end: Optional[float] = None) -> float:
    ''' Return elapsed seconds rounded to 3 decimal places '''

    # FLOW-1: Use current time if end timestamp not provided
    if end is None:
        end = time.perf_counter()

    # FLOW-2: Calculate difference and round to 3 decimals
    return round(end - start, 3)


# ROLE: Log formatted banner message with emoji and dashes
def log_banner(title: str, emoji: str = "⚙️", width: int = 72) -> None:
    ''' Print decorative banner with title, emoji, and dashes '''

    # FLOW-1: Build message string with emoji prefix
    msg = f"{emoji} {title} "

    # FLOW-2: Calculate remaining space and fill with dashes
    dashes = "-" * max(0, width - len(msg))
    logger.info(f"{msg}{dashes}")


# ROLE: Context manager for logging operation execution steps with timing
@contextmanager
def log_step(title: str, emoji: str = "⚙️"):
    ''' Log step entry, completion or exception with elapsed time '''

    # FLOW-1: Log step start with banner
    log_banner(title, emoji=emoji)
    t0 = time.perf_counter()

    # FLOW-2: Execute step and handle completion or exception
    try:
        yield
        logger.info(f"Done: {title} ({_secs(t0)}s)")
    except Exception:
        logger.exception(f"Failed: {title} ({_secs(t0)}s)")
        raise


# ROLE: Transform timing measurements from milliseconds to seconds
def timings_payload(timings: dict) -> dict:
    ''' Convert millisecond timings to seconds format for API response '''

    # FLOW-1: Copy raw millisecond timings
    out = {"raw": timings.copy()}

    # FLOW-2: Convert _ms keys to _s keys with value in seconds
    seconds = {}
    for k, v in timings.items():
        if k.endswith("_ms") and isinstance(v, (int, float)):
            seconds[k.replace("_ms", "_s")] = round(float(v) / 1000.0, 3)

    out["seconds"] = seconds
    return out


# ROLE: Configure logging with UTF-8 encoding and formatted output
def setup_logging() -> None:
    ''' Configure root logger with stream handler and formatted output '''

    # FLOW-1: Reconfigure stdout to UTF-8 if possible
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # FLOW-2: Set logging level from config
    level = getattr(logging, str(LOG_LEVEL).upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    # FLOW-3: Return early if handlers already configured
    if root.handlers:
        return

    # FLOW-4: Create stream handler with formatted output
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(fmt="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S"))
    root.addHandler(handler)
# =========== UTILITY FUNCTIONS ===========