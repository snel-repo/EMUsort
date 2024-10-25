# emusort/__init__.py

"""
EMUsort: A command-line tool for high-performance spike sorting of multi-channel, single-unit electromyography
"""

try:
    from importlib.metadata import version  # For Python 3.8+
except ImportError:
    from pkg_resources import DistributionNotFound, get_distribution

    def version(package_name):
        try:
            return get_distribution(package_name).version
        except DistributionNotFound:
            return "unknown"


__version__ = version("emusort")  # Dynamically retrieve the version

from .emusort import main  # Import the main function or class

__all__ = ["main", "__version__"]  # Expose main and version
