#!/usr/bin/env python3
"""
vwc — A GNU-compatible `wc` implementation with visual preview.

Usage: vwc [OPTION]... [FILE]...
  or:  vwc [OPTION]... --files0-from=F

Print newline, word, and byte counts for each FILE, and a total line if
more than one FILE is specified. A word is a non-zero-length sequence of
printable characters delimited by white space.

With no FILE, or when FILE is -, read standard input.

Live preview of counts is shown every 200ms to stderr if stderr is a TTY.

Options:
  -c, --bytes            print the byte counts
  -m, --chars            print the character counts
  -l, --lines            print the newline counts
  -w, --words            print the word counts
  -L, --max-line-length  print the maximum display width
      --files0-from=F    read input from the files specified by
                         NUL-terminated names in file F;
                         If F is - then read names from standard input
      --total=WHEN       when to print a line with total counts;
                         WHEN can be: auto, always, only, never
      --help             display this help and exit
      --version          print version information and exit
"""

import sys
import time
import argparse
import locale
import signal
import re
import subprocess

locale.setlocale(locale.LC_ALL, "")

FIELD_ORDER = ["lines", "words", "chars", "bytes", "max_line_length"]


class Counts:
    def __init__(self):
        self.lines = self.words = self.chars = self.bytes = self.max_line_length = 0

    def __iadd__(self, other):
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


def format_line(fields, label, width_map):
    parts = []
    selected = [k for k in FIELD_ORDER if k in width_map]
    for idx, k in enumerate(selected):
        parts.append(f"{fields[idx]:>{width_map[k]}}")
    if label:
        parts.append(label)
    return " ".join(parts)


def write(line, to_err=False, newline=True):
    out = sys.stderr if to_err else sys.stdout
    out.write(line + ("\n" if newline else ""))
    out.flush()


def parse_args(argv):
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("-c", "--bytes", action="store_true", dest="bytes")
    p.add_argument("-m", "--chars", action="store_true", dest="chars")
    p.add_argument("-l", "--lines", action="store_true", dest="lines")
    p.add_argument("-w", "--words", action="store_true", dest="words")
    p.add_argument("-L", "--max-line-length", action="store_true", dest="max_line_length")
    p.add_argument("--files0-from")
    p.add_argument("--total", choices=["auto", "always", "only", "never"], default="auto")
    p.add_argument("--help", action="store_true")
    p.add_argument("--version", action="store_true")
    p.add_argument("files", nargs="*")
    return p.parse_args(argv)


def is_tty():
    return sys.stderr.isatty()


def read_nul_list(fname):
    data = sys.stdin.buffer.read() if fname == "-" else open(fname, "rb").read()
    return data.decode(errors="ignore").split("\0")[:-1]


def get_files(args):
    return read_nul_list(args.files0_from) if args.files0_from else (args.files or ["-"])


def compute_widths(all_fields, opts, default=False):
    widths = {}
    sel = [k for k in FIELD_ORDER if getattr(opts, k)]
    for i, k in enumerate(sel):
        if default:
            widths[k] = 7
        else:
            widths[k] = max(7, max(len(f[i]) for f in all_fields)) if all_fields else 7
    return widths


def detect_platform():
    """Detect platform for wc behavior differences."""
    import platform

    system = platform.system()
    if system == "Linux":
        # Check if it's GNU coreutils
        try:
            version = subprocess.check_output(["wc", "--version"], text=True)
            if "GNU coreutils" in version:
                return "gnu"
        except:  # noqa: E722
            pass
        return "linux"
    elif system == "Darwin":
        return "bsd"
    elif system == "FreeBSD":
        return "bsd"
    elif system == "Windows":
        return "windows"
    return "unknown"


def char_width(c):
    """Get display width of a character, accounting for CJK characters."""
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


def count_stream(f, opts, widths, live=False):
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
        if live and (time.monotonic() - last) >= 0.2:
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

            write("\r" + format_line(fields, None, widths), to_err=True, newline=False)
            last = time.monotonic()

    return cnt


def run_wc(argv):
    args = parse_args(argv)
    if args.help:
        write(__doc__)
        return 0
    if args.version:
        write("vwc 0.0.2 (GNU-compatible)")
        return 0

    # Default flags
    if not any([args.bytes, args.chars, args.lines, args.words, args.max_line_length]):
        args.lines = args.words = args.bytes = True

    files = get_files(args)
    show_tot = args.total in ("always", "only") or (args.total == "auto" and len(files) > 1)
    live = is_tty()

    # Prepare for live preview
    live_width = compute_widths([], args, default=True)
    results = []
    tot = Counts()
    all_fields = []
    had_error = False  # Track errors for return code

    # Get platform for platform-specific behavior
    platform = detect_platform()

    # Process each file
    for p in files:
        try:
            # Always use binary mode for consistency
            f = sys.stdin.buffer if p == "-" else open(p, "rb")
            cnt = count_stream(f, args, live_width, live)
            if p != "-":
                f.close()
            fields = cnt.to_fields(args)
            results.append((fields, None if p == "-" else p))
            all_fields.append(fields)
            tot += cnt
        except FileNotFoundError:
            write(f"vwc: {p}: No such file or directory", to_err=True)
            had_error = True
        except PermissionError:
            write(f"vwc: {p}: Permission denied", to_err=True)
            had_error = True
        except IsADirectoryError:
            # Handle directories according to platform behavior
            if platform in ("gnu", "linux"):
                write(f"vwc: {p}: Is a directory", to_err=True)
            elif platform == "bsd":
                # BSD might count directories as empty files
                cnt = Counts()
                fields = cnt.to_fields(args)
                results.append((fields, p))
                all_fields.append(fields)
                tot += cnt
            else:
                # Default to GNU behavior
                write(f"vwc: {p}: Is a directory", to_err=True)
            had_error = True
        except OSError as e:
            # Match the exact formatting of wc errors
            write(f"vwc: {p}: {e.strerror}", to_err=True)
            had_error = True
        except Exception as e:  # noqa: E722
            # Generic error handler as fallback
            write(f"vwc: {p}: {str(e)}", to_err=True)
            had_error = True

    # Handle totals
    if args.total == "only":
        results = [(tot.to_fields(args), None)]
        all_fields = [tot.to_fields(args)]
    elif show_tot:
        results.append((tot.to_fields(args), "total"))
        all_fields.append(tot.to_fields(args))

    # Clear live preview line before final output
    if live:
        write("\r\033[K", to_err=True, newline=False)

    # Final formatting and output
    final_width = compute_widths(all_fields, args)
    for fld, label in results:
        line = format_line(fld, label, final_width)
        write(line)

    return 1 if had_error else 0  # Return non-zero if any errors occurred


def main():
    # Handle broken pipe gracefully
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    # Handle other common signals
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda s, f: sys.exit(128 + s))

    try:
        sys.exit(run_wc(sys.argv[1:]))
    except KeyboardInterrupt:
        write("", to_err=True)
        sys.exit(130)  # Standard exit code for SIGINT


if __name__ == "__main__":
    main()
