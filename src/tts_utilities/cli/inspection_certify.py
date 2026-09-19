"""Human-facing certification tool for inspection artifacts.

IMPORTANT: This tool is for humans only - never call it from automated
tests, CI, or agent tooling. The .sha256 sidecar files are the human
stamp of approval on generated artifacts.

Usage:
    python -m tts_utilities.cli.inspection_certify --root <artifact dir>
    python -m tts_utilities.cli.inspection_certify --root <dir> --certify
    python -m tts_utilities.cli.inspection_certify --root <dir> --certify file.html
"""

import argparse
import sys
from pathlib import Path

from tts_utilities.inspection import (
    DEFAULT_STATUS_REPORT_NAME,
    certify,
    discover_artifacts,
    print_status,
    render_status_report,
)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            'Review status dashboard and certification tool for generated '
            'inspection artifacts. FOR HUMANS ONLY: the .sha256 sidecars it '
            'writes are the record of human approval; tests, CI, and agents '
            'must never run the certify step.'
        )
    )
    parser.add_argument(
        '--root', default='.',
        help='Directory containing generated artifacts (default: cwd)')
    parser.add_argument(
        '--certify', nargs='*', default=None, metavar='PATH',
        help='Certify all artifacts (no args) or the listed artifact paths')
    parser.add_argument(
        '--no-dashboard', action='store_true',
        help='Do not write the HTML status dashboard (it is written by '
             'default on every status run)')
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print("Error: '%s' is not a directory" % root, file=sys.stderr)
        sys.exit(1)

    artifacts = discover_artifacts(
        root, status_report_name=DEFAULT_STATUS_REPORT_NAME)
    certify_cmd = (
        'python -m tts_utilities.cli.inspection_certify --root %s --certify'
        % root
    )

    if args.certify is not None:
        targets = [Path(p) for p in args.certify] if args.certify else artifacts
        certify(targets)
        return

    print_status(artifacts, certify_cmd)
    if not args.no_dashboard:
        report = render_status_report(artifacts, certify_cmd)
        report_path = root / DEFAULT_STATUS_REPORT_NAME
        report_path.write_text(report, encoding='utf-8')
        print('\n  Dashboard written: %s\n' % report_path)


if __name__ == '__main__':
    main()
