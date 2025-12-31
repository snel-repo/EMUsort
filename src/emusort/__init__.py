# emusort/__init__.py

"""
EMUsort: A command-line tool for high-performance spike sorting of multi-channel, single-unit electromyography
"""

import subprocess

# import os

# def version():
#     # Retrieve version from the environment variable
#     return os.getenv('GITHUB_REF_NAME', '0.0.0')  # Default to 'unknown' if not set
def version():
    try:
        # Execute the git command to get the current tag
        tag = subprocess.check_output(
            ['git', 'describe', '--tags', '--abbrev=0'],
            # cwd=repo_dir,
            stderr=subprocess.STDOUT
        ).strip().decode('utf-8')
        return tag
    except subprocess.CalledProcessError:
        return "unknown"

__version__ = version()  # Dynamically retrieve the version

from .emusort import main  # Import the main function or class

__all__ = ["main", "__version__"]  # Expose main and version
