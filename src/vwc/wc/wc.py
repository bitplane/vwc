# src/vwc/wc/wc.py
"""
Base class for word count (wc) implementations.
This is the base UNIX implementation.
"""

import argparse
import codecs
import importlib.util
import locale
import os
import platform
import stat
import sys
import time

import wcwidth


class WCArgumentParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        # All supported native wc implementations use status 1 for an
        # invalid command line; argparse uses 2 by default.
        super().exit(1 if status == 2 else status, message)


class WC:
    """
    Usage: wc [-cmlwL] [FILE]...

    Count lines, words, and bytes for FILEs (or stdin)
    """

    def __init__(self):
        # Configuration state
        self.platform = platform.system()
        self.parser = self.create_parser()
        self.exit_code = 0
        self.column_width = 7  # Default column width
        self.args = None

        # Reset current file count and total counts
        self.reset_counts()
        self.reset_totals()

    def create_parser(self) -> argparse.ArgumentParser:
        """Create a basic argument parser with core options."""
        parser = WCArgumentParser(
            description=self.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, add_help=False
        )
        # Core options common to all wc implementations
        parser.add_argument("-c", action="store_true", dest="bytes", help="print the byte counts")
        parser.add_argument("-m", action="store_true", dest="chars", help="print the character counts")
        parser.add_argument("-l", action="store_true", dest="lines", help="print the newline counts")
        parser.add_argument("-w", action="store_true", dest="words", help="print the word counts")

        # Platform-specific arguments added by subclasses
        self.add_platform_args(parser)

        parser.add_argument("files", nargs="*", help="files to process")
        return parser

    def add_platform_args(self, parser):
        """Add platform-specific arguments - overridden by subclasses"""
        # Default help option - most basic implementation
        parser.add_argument("-h", action="help", help="display help and exit")

    def parse_args(self, argv):
        """Parse command line arguments"""
        self.args = self.parser.parse_args(argv)

    def get_display_width(self, text):
        """Calculate the display width of text according to POSIX rules."""
        width = 0
        maximum = 0
        for char in text:
            if char == "\t":
                width = (width // 8 + 1) * 8
            elif char in ("\r", "\f"):
                maximum = max(maximum, width)
                width = 0
            else:
                # Invalid bytes decoded with surrogateescape have no display width.
                char_width = self.char_width(char)
                if char_width >= 0:
                    width += char_width
            maximum = max(maximum, width)
        return maximum

    def char_width(self, char):
        if 0xDC80 <= ord(char) <= 0xDCFF:
            return 0
        return wcwidth.wcwidth(char)

    def reset_counts(self):
        """Reset file-specific counts."""
        self.lines = 0
        self.words = 0
        self.bytes = 0
        self.chars = 0
        self.max_width = 0

    def reset_totals(self):
        """Reset total counts."""
        self.total_lines = 0
        self.total_words = 0
        self.total_bytes = 0
        self.total_chars = 0
        self.total_max_width = 0

    def process_line(self, line):
        """Process a single line and update instance state."""
        # Calculate all requested counts
        if self.args.lines:
            self.lines += line.count(b"\n")

        # A bad byte must not change the interpretation of valid characters
        # elsewhere in the line. Surrogateescape preserves one character per
        # invalid byte, like the native counters used for this platform.
        text = None
        if self.args.words or self.args.chars or getattr(self.args, "max_line_length", False):
            text = line.decode(self.encoding, errors="surrogateescape")

        if self.args.words:
            self.words += self.count_words(line, text)

        if self.args.bytes:
            self.bytes += len(line)

        if self.args.chars:
            self.chars += self.count_chars(line, text)

        if getattr(self.args, "max_line_length", False):
            display_width = self.line_width(line, text)
            # Update max_width if this line is longer
            self.max_width = max(self.max_width, display_width)

    def count_words(self, line, text):
        return len(text.split())

    def count_chars(self, line, text):
        return len(text)

    def line_width(self, line, text):
        return self.get_display_width(text.removesuffix("\n"))

    def get_counts_array(self, use_totals=False):
        """Get current counts as an array in the standard order."""
        counts = []

        if self.args.lines:
            counts.append(self.total_lines if use_totals else self.lines)

        if self.args.words:
            counts.append(self.total_words if use_totals else self.words)

        if self.args.bytes:
            counts.append(self.total_bytes if use_totals else self.bytes)

        if self.args.chars:
            counts.append(self.total_chars if use_totals else self.chars)

        if getattr(self.args, "max_line_length", False):
            counts.append(self.total_max_width if use_totals else self.max_width)

        return counts

    def print_line(self, counts, filename, file=sys.stdout):
        """Format and print count line for a file, totals or preview."""
        # Format counts with proper spacing
        output = ""
        for count in counts:
            if count is not None:
                output += f"{count:8d} "

        # Add filename if not empty
        if filename:
            output += filename

        print(output, file=file, flush=True)

    def print_totals(self, file=sys.stdout):
        """Print total counts."""
        if len(self.args.files) > 1:
            counts = self.get_counts_array(use_totals=True)
            self.print_line(counts, "total", file)

    def print_counts(self, filename, file=sys.stdout):
        """Print counts for the current file."""
        counts = self.get_counts_array()
        self.print_line(counts, filename, file)

    def print_progress(self, filename):
        """Show progress to stderr if it's a TTY."""
        if not sys.stderr.isatty():
            return

        # Clear current line and move cursor to beginning
        sys.stderr.write("\r\033[K")
        counts = self.get_counts_array()
        self.print_line(counts, filename, file=sys.stderr)
        # Move up a line to overwrite next time
        sys.stderr.write("\033[F")

        sys.stderr.flush()

    def handle_error(self, error, filename):
        """Handle file error and report it."""
        exe = os.path.basename(sys.argv[0])
        sys.stderr.write(f"{exe}: {filename}: {error.strerror}\n")
        self.set_status(1)  # Set non-zero exit status

    def set_status(self, code):
        """Set the exit status - generic implementation."""
        self.exit_code = code
        return code

    def get_file_names(self):
        """Files to process, can be overriden"""
        return self.args.files or [""]

    def get_files(self):
        """
        Get file objects to process based on arguments as a generator.
        """
        names = self.get_file_names()
        self.file_count = len(names)
        # Process each file argument
        for index, filename in enumerate(names, 1):
            if filename is None:
                self.handle_empty_name(index)
                continue
            if not self.validate_filename(filename):
                continue
            try:
                yield filename, self.open_file(filename)
            except OSError as e:
                self.handle_error(e, filename)

    def handle_empty_name(self, index):
        raise ValueError("empty file name is unsupported on this platform")

    def validate_filename(self, filename):
        return True

    def open_file(self, filename):
        # Open in binary mode to handle all types of files
        # In UNIX, '-' is just a regular file name
        if not filename or filename == "-":
            return sys.stdin.buffer
        return open(filename, "rb")

    def run(self):
        """Process files and print counts."""
        self.exit_code = 0
        args = self.args
        if getattr(args, "version", False):
            from importlib.metadata import version

            print(f"vwc {version('vwc')}")
            return 0
        # Python may silently coerce an inherited C locale to C.UTF-8 at
        # startup. Native wc still sees C, so restore it for counting.
        coerced_c = (
            sys.flags.utf8_mode
            and os.environ.get("LC_CTYPE") == "C.UTF-8"
            and os.environ.get("LANG") in (None, "C", "POSIX")
            and not os.environ.get("LC_ALL")
        )
        locale.setlocale(locale.LC_CTYPE, "C" if coerced_c else "")
        self.encoding = locale.nl_langinfo(locale.CODESET)

        # If no options specified, show default set (lines, words, bytes)
        if not (args.bytes or args.chars or args.lines or args.words or getattr(args, "max_line_length", False)):
            args.lines = args.words = args.bytes = True

        # Get file generator
        file_gen = self.get_files()

        # Reset total counters
        self.reset_totals()

        for filename, file_obj in file_gen:
            try:
                # Process the file
                self.process_file(filename, file_obj)

                # Print counts for this file
                self.print_counts(filename)

                # Update totals from current file counts
                self.update_totals()

            except KeyboardInterrupt:
                raise
            except OSError as e:
                self.handle_read_error(e, filename)

        # Print totals if needed
        self.print_totals()

        return self.exit_code

    def handle_read_error(self, error, filename):
        self.handle_error(error, filename)

    def update_totals(self):
        """Update total counts from current file counts."""
        if self.args.lines:
            self.total_lines += self.lines
        if self.args.words:
            self.total_words += self.words
        if self.args.bytes:
            self.total_bytes += self.bytes
        if self.args.chars:
            self.total_chars += self.chars
        if getattr(self.args, "max_line_length", False):
            # For max line length, take the maximum value
            self.total_max_width = max(self.total_max_width, self.max_width)

    def process_file(self, filename, file_obj):
        """Process a file and update instance state."""
        # Reset counts for this file
        self.reset_counts()

        if self.use_accelerated_scan(file_obj):
            self.process_file_accelerated(filename, file_obj)
            if filename and file_obj != sys.stdin.buffer:
                file_obj.close()
            return

        # Track timing for progress updates
        last_update = time.time()

        # Process file line by line
        for line in file_obj:
            # Process the line and update state
            self.process_line(line)

            # Show progress every ~200ms if stderr is a TTY
            current_time = time.time()
            if current_time - last_update >= 0.2:
                self.print_progress(filename)
                last_update = current_time

        # Clear progress line before returning
        if sys.stderr.isatty():
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()

        # Close file if not stdin
        if filename and file_obj != sys.stdin.buffer:
            file_obj.close()

    def accelerated_word_mode(self):
        """Return the byte word rule, or None when word counting needs the line path."""

    def use_accelerated_scan(self, file_obj):
        if self.args.chars or getattr(self.args, "max_line_length", False):
            return False
        try:
            source = os.fstat(file_obj.fileno())
        except (AttributeError, OSError):
            return False
        if stat.S_ISREG(source.st_mode) and source.st_size < 4 * 1024 * 1024:
            return False
        if not self.args.words:
            return True
        if importlib.util.find_spec("numba") is None:
            return False
        return self.accelerated_word_mode() is not None

    def process_file_accelerated(self, filename, file_obj):
        """Count fixed-size chunks so even a very long line can show progress."""
        mode = self.accelerated_word_mode() if self.args.words else None
        byte_mode = mode in ("gnu_c", "gnu_legacy_c", "busybox", "openbsd")
        decoder = None
        if self.args.words and not byte_mode:
            errors = "ignore" if mode == "unicode_ignore" else "surrogateescape"
            decoder = codecs.getincrementaldecoder(self.encoding)(errors=errors)

        read_chunk = getattr(file_obj, "read1", file_obj.read)
        use_numba = self.args.words and stat.S_ISREG(os.fstat(file_obj.fileno()).st_mode)
        accelerated = None
        bytes_seen = 0
        in_word = False
        last_update = time.monotonic()
        while chunk := read_chunk(1024 * 1024):
            bytes_seen += len(chunk)
            if self.args.bytes:
                self.bytes += len(chunk)

            scanned_lines = None
            if self.args.words:
                if not use_numba and bytes_seen >= 4 * 1024 * 1024:
                    use_numba = True
                if use_numba and accelerated is None:
                    from . import accelerated as scanner

                    accelerated = scanner
                if use_numba and (byte_mode or (chunk.isascii() and not decoder.getstate()[0])):
                    modes = {
                        "gnu_c": accelerated.GNU_C,
                        "gnu_legacy_c": accelerated.GNU_LEGACY_C,
                        "busybox": accelerated.BUSYBOX,
                        "openbsd": accelerated.OPENBSD,
                    }
                    scan_mode = modes[mode] if byte_mode else accelerated.UNICODE_ASCII
                    scanned_lines, words, in_word = accelerated.scan(chunk, in_word, scan_mode, True)
                    self.words += words
                elif byte_mode:
                    words, in_word = self.count_byte_words(chunk, in_word, mode)
                    self.words += words
                else:
                    text = decoder.decode(chunk)
                    count, in_word = self.count_decoded_words(text, in_word)
                    self.words += count
            if self.args.lines:
                self.lines += scanned_lines if scanned_lines is not None else chunk.count(b"\n")

            now = time.monotonic()
            if now - last_update >= 0.2:
                self.print_progress(filename)
                last_update = now

        if decoder is not None:
            count, _ = self.count_decoded_words(decoder.decode(b"", final=True), in_word)
            self.words += count
        if sys.stderr.isatty():
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()

    @staticmethod
    def count_byte_words(chunk, in_word, mode):
        words = 0
        for byte in chunk:
            space = byte in (9, 10, 11, 12, 13, 32)
            if mode == "gnu_legacy_c" and byte >= 128:
                continue
            if mode == "gnu_c":
                space = space or byte == 160
            elif mode == "gnu_legacy_c":
                space = space or 28 <= byte <= 31
            if space:
                in_word = False
            elif mode == "busybox" and not 33 <= byte <= 126:
                continue
            elif not in_word:
                words += 1
                in_word = True
        return words, in_word

    @staticmethod
    def count_decoded_words(text, in_word):
        if not text:
            return 0, in_word
        parts = text.split()
        count = len(parts)
        if count and in_word and not text[0].isspace():
            count -= 1
        return count, not text[-1].isspace()
