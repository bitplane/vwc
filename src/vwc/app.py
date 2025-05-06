"""
Main application logic for vwc.
"""

import sys
from .count import Counts, count_stream
from .format import compute_widths, format_line, write
from .platform import detect_platform


def read_nul_list(fname):
    """Read a NUL-separated list of filenames."""
    data = sys.stdin.buffer.read() if fname == "-" else open(fname, "rb").read()
    return data.decode(errors="ignore").split("\0")[:-1]


def get_files(args):
    """Get list of files to process."""
    return read_nul_list(args.files0_from) if args.files0_from else (args.files or ["-"])


def is_tty():
    """Check if stderr is a TTY (for live preview)."""
    return sys.stderr.isatty()


def run_wc(argv):
    """Main function to run the wc command."""
    from .cli import parse_args, HELP_TEXT

    args = parse_args(argv)
    if args.help:
        write(HELP_TEXT)
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
            cnt = count_stream(f, args, live_width, live, write)
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
