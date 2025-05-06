"""
Formatting functionality for vwc output.
"""

import sys

# Field order for output
FIELD_ORDER = ["lines", "words", "chars", "bytes", "max_line_length"]


def format_line(fields, label, width_map):
    """Format a line of output with proper column alignment."""
    parts = []
    selected = [k for k in FIELD_ORDER if k in width_map]
    for idx, k in enumerate(selected):
        parts.append(f"{fields[idx]:>{width_map[k]}}")
    if label:
        parts.append(label)
    return " ".join(parts)


def compute_widths(all_fields, opts, default=False):
    """Compute column widths for output formatting."""
    widths = {}
    sel = []
    if opts.lines:
        sel.append("lines")
    if opts.words:
        sel.append("words")
    if opts.chars:
        sel.append("chars")
    if opts.bytes:
        sel.append("bytes")
    if opts.max_line_length:
        sel.append("max_line_length")

    for i, k in enumerate(sel):
        if default:
            widths[k] = 7
        else:
            # Only one selected field - no padding
            if len(sel) == 1:
                widths[k] = len(max(all_fields, key=lambda x: len(x[i]))[i]) if all_fields else 0
            else:
                # Use minimum field width or the width needed for the largest number
                widths[k] = max(7, max(len(f[i]) for f in all_fields) if all_fields else 7)

    return widths


def write(line, to_err=False, newline=True):
    """Write output to stdout or stderr with proper flushing."""
    out = sys.stderr if to_err else sys.stdout
    out.write(line + ("\n" if newline else ""))
    out.flush()
