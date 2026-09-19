"""Tests for the artifact human-certification workflow."""

import hashlib
import io
import zipfile

import pytest

from tts_utilities.inspection import (
    CERTIFIED,
    STALE,
    UNCERTIFIED,
    artifact_status,
    certify_file,
    check_inspection_hash,
    default_normalizers,
    discover_artifacts,
    normalized_digest,
    normalize_ooxml,
    normalize_uuids,
    render_status_report,
    sidecar_path,
)
from tts_utilities.cli.inspection_certify import main as certify_main


@pytest.fixture
def artifact(tmp_path):
    """A minimal HTML artifact in a temp directory."""
    path = tmp_path / 'report.html'
    path.write_text('<html><body><div id="x">hello</div></body></html>')
    return path


def _write_docx(path, body_text='hello', timestamps=('2024-01-01T00:00:00Z',)):
    """Write a minimal synthetic .docx (zip of XML members)."""
    core = (
        '<?xml version="1.0"?><cp:coreProperties '
        'xmlns:cp="x" xmlns:dcterms="y">'
        '<dcterms:created>%s</dcterms:created>'
        '<dcterms:modified>%s</dcterms:modified>'
        '<cp:lastModifiedBy>someone</cp:lastModifiedBy>'
        '</cp:coreProperties>'
    ) % (timestamps + ('2024-01-01T00:00:00Z',))[:2]
    with zipfile.ZipFile(str(path), 'w') as z:
        z.writestr('[Content_Types].xml', '<Types/>')
        z.writestr('word/document.xml', '<w:document>%s</w:document>' % body_text)
        z.writestr('docProps/core.xml', core)
        z.writestr('calcChain.xml', '<calcChain/>')


class TestUuidNormalization:
    def test_uuids_replaced(self):
        data = b'id="3f8a9b2c-1111-4222-8333-abcdef012345"'
        out = normalize_uuids(data)
        assert b'00000000-0000-0000-0000-000000000000' in out

    def test_different_uuids_same_hash(self, tmp_path):
        a = tmp_path / 'a.html'
        b = tmp_path / 'b.html'
        a.write_text('<div id="3f8a9b2c-1111-4222-8333-abcdef012345">x</div>')
        b.write_text('<div id="99998888-7777-4666-8555-0123456789ab">x</div>')
        assert normalized_digest(a) == normalized_digest(b)

    def test_normalizers_compose_in_order(self, tmp_path):
        path = tmp_path / 'a.html'
        path.write_text('A_VERSION_B')
        n1 = lambda d: d.replace(b'A', b'Z')
        n2 = lambda d: d.replace(b'VERSION', b'V')
        both = normalized_digest(path, normalizers=[n1, n2])
        only_second = normalized_digest(path, normalizers=[n2])
        assert both != only_second
        assert hashlib.sha256(b'Z_V_B').hexdigest() == both


class TestCheckInspectionHash:
    def test_missing_sidecar_raises(self, artifact):
        with pytest.raises(AssertionError, match='No certification hash'):
            check_inspection_hash(artifact)

    def test_certified_passes_silently(self, artifact):
        certify_file(artifact)
        check_inspection_hash(artifact)  # no raise

    def test_stale_raises(self, artifact):
        certify_file(artifact)
        artifact.write_text('<html><body>changed</body></html>')
        with pytest.raises(AssertionError, match='changed since last'):
            check_inspection_hash(artifact)

    def test_failure_message_mentions_certify(self, artifact):
        with pytest.raises(AssertionError, match='Run:'):
            check_inspection_hash(artifact)


class TestStatuses:
    def test_status_lifecycle(self, artifact):
        assert artifact_status(artifact) == UNCERTIFIED
        certify_file(artifact)
        assert artifact_status(artifact) == CERTIFIED
        artifact.write_text('<html><body>drifted</body></html>')
        assert artifact_status(artifact) == STALE

    def test_sidecar_format(self, artifact):
        certify_file(artifact)
        text = sidecar_path(artifact).read_text()
        digest, name = text.split()
        assert len(digest) == 64
        assert name == artifact.name


