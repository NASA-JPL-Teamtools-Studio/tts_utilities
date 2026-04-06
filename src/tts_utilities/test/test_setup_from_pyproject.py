import pytest
from unittest.mock import patch, MagicMock
import os

# Import the module under test
import tts_utilities.setup_from_pyproject as sut

@pytest.fixture
def mock_pyproject_data():
    """Standard pyproject.toml structure for testing."""
    return {
        "project": {
            "name": "test-library",
            "description": "A test library description",
            "authors": [{"name": "Jane Doe", "email": "jane@example.com"}],
            "license": {"text": "MIT"},
            "requires-python": ">=3.7",
            "dependencies": ["requests", "numpy"],
            "scripts": {"test-cli": "test_lib.main:run"}
        },
        "tool": {
            "setuptools": {
                "package-dir": {"": "src"},
                "packages": {
                    "find": {
                        "where": ["src"],
                        "include": ["my_package*"],
                        "exclude": ["*.tests"]
                    }
                }
            }
        }
    }

# We patch the targets INSIDE the tts_utilities.setup_from_pyproject namespace
@patch("tts_utilities.setup_from_pyproject.setup")
@patch("tts_utilities.setup_from_pyproject.toml.load")
@patch("tts_utilities.setup_from_pyproject.setuptools_scm.get_version")
@patch("tts_utilities.setup_from_pyproject.find_packages")
@pytest.mark.ai
def test_setup_from_pyproject_mapping(
    mock_find_packages, 
    mock_scm, 
    mock_toml_load, 
    mock_setup, 
    mock_pyproject_data
):
    """Verifies that TOML data is correctly mapped to setup() arguments."""
    
    # Setup mocks
    mock_toml_load.return_value = mock_pyproject_data
    mock_scm.return_value = "1.2.3"
    mock_find_packages.return_value = ["test_lib"]

    # Execute
    sut.setup_from_pyproject(base_path="/mock/path")

    # Verify setuptools_scm was called for the version
    mock_scm.assert_called_once_with(
        root="/mock/path",
        version_scheme="post-release",
        local_scheme="node-and-date"
    )

    # Verify find_packages was called with the correct directory logic
    mock_find_packages.assert_called_once_with(
        where="src",
        include=["my_package*"],
        exclude=["*.tests"]
    )

    # Capture and verify the arguments passed to setup()
    # This mock prevents SystemExit because the real setup() is never called
    args, kwargs = mock_setup.call_args
    
    assert kwargs["name"] == "test-library"
    assert kwargs["version"] == "1.2.3"
    assert kwargs["author"] == "Jane Doe"
    assert kwargs["author_email"] == "jane@example.com"
    assert kwargs["install_requires"] == ["requests", "numpy"]
    assert kwargs["entry_points"] == {"console_scripts": ["test-cli = test_lib.main:run"]}
    assert kwargs["python_requires"] == ">=3.7"

@patch("tts_utilities.setup_from_pyproject.setup")
@patch("tts_utilities.setup_from_pyproject.toml.load")
@patch("tts_utilities.setup_from_pyproject.setuptools_scm.get_version")
@pytest.mark.ai
def test_setup_from_pyproject_defaults(mock_scm, mock_toml_load, mock_setup):
    """Verifies that the function handles missing optional TOML keys gracefully."""
    
    # Minimal TOML data
    mock_toml_load.return_value = {
        "project": {"name": "minimal-lib"}
    }
    mock_scm.return_value = "0.1.0"

    sut.setup_from_pyproject()

    _, kwargs = mock_setup.call_args
    
    assert kwargs["description"] == ""
    assert kwargs["author"] == ""
    assert kwargs["author_email"] == ""
    assert kwargs["package_dir"] == {"": "src"}  # Defaults to src
    assert kwargs["python_requires"] == ">=3.6"  # Defaults to 3.6