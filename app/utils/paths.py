"""
Provides utility functions for handling file paths.

This module contains functions to resolve resource paths, which is crucial
for accessing data files (like icons and stylesheets) in a way that works
both in a development environment and in a bundled PyInstaller executable.
"""
import sys
import os

def resource_path(relative_path):
    """
    Get the absolute path to a resource.

    This function resolves the path to a resource file, handling the difference
    between running from source and running from a PyInstaller bundle. When
    running as a bundled executable, PyInstaller unpacks resources to a
    temporary folder and stores its path in the `_MEIPASS` attribute of the
    `sys` module. This function checks for that attribute to determine the
    correct base path.

    Args:
        relative_path (str): The path to the resource relative to the
                             application root or the bundled resources folder.

    Returns:
        str: The absolute path to the resource.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Not bundled, running from source
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)