# WHAT DOES THIS FILE DO: Input validation and output sanitization for security

# ================== IMPORTS ==================
import logging
import re

from core.constants import INJECTION_PATTERNS
# ================== IMPORTS ==================


# =========== VARIABLES : logging ===========
logger = logging.getLogger("white_label")
# =========== VARIABLES : logging ===========


# =========== PROMPT INJECTION PROTECTION ===========

# ROLE: Pre-compile injection patterns for efficient matching during sanitization
COMPILED_INJECTIONS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]  # USE: Pre-compiled for performance


# ROLE: Clean and validate user input against injection attacks and threats
def sanitize_input(text: str) -> str:
    ''' Remove HTML, normalize whitespace, detect injections, truncate to 500 chars '''

    # FLOW-1: Return early if text is empty or None
    if not text:
        return text

    # FLOW-2: Remove HTML tags and HTML-encoded tags
    text = re.sub(r'<[^>]*>', '', text)
    text = re.sub(r'&lt;[^&gt;]*&gt;', '', text)

    # FLOW-3: Normalize whitespace - replace newlines/tabs/multiple spaces
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r' {2,}', ' ', text).strip()

    # FLOW-4: Check against injection patterns - return empty if match found
    for pattern in COMPILED_INJECTIONS:
        if pattern.search(text):
            logger.warning(f"Injection blocked: '{text[:120]}'")
            return ""

    # FLOW-5: Truncate to 500 characters maximum
    return text[:500].strip()

# =========== PROMPT INJECTION PROTECTION ===========


# =========== OUTPUT SANITIZATION ===========

# ROLE: Remove HTML tags from response text
def sanitize_response(text: str) -> str:
    ''' Strip HTML tags and trim whitespace from response '''

    # FLOW-1: Return early if text is empty
    if not text:
        return text

    # FLOW-2: Remove HTML tags using regex
    text = re.sub(r'<[^>]*>', '', text)

    return text.strip()

# =========== OUTPUT SANITIZATION ===========
