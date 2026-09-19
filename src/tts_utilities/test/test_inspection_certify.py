"""Tests for the certification CLI wrapper.

The certify tool is for humans only, so these tests never exercise the
real certification path: ``certify_file`` is mocked wherever a test would
otherwise stamp approval. What is verified is routing: which artifacts
the tool would certify and that the dashboard is written.
"""

import pytest

import tts_utilities.inspection as inspection
from tts_utilities.cli.inspection_certify import main as certify_main


@pytest.fixture
def no_certify(monkeypatch):
    """Replace certify_file with a recorder; returns certified paths."""
    certified = []
    monkeypatch.setattr(
        inspection, 'certify_file',
        lambda path, normalizers=None: certified.append(path.name))
    return certified


@pytest.mark.unreviewed_ai
class TestCli:
    def test_status_prints_unreviewed(self, tmp_path, capsys):
        (tmp_path / 'a.html').write_text('x')
        certify_main(['--root', str(tmp_path), '--no-dashboard'])
        out = capsys.readouterr().out
        assert 'UNREVIEWED' in out

    def test_certify_all_targets_every_artifact(
            self, tmp_path, no_certify):
        (tmp_path / 'a.html').write_text('x')
        (tmp_path / 'b.html').write_text('y')
        certify_main(['--root', str(tmp_path), '--certify'])
        assert sorted(no_certify) == ['a.html', 'b.html']

    def test_certify_single_file(self, tmp_path, no_certify):
        first = tmp_path / 'a.html'
        (first).write_text('x')
        (tmp_path / 'b.html').write_text('y')
        certify_main(['--root', str(tmp_path), '--certify', str(first)])
        assert no_certify == ['a.html']

    def test_dashboard_written_by_default(self, tmp_path):
        (tmp_path / 'a.html').write_text('x')
        certify_main(['--root', str(tmp_path)])
        assert (tmp_path / 'inspection_status.html').exists()

    def test_no_dashboard_flag_suppresses_report(self, tmp_path):
        (tmp_path / 'a.html').write_text('x')
        certify_main(['--root', str(tmp_path), '--no-dashboard'])
        assert not (tmp_path / 'inspection_status.html').exists()
