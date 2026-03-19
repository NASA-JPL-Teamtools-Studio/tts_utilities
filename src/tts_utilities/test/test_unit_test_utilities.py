import os
import pytest
import tempfile  # Added to access gettempdir()
from pathlib import Path
from unittest.mock import patch, MagicMock
from tempfile import TemporaryDirectory
from tts_utilities.test_utilities import safe_test_paths

# Replace 'your_module' with the actual filename where safe_test_paths resides
# from your_module import safe_test_paths

def test_safe_test_paths_writable(tmp_path):
    """
    Scenario: The directory exists and is writable.
    Expected: Input and output paths should be identical.
    """
    repo_dir = tmp_path / "repo"
    test_dir = Path("sub_test")
    full_path = repo_dir / test_dir
    full_path.mkdir(parents=True)

    # We mock os.access to return True (writable)
    with patch("os.access", return_value=True):
        input_path, output_path = safe_test_paths(repo_dir, test_dir)
        
        assert input_path == full_path
        assert output_path == full_path
        assert input_path == output_path

def test_safe_test_paths_not_writable():
    """
    Scenario: The directory exists but is NOT writable (simulating site-packages).
    Expected: Input path is the original, output path is a new temp directory.
    """
    repo_dir = Path("/mock/read_only/repo")
    test_dir = Path("my_tests")
    full_path = repo_dir / test_dir

    # 1. Define a dynamic safe temp path
    safe_mock_temp = os.path.join(tempfile.gettempdir(), "tts_test_random")

    # Mock exists=True, but access=False
    with patch("pathlib.Path.exists", return_value=True), \
         patch("os.access", return_value=False), \
         patch("tempfile.mkdtemp") as mock_mkdtemp:
        
        # 2. Use the dynamic path variable instead of "/tmp/..."
        mock_mkdtemp.return_value = safe_mock_temp
        
        input_path, output_path = safe_test_paths(repo_dir, test_dir)
        
        assert input_path == full_path
        # Output should be the temp dir + the relative test_test_files_dir
        # 3. Assert against the dynamic variable
        assert str(output_path).startswith(safe_mock_temp)
        assert output_path.name == "my_tests"

def test_safe_test_paths_not_exists():
    """
    Scenario: The directory does not exist at all.
    Expected: Should default to the temp directory logic.
    """
    repo_dir = Path("/non/existent/path")
    test_dir = Path("missing")

    # 1. Define a dynamic safe temp path
    safe_mock_temp = os.path.join(tempfile.gettempdir(), "tts_test_missing")

    with patch("pathlib.Path.exists", return_value=False), \
         patch("tempfile.mkdtemp") as mock_mkdtemp:
        
        # 2. Use the dynamic path variable
        mock_mkdtemp.return_value = safe_mock_temp
        
        input_path, output_path = safe_test_paths(repo_dir, test_dir)
        
        assert input_path == repo_dir / test_dir
        # Check if the folder name is in the output path string
        assert "tts_test_missing" in str(output_path)

def test_string_input_handling(tmp_path):
    """
    Verifies that the function correctly handles string inputs by converting them to Paths.
    """
    repo_str = str(tmp_path)
    test_str = "relative_folder"
    
    with patch("os.access", return_value=True), \
         patch("pathlib.Path.exists", return_value=True):
        
        in_p, out_p = safe_test_paths(repo_str, test_str)
        
        assert isinstance(in_p, Path)
        assert isinstance(out_p, Path)
        assert in_p == tmp_path / "relative_folder"