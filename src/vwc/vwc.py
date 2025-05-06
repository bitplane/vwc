#!/usr/bin/env python3
"""
wc.py — A GNU-compatible `wc` implementation in Python (Cython-friendly).

Usage: wc.py [OPTION]... [FILE]...
  or:  wc.py [OPTION]... --files0-from=F

Print newline, word, and byte counts for each FILE, and a total line if
more than one FILE is specified. A word is a non-zero-length sequence of
printable characters delimited by white space.

With no FILE, or when FILE is -, read standard input.

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

Live preview of counts is shown every 200ms to stderr if stderr is a TTY.
Output columns appear in the following fixed order:
  lines, words, chars, bytes, max-line-length

This script is structured for easy Cython porting.
"""

import sys
import time
import argparse
import locale
import signal

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
        return [str(getattr(self, k)) for k in FIELD_ORDER if getattr(opts, k)]


# Single formatting function for preview and final


def format_line(fields, label, width_map):
    parts = []
    selected = [k for k in FIELD_ORDER if k in width_map]
    for idx, k in enumerate(selected):
        parts.append(f"{fields[idx]:>{width_map[k]}}")
    if label:
        parts.append(label)
    return " ".join(parts)


# Write and flush helper


def write(line, to_err=False, newline=True):
    out = sys.stderr if to_err else sys.stdout
    out.write(line + ("\n" if newline else ""))
    out.flush()


# Argument parsing


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


# Detect TTY for live preview


def is_tty():
    return sys.stderr.isatty()


# Read NUL-separated file list


def read_nul_list(fname):
    data = sys.stdin.buffer.read() if fname == "-" else open(fname, "rb").read()
    return data.decode(errors="ignore").split("\0")[:-1]


# Resolve input files


def get_files(args):
    return read_nul_list(args.files0_from) if args.files0_from else (args.files or ["-"])


# Compute column widths


def compute_widths(all_fields, opts, default=False):
    widths = {}
    sel = [k for k in FIELD_ORDER if getattr(opts, k)]
    for i, k in enumerate(sel):
        if default:
            widths[k] = 7
        else:
            widths[k] = max(7, max(len(f[i]) for f in all_fields))
    return widths


# Core counting logic


def count_stream(f, opts, widths, live=False):
    cnt = Counts()
    last = time.monotonic()
    in_word = False
    decoder = None
    if opts.chars:
        import codecs

        enc = locale.getpreferredencoding(False)
        decoder = codecs.getincrementaldecoder(enc)(errors="ignore")

    while True:
        chunk = f.read(65536)
        if not chunk:
            break
        data = chunk if isinstance(chunk, bytes) else chunk.encode("utf-8")
        cnt.bytes += len(data)
        if opts.chars:
            text = decoder.decode(data)
            cnt.chars += len(text)
        partial = 0
        for b in data:
            c = chr(b)
            if opts.lines and c == "\n":
                cnt.lines += 1
                partial = 0
            elif opts.max_line_length:
                if c == "\t":
                    partial = partial - (partial % 8) + 8
                else:
                    partial += 1
                cnt.max_line_length = max(cnt.max_line_length, partial)
            if opts.words:
                if c.isspace():
                    in_word = False
                elif not in_word:
                    cnt.words += 1
                    in_word = True
        if live and (time.monotonic() - last) >= 0.2:
            line = format_line(cnt.to_fields(opts), None, widths)
            write(line, to_err=True, newline=False)
            last = time.monotonic()
    return cnt


# Main execution


def run_wc(argv):
    args = parse_args(argv)
    if args.help:
        write(__doc__)
        return 0
    if args.version:
        write("wc.py 0.1 (GNU-compatible)")
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

    # Process each file
    for p in files:
        try:
            f = (
                sys.stdin.buffer
                if p == "-"
                else (open(p, "rb") if not args.chars else open(p, "r", encoding="utf-8", errors="ignore"))
            )
            cnt = count_stream(f, args, live_width, live)
            if p != "-":
                f.close()
            fields = cnt.to_fields(args)
            results.append((fields, None if p == "-" else p))
            all_fields.append(fields)
            tot += cnt
        except Exception as e:
            write(f"wc.py: {p}: {e}", to_err=True)

    # Handle totals
    if args.total == "only":
        results = [(tot.to_fields(args), None)]
        all_fields = [tot.to_fields(args)]
    elif show_tot:
        results.append((tot.to_fields(args), "total"))
        all_fields.append(tot.to_fields(args))

    # Clear live preview line before final output
    if live:
        write("\033[K", to_err=True, newline=False)

    # Final formatting and output
    final_width = compute_widths(all_fields, args, default=False)
    for fld, label in results:
        line = format_line(fld, label, final_width)
        write(line)
    return 0


# Entrypoint


def main():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    try:
        sys.exit(run_wc(sys.argv[1:]))
    except KeyboardInterrupt:
        write("", to_err=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
