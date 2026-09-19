"""Tests for the artifact human-certification workflow."""

import hashlib
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
    register_normalizer,
    render_status_report,
    sidecar_path,
)


@pytest.fixture
def artifact(tmp_path):
    """A minimal HTML artifact in a temp directory."""
    path = tmp_path / 'report.html'
    path.write_text('<html><body><div id="x">hello</div></body></html>')
    return path


def _write_docx(path, body_text='hello',
                timestamps=('2024-01-01T00:00:00Z',),
                modified_by='someone', calc_chain='<calcChain/>'):
    """Write a minimal synthetic .docx (zip of XML members)."""
    core = (
        '<?xml version="1.0"?><cp:coreProperties '
        'xmlns:cp="x" xmlns:dcterms="y">'
        '<dcterms:created>%s</dcterms:created>'
        '<dcterms:modified>%s</dcterms:modified>'
        '<cp:lastModifiedBy>%s</cp:lastModifiedBy>'
        '</cp:coreProperties>'
    ) % (
        (timestamps + ('2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z'))[:2]
        + (modified_by,)
    )
    with zipfile.ZipFile(str(path), 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr(
            'word/document.xml', '<w:document>%s</w:document>' % body_text)
        archive.writestr('docProps/core.xml', core)
        # Excel stores the chain under xl/; keep the realistic path so
        # basename matching is what actually excludes it.
        archive.writestr('xl/calcChain.xml', calc_chain)


@pytest.mark.unreviewed_ai
class TestUuidNormalization:
    def test_uuids_replaced(self):
        data = b'id="3f8a9b2c-1111-4222-8333-abcdef012345"'
        out = normalize_uuids(data)
        assert b'00000000-0000-0000-0000-000000000000' in out

    def test_different_uuids_same_hash(self, tmp_path):
        first = tmp_path / 'a.html'
        second = tmp_path / 'b.html'
        first.write_text(
            '<div id="3f8a9b2c-1111-4222-8333-abcdef012345">x</div>')
        second.write_text(
            '<div id="99998888-7777-4666-8555-0123456789ab">x</div>')
        assert normalized_digest(first) == normalized_digest(second)

    def test_normalizers_compose_in_order(self, tmp_path):
        path = tmp_path / 'a.html'
        path.write_text('A_VERSION_B')
        replace_a = lambda data: data.replace(b'A', b'Z')
        replace_version = lambda data: data.replace(b'VERSION', b'V')
        both = normalized_digest(
            path, normalizers=[replace_a, replace_version])
        only_second = normalized_digest(path, normalizers=[replace_version])
        assert both != only_second
        assert hashlib.sha256(b'Z_V_B').hexdigest() == both


@pytest.mark.unreviewed_ai
class TestNormalizerRegistry:
    def test_registered_normalizer_applies_to_defaults(self, tmp_path):
        path = tmp_path / 'a.html'
        path.write_text('HELLO')
        before = normalized_digest(path)
        register_normalizer(lambda data: data.lower())
        try:
            after = normalized_digest(path)
        finally:
            # Registry is process-global; never leak it into other tests.
            from tts_utilities import inspection
            inspection._GLOBAL_NORMALIZERS.clear()
        assert after != before
        assert after == hashlib.sha256(b'hello').hexdigest()


@pytest.mark.unreviewed_ai
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


@pytest.mark.unreviewed_ai
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


@pytest.mark.unreviewed_ai
class TestOoxml:
    def test_docx_stable_across_timestamps(self, tmp_path):
        first = tmp_path / 'a.docx'
        second = tmp_path / 'b.docx'
        _write_docx(
            first, timestamps=('2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z'))
        _write_docx(
            second, timestamps=('2030-06-15T12:34:56Z', '2030-06-15T12:34:56Z'))
        assert normalized_digest(first) == normalized_digest(second)

    def test_docx_member_order_irrelevant(self, tmp_path):
        first = tmp_path / 'a.docx'
        second = tmp_path / 'b.docx'
        _write_docx(first)
        core = (
            '<?xml version="1.0"?><cp:coreProperties '
            'xmlns:cp="x" xmlns:dcterms="y">'
            '<dcterms:created>2024-01-01T00:00:00Z</dcterms:created>'
            '<dcterms:modified>2024-01-01T00:00:00Z</dcterms:modified>'
            '<cp:lastModifiedBy>someone</cp:lastModifiedBy>'
            '</cp:coreProperties>'
        )
        with zipfile.ZipFile(str(second), 'w') as archive:
            archive.writestr('xl/calcChain.xml', '<calcChain/>')
            archive.writestr('docProps/core.xml', core)
            archive.writestr(
                'word/document.xml', '<w:document>hello</w:document>')
            archive.writestr('[Content_Types].xml', '<Types/>')
        assert normalized_digest(first) == normalized_digest(second)

    def test_volatile_members_do_not_affect_hash(self, tmp_path):
        """Differing calcChain content and lastModifiedBy hash identically."""
        first = tmp_path / 'a.docx'
        second = tmp_path / 'b.docx'
        _write_docx(
            first, calc_chain='<calcChain><c r="A1"/></calcChain>',
            modified_by='alice')
        _write_docx(
            second,
            calc_chain='<calcChain><c r="A1"/><c r="B7"/></calcChain>',
            modified_by='bob')
        assert normalized_digest(first) == normalized_digest(second)

    def test_docx_content_change_detected(self, tmp_path):
        first = tmp_path / 'a.docx'
        second = tmp_path / 'b.docx'
        _write_docx(first, body_text='hello')
        _write_docx(second, body_text='goodbye')
        assert normalized_digest(first) != normalized_digest(second)

    def test_xlsx_extension_uses_ooxml_normalizer(self, tmp_path):
        path = tmp_path / 'a.xlsx'
        _write_docx(path)
        assert normalize_ooxml in default_normalizers(path)

    def test_not_a_zip_falls_back_to_raw(self, tmp_path):
        path = tmp_path / 'a.docx'
        path.write_bytes(b'this is not a zip archive')
        assert normalized_digest(path) == hashlib.sha256(
            b'this is not a zip archive').hexdigest()


@pytest.mark.unreviewed_ai
class TestBinaries:
    def test_raw_hash_for_opaque_binary(self, tmp_path):
        blob = bytes(range(256))
        path = tmp_path / 'blob.bin'
        path.write_bytes(blob)
        assert default_normalizers(path) == []
        assert normalized_digest(path) == hashlib.sha256(blob).hexdigest()


@pytest.mark.unreviewed_ai
class TestDiscoveryAndReport:
    def test_discover_skips_sidecars_and_dashboard(self, tmp_path):
        (tmp_path / 'a.html').write_text('x')
        (tmp_path / 'a.html.sha256').write_text('deadbeef')
        (tmp_path / 'inspection_status.html').write_text('dash')
        found = discover_artifacts(tmp_path)
        assert [p.name for p in found] == ['a.html']

    def test_discover_scopes_to_pattern(self, tmp_path):
        (tmp_path / 'a.html').write_text('x')
        (tmp_path / 'notes.txt').write_text('y')
        (tmp_path / 'raw.bin').write_bytes(b'z')
        assert [p.name for p in discover_artifacts(tmp_path)] == ['a.html']
        assert [
            p.name for p in discover_artifacts(tmp_path, pattern='*.bin')
        ] == ['raw.bin']

    def test_status_report_lists_artifacts(self, tmp_path):
        first = tmp_path / 'a.html'
        second = tmp_path / 'b.html'
        first.write_text('x')
        second.write_text('y')
        certify_file(first)
        html = render_status_report([first, second], 'python certify.py --certify')
        assert 'CERTIFIED' in html and 'UNCERTIFIED' in html
        assert 'a.html' in html and 'b.html' in html

    def test_self_dogfooding_dashboard_certifiable(self, tmp_path):
        first = tmp_path / 'a.html'
        first.write_text('x')
        certify_file(first)
        html = render_status_report([first], 'python certify.py')
        dashboard = tmp_path / 'inspection_status.html'
        dashboard.write_text(html)
        # A dashboard artifact can itself be certified and verified:
        certify_file(dashboard)
        check_inspection_hash(dashboard)
