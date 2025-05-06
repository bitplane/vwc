"""
Visual Word Count (vwc) - A wc alternative with live preview.
"""

__version__ = "0.0.2"

# Define __all__ for explicit exports
__all__ = [
    "main",  # Main entry point
    "count_stream",  # Core counting function
    "Counts",  # Counts class
    "run_wc",  # Main application logic
    "write",  # Output writer
    "format_line",  # Line formatter
    "compute_widths",  # Width calculator
    "FIELD_ORDER",  # Field order constant
    "detect_platform",  # Platform detector
]

# Import the public API
from .cli import main
from .count import count_stream, Counts
from .app import run_wc
from .format import write, format_line, compute_widths, FIELD_ORDER
from .platform import detect_platform
