# emusort/__init__.py

"""
EMUsort: A command-line tool for high-performance spike sorting of multi-channel, single-unit electromyography
"""

import subprocess


def version():
    try:
        # Execute the git command to get the current tag
        tag = subprocess.check_output(
            ['git', 'describe', '--tags', '--abbrev=0'],
            stderr=subprocess.STDOUT
        ).strip().decode('utf-8')
        return tag
    except subprocess.CalledProcessError:
        return "unknown"

__version__ = version()  # Dynamically retrieve the version

from .emusort import main  # Import the main function or class

__all__ = ["main", "__version__"]  # Expose main and version
