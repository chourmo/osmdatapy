"""
Unit and regression test for the osmdatapy package.
"""

# Import package, test suite, and other packages as needed
import sys

import pytest

import osmdatapy


def test_osmdatapy_imported():
    """Sample test, will always pass so long as import statement worked."""
    assert "osmdatapy" in sys.modules
