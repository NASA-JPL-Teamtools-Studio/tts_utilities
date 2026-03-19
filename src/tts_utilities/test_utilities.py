#Standard Library Imports
import tempfile
from typing import Tuple, Union
import os
from pathlib import Path
import pdb
import shutil

#This Library Imports
from tts_utilities.logger import create_logger

logger = create_logger('tts_utilities.test_utilities')


def safe_test_paths(
    repo_test_files_dir: Union[str, Path], 
    test_test_files_dir: Union[str, Path]
    ) -> Tuple[Path, Path]:
    """
    Helper to ensure that tests that rely on files can run regardless
    of the context. The Teamtools Studio's testing philosophy includes
    deploying tests to src/my_library/test so that they can be run either
    locally by a developer with the code present, or by running

        pytest --pyargs my_library.test

    once the library is installed in production. This takes us out of
    any context where there may be some deployment difference that will
    affect tests and produce false positives. Developers and even end
    users can run tests at any time if they are suspicious that there
    is a bug or a deployment issue.

    This function is here for tests that rely on the output of files, which
    is impossible once a library has been deployed to site-packages.

    This function will check repo_test_files_dir/test_test_files_dir to
    see if the current user has write permissions there. If they do, the
    function returns input and output directories as the same. If they do
    not, output directory is replaced with a safe tmpdir.

    :param repo_test_files_dir: Absath to repository's parent test files directory
    :type repo_test_files_dir: str or Path

    :param test_test_files_dir: Path to the files for this test relative to repo_test_files_dir
    :type test_test_files_dir: str or Path

    :return: A tuple containing the input and output directories for tests. The input directory
        is always the path `repo_test_files_dir/test_test_files_dir`. The output directory is either
        the same as the input directory (if the user has write permissions) or a temporary directory
        (if the user does not have write permissions).
    :rtype: tuple(Path, Path)
    """

    if isinstance(repo_test_files_dir, str): repo_test_files_dir = Path(repo_test_files_dir)
    if isinstance(test_test_files_dir, str): test_test_files_dir = Path(test_test_files_dir)

    fullpath = repo_test_files_dir.joinpath(test_test_files_dir)
    
    # Check if the directory exists and is writable
    if fullpath.exists() and os.access(fullpath, os.W_OK):
        return fullpath, fullpath
    else:
        # Create a safe, unique temporary directory
        # prefix='tts_' makes it easier to identify in /tmp during debugging
        base_tmp = Path(tempfile.mkdtemp(prefix='tts_test_'))
        
        # Create the sub-structure to match the expected test path 
        # (optional, but helpful if tests expect specific folder nesting)
        tmppath = base_tmp.joinpath(test_test_files_dir)
        tmppath.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Write access denied to {fullpath}. Using temporary directory: {tmppath}")
        
        return fullpath, tmppath


if __name__ == '__main__':
    pdb.set_trace()