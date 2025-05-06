"""
Core counting functionality for vwc.
"""

import re
import time
import locale


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
    """
    Get display width of a character, accounting for CJK characters.
    """
    # Basic implementation - ideally use wcwidth library if available
    if ord(c) >= 0x1100 and (
        ord(c) <= 0x115F  # Hangul Jamo
        or ord(c) <= 0x11A2  # Hangul Jamo Extended-A
        or (0x2E80 <= ord(c) <= 0x9FFF)  # CJK
        or (0xAC00 <= ord(c) <= 0xD7A3)  # Hangul Syllables
        or (0xF900 <= ord(c) <= 0xFAFF)  # CJK Compatibility Ideographs
        or (0xFF00 <= ord(c) <= 0xFF60)  # Fullwidth ASCII
        or (0xFFE0 <= ord(c) <= 0xFFE6)  # Fullwidth symbols
    ):
        return 2
    if ord(c) < 32 or (0x7F <= ord(c) <= 0x9F):  # Control characters
        return 0
    return 1


def count_stream(f, opts, widths, live=False, write_func=None):
    """
    Count lines, words, bytes, chars, and max line length in a file stream.
    """
    from .format import format_line

    cnt = Counts()
    last = time.monotonic()
    in_word = False
    curr_width = 0
    decoder = None

    # Setup for character counting
    if opts.chars:
        import codecs

        enc = locale.getpreferredencoding(False)
        decoder = codecs.getincrementaldecoder(enc)(errors="ignore")

    # Regex for word counting
    word_re = re.compile(rb"\S+")

    while True:
        chunk = f.read(131072)  # Larger buffer for efficiency
        if not chunk:
            break

        # Always count bytes
        cnt.bytes += len(chunk)

        # Count lines efficiently
        if opts.lines:
            cnt.lines += chunk.count(b"\n")

        # Count words using regex for better performance
        if opts.words:
            # Handle potential word spanning across chunks
            if in_word and chunk and not chunk[0:1].isspace():
                cnt.words -= 1  # Adjust for double-counting

            words = word_re.findall(chunk)
            cnt.words += len(words)

            # Set state for next chunk
            in_word = chunk and not chunk[-1:].isspace()

        # Character counting with proper decoding
        if opts.chars:
            text = decoder.decode(chunk)
            cnt.chars += len(text)

        # Max line length calculation
        if opts.max_line_length:
            # We need to process the text character by character for width
            if opts.chars:
                # Reuse decoded text from character counting
                text = decoder.decode(chunk)
            else:
                # Decode specifically for width calculation
                text = chunk.decode(locale.getpreferredencoding(False), errors="ignore")

            lines = text.split("\n")
            for i, line in enumerate(lines):
                # Process continuation from previous chunk
                if i == 0 and len(lines) > 1:
                    line_width = curr_width
                    for c in line:
                        if c == "\t":
                            line_width = (line_width // 8 + 1) * 8
                        else:
                            line_width += char_width(c)
                    cnt.max_line_length = max(cnt.max_line_length, line_width)
                    curr_width = 0
                # Process middle complete lines
                elif i < len(lines) - 1:
                    line_width = 0
                    for c in line:
                        if c == "\t":
                            line_width = (line_width // 8 + 1) * 8
                        else:
                            line_width += char_width(c)
                    cnt.max_line_length = max(cnt.max_line_length, line_width)
                # Process last line (might continue to next chunk)
                else:
                    curr_width = 0
                    for c in line:
                        if c == "\t":
                            curr_width = (curr_width // 8 + 1) * 8
                        else:
                            curr_width += char_width(c)

        # Live preview
        if live and write_func and (time.monotonic() - last) >= 0.2:
            fields = []
            if opts.lines:
                fields.append(str(cnt.lines))
            if opts.words:
                fields.append(str(cnt.words))
            if opts.chars:
                fields.append(str(cnt.chars))
            if opts.bytes:
                fields.append(str(cnt.bytes))
            if opts.max_line_length:
                fields.append(str(cnt.max_line_length))

            line = format_line(fields, None, widths)
            write_func("\r" + line, to_err=True, newline=False)
            last = time.monotonic()

    return cnt
