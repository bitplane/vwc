# src/vwc/wc/linux.py
import sys

from .wc import WC


class Linux(WC):
    """
    Shared base class for BusyBox and GNU, since they have similar
    implementations.
    """

    def get_file(self, filename):
        """
        Open a file for reading.
        In Linux, '-' is treated as a regular file name.
        """
        if not filename or filename == "-":
            return sys.stdin.buffer
        return open(filename, "rb")

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