class TestOoxml:
    def test_docx_stable_across_timestamps(self, tmp_path):
        a = tmp_path / 'a.docx'
        b = tmp_path / 'b.docx'
        _write_docx(a, timestamps=('2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z'))
        _write_docx(b, timestamps=('2030-06-15T12:34:56Z', '2030-06-15T12:34:56Z'))
        assert normalized_digest(a) == normalized_digest(b)

    def test_docx_member_order_irrelevant(self, tmp_path):
        a = tmp_path / 'a.docx'
        b = tmp_path / 'b.docx'
        _write_docx(a)
        core = (
            '<?xml version="1.0"?><cp:coreProperties '
            'xmlns:cp="x" xmlns:dcterms="y">'
            '<dcterms:created>2024-01-01T00:00:00Z</dcterms:created>'
            '<dcterms:modified>2024-01-01T00:00:00Z</dcterms:modified>'
            '<cp:lastModifiedBy>someone</cp:lastModifiedBy>'
            '</cp:coreProperties>'
        )
        with zipfile.ZipFile(str(b), 'w') as z:  # reversed member order
            z.writestr('calcChain.xml', '<calcChain/>')
            z.writestr('docProps/core.xml', core)
            z.writestr('word/document.xml', '<w:document>hello</w:document>')
            z.writestr('[Content_Types].xml', '<Types/>')
        assert normalized_digest(a) == normalized_digest(b)

    def test_docx_content_change_detected(self, tmp_path):
        a = tmp_path / 'a.docx'
        b = tmp_path / 'b.docx'
        _write_docx(a, body_text='hello')
        _write_docx(b, body_text='goodbye')
        assert normalized_digest(a) != normalized_digest(b)

    def test_xlsx_extension_uses_ooxml_normalizer(self, tmp_path):
        path = tmp_path / 'a.xlsx'
        _write_docx(path)
        assert normalize_ooxml in default_normalizers(path)

    def test_not_a_zip_falls_back_to_raw(self, tmp_path):
        path = tmp_path / 'a.docx'
        path.write_bytes(b'this is not a zip archive')
        assert normalized_digest(path) == hashlib.sha256(
            b'this is not a zip archive').hexdigest()


class TestBinaries:
    def test_raw_hash_for_opaque_binary(self, tmp_path):
        blob = bytes(range(256))
        path = tmp_path / 'blob.bin'
        path.write_bytes(blob)
        assert default_normalizers(path) == []
        assert normalized_digest(path) == hashlib.sha256(blob).hexdigest()


class TestDiscoveryAndReport:
    def test_discover_skips_sidecars_and_dashboard(self, tmp_path):
        (tmp_path / 'a.html').write_text('x')
        (tmp_path / 'a.html.sha256').write_text('deadbeef')
        (tmp_path / 'inspection_status.html').write_text('dash')
        found = discover_artifacts(tmp_path)
        assert [p.name for p in found] == ['a.html']

    def test_status_report_lists_artifacts(self, tmp_path):
        a = tmp_path / 'a.html'
        b = tmp_path / 'b.html'
        a.write_text('x')
        b.write_text('y')
        certify_file(a)
        html = render_status_report([a, b], 'python certify.py --certify')
        assert 'CERTIFIED' in html and 'UNCERTIFIED' in html
        assert 'a.html' in html and 'b.html' in html

    def test_self_dogfooding_dashboard_certifiable(self, tmp_path):
        a = tmp_path / 'a.html'
        a.write_text('x')
        certify_file(a)
        html = render_status_report([a], 'python certify.py')
        dash = tmp_path / 'inspection_status.html'
        dash.write_text(html)
        # A dashboard artifact can itself be certified and verified:
        certify_file(dash)
        check_inspection_hash(dash)


class TestCli:
    def test_status_then_certify_all(self, tmp_path, capsys):
        a = tmp_path / 'a.html'
        a.write_text('x')
        certify_main(['--root', str(tmp_path)])
        out = capsys.readouterr().out
        assert 'UNREVIEWED' in out
        certify_main(['--root', str(tmp_path), '--certify'])
        assert artifact_status(a) == CERTIFIED

    def test_certify_single_file(self, tmp_path):
        a = tmp_path / 'a.html'
        b = tmp_path / 'b.html'
        a.write_text('x')
        b.write_text('y')
        certify_main(['--root', str(tmp_path), '--certify', str(a)])
        assert artifact_status(a) == CERTIFIED
        assert artifact_status(b) == UNCERTIFIED

    def test_dashboard_written(self, tmp_path):
        (tmp_path / 'a.html').write_text('x')
        certify_main(['--root', str(tmp_path), '--dashboard'])
        assert (tmp_path / 'inspection_status.html').exists()
