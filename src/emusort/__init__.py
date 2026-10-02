# emusort/__init__.py

"""
EMUsort: A command line tool for high performance spike sorting of multichannel, single unit electromyography
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("emusort")
except PackageNotFoundError:
    __version__ = "unknown"

from .emusort import main  # Import the main function or class

__all__ = ["__version__", "main"]  # Expose main and version
