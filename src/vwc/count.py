"""
Core counting functionality for vwc.
"""

import time
import locale
import numpy as np
from numba import njit


class Counts:
    """Container for all counts tracked by vwc."""

    def __init__(self):
        self.lines = self.words = self.chars = self.bytes = self.max_line_length = 0

    def __iadd__(self, other):
        """Add another Counts object to this one."""
        self.lines += other.lines
        self.words += other.words
        self.chars += other.chars
        self.bytes += other.bytes
        self.max_line_length = max(self.max_line_length, other.max_line_length)
        return self

    def to_fields(self, opts):
        """Convert counts to fields based on enabled options."""
        fields = []
        if opts.lines:
            fields.append(str(self.lines))
        if opts.words:
            fields.append(str(self.words))
        if opts.chars:
            fields.append(str(self.chars))
        if opts.bytes:
            fields.append(str(self.bytes))
        if opts.max_line_length:
            fields.append(str(self.max_line_length))
        return fields


def char_width(c):
    """Get display width of a character, accounting for CJK characters."""
    c_ord = ord(c)
    # Fast path for ASCII
    if c_ord < 127:
        return 0 if c_ord < 32 else 1

    # Handle wide characters
    if c_ord >= 0x1100 and (
        c_ord <= 0x115F  # Hangul Jamo
        or c_ord <= 0x11A2  # Hangul Jamo Extended-A
        or (0x2E80 <= c_ord <= 0x9FFF)  # CJK
        or (0xAC00 <= c_ord <= 0xD7A3)  # Hangul Syllables
        or (0xF900 <= c_ord <= 0xFAFF)  # CJK Compatibility Ideographs
        or (0xFF00 <= c_ord <= 0xFF60)  # Fullwidth ASCII
        or (0xFFE0 <= c_ord <= 0xFFE6)  # Fullwidth symbols
    ):
        return 2

    # Other control characters
    if 0x7F <= c_ord <= 0x9F:
        return 0

    # Default for everything else
    return 1


@njit(cache=True)
def count_newlines(data):
    """Count newlines in byte data, optimized with Numba."""
    count = 0
    for i in range(len(data)):
        if data[i] == 10:  # ASCII for newline '\n'
            count += 1
    return count


@njit(cache=True)
def count_words(data, initial_in_word):
    """
    Count words in byte data using a simple state machine, optimized with Numba.

    Args:
        data: NumPy array of bytes
        initial_in_word: Whether we're starting in a word

    Returns:
        tuple: (word_count, final_in_word)
    """
    in_word = initial_in_word
    word_count = 0

    for i in range(len(data)):
        # Simple whitespace check (ASCII only)
        is_space = data[i] <= 32

        if not is_space and not in_word:
            # Transition from whitespace to non-whitespace: start of new word
            word_count += 1
            in_word = True
        elif is_space:
            # Any whitespace: no longer in a word
            in_word = False

    return word_count, in_word


def calc_line_widths(lines, initial_width=0):
    """
    Calculate width of each line, handling tabs and wide chars.

    Args:
        lines: List of text lines
        initial_width: Starting width for first line (for continued lines)

    Returns:
        tuple: (max_width, final_line_width)
    """
    max_width = 0
    curr_width = initial_width

    for i, line in enumerate(lines):
        # Process first line (continuation from previous chunk)
        if i == 0:
            for c in line:
                if c == "\t":
                    curr_width = (curr_width // 8 + 1) * 8
                else:
                    curr_width += char_width(c)

            if len(lines) > 1:
                # Line is complete (ends with newline)
                max_width = max(max_width, curr_width)
                curr_width = 0

        # Process middle lines (complete lines)
        elif i < len(lines) - 1:
            width = 0
            for c in line:
                if c == "\t":
                    width = (width // 8 + 1) * 8
                else:
                    width += char_width(c)
            max_width = max(max_width, width)

        # Process last line (continuing to next chunk)
        else:
            curr_width = 0
            for c in line:
                if c == "\t":
                    curr_width = (curr_width // 8 + 1) * 8
                else:
                    curr_width += char_width(c)

    return max(max_width, curr_width) if len(lines) == 1 else max_width, curr_width


def show_live_preview(cnt, opts, widths, write_func):
    """Show live preview of current counts."""
    from .format import format_line

    fields = cnt.to_fields(opts)
    line = format_line(fields, None, widths)
    write_func("\r" + line, to_err=True, newline=False)


def count_stream(f, opts, widths, live=False, write_func=None):
    """Count lines, words, bytes, chars, and max line length in a file stream."""
    cnt = Counts()
    last_update = time.monotonic()
    in_word = False
    curr_width = 0
    decoder = None

    # Setup for character counting
    if opts.chars:
        import codecs

        enc = locale.getpreferredencoding(False)
        decoder = codecs.getincrementaldecoder(enc)(errors="ignore")

    while True:
        chunk = f.read(131072)
        if not chunk:
            break

        # Always count bytes
        cnt.bytes += len(chunk)

        # Create numpy array for Numba functions
        np_chunk = np.frombuffer(chunk, dtype=np.uint8)

        # Count lines with Numba
        if opts.lines:
            cnt.lines += count_newlines(np_chunk)

        # Count words with Numba
        if opts.words:
            words, in_word = count_words(np_chunk, in_word)
            cnt.words += words

        # Character counting
        if opts.chars:
            text = decoder.decode(chunk)
            cnt.chars += len(text)

        # Max line length calculation
        if opts.max_line_length:
            text = text if opts.chars else chunk.decode(locale.getpreferredencoding(False), errors="ignore")
            lines = text.split("\n")
            max_width, curr_width = calc_line_widths(lines, curr_width)
            cnt.max_line_length = max(cnt.max_line_length, max_width)

        # Live preview
        if live and write_func and (time.monotonic() - last_update) >= 0.2:
            show_live_preview(cnt, opts, widths, write_func)
            last_update = time.monotonic()

    return cnt
