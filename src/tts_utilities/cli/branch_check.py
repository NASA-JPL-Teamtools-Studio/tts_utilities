import argparse
import sys
from pathlib import Path

from tts_utilities.branch_checker import print_branch_report


def main():
    parser = argparse.ArgumentParser(
        description="Assess branches across all git repositories in a directory"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan for git repositories (default: current directory)"
    )
    
    args = parser.parse_args()
    
    directory = Path(args.directory).resolve()
    
    if not directory.exists():
        print(f"Error: Directory '{directory}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory", file=sys.stderr)
        sys.exit(1)
    
    print_branch_report(str(directory))


if __name__ == "__main__":
    main()
