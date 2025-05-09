# src/vwc/wc/linux.py
import os
import stat
import sys

from .wc import WC


class Linux(WC):
    """
    Shared base class for BusyBox and GNU, since they have similar
    implementations.
    """

    def get_file_names(self):
        """
        Basic file name handling
        """
        return self.args.files or [""]

    def get_files(self):
        """Handle file processing with BusyBox/GNU behavior."""

        files = self.get_file_names()
        self.set_column_width(files)

        if not files:
            yield ("", sys.stdin.buffer)
            return

        for filename in files:
            try:
                if filename == "-" or not filename:
                    yield (filename, sys.stdin.buffer)
                else:
                    yield (filename, open(filename, "rb"))
            except OSError as e:
                self.handle_error(e, filename)

    def set_column_width(self, filenames):
        """
        Do the same as compute_number_width in GNU's wc.c
        BusyBox does this too.
        """

        # We aren't reporting on files, so GNU assumes a width of 1 here
        if hasattr(self.args, "total") and self.args.total == "only":
            self.column_width = 1
            return

        # If we don't actually have named files, we assume maximum width
        if not filenames:
            self.column_width = 7
            return
        else:
            # otherwise, we will start at 1 and work our way up
            self.column_width = 1

        total_size = 0

        # loop over files and check their sizes
        for name in filenames:
            # hang on, this is stdin.
            if name == "-" or not name:
                self.column_width = 7
                break

            try:
                st = os.stat(name, follow_symlinks=False)
            except Exception:
                # Ignore errors. We don't want to complain about them early.
                # GNU does this because it's trying to preserve UNIX behaviour.
                continue

            if not stat.S_ISREG(st.st_mode):
                # yep, adding a dir to the list will cause GNU wc to use 7 as the column width.
                # Bug IMO, but we do the same.
                self.column_width = 7
                break
            else:
                # we have a regular file, and its size is the maximum size we will ever print.
                # because printing characters can't print a bigger number than that. This is, of course,
                # incorrect, because
                total_size += st.st_size
                new_width = len(str(total_size))
                self.column_width = max(self.column_width, new_width)
                if self.column_width >= 7:
                    # we have a file that is 7 digits long. We can stop now.
                    self.column_width = 7
                    break

    def handle_error(self, error, filename):
        """
        In Linux, print the counts on directories.
        """
        super().handle_error(error, filename)
        if isinstance(error, IsADirectoryError):
            # Reset counts to zeros for directories
            self.reset_counts()

            # Print zero counts for the directory
            self.print_counts(filename)
