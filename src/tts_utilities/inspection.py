"""Human-certification workflow for generated test artifacts.

Tests generate Inspection Artifacts (HTML reports, Office documents,
binaries) whose correctness is a human judgment call. This module records
that judgment: a normalized sha256 of each artifact is committed in a
``.sha256`` sidecar file, and ``check_inspection_hash`` fails the test
suite when regenerated output drifts from the last certified form. A
human reviews the artifact in a browser or other viewer and re-certifies
with the ``certify`` tool, which is for human use only — never call it
from automated tests, CI, or agent tooling.

Normalization removes run-to-run nondeterminism before hashing (embedded
UUIDs, document timestamps) so only real content changes invalidate a
certification.
"""

import hashlib
import io
import re
import zipfile
from pathlib import Path

_UUID_RE = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    re.IGNORECASE,
)
_UUID_PLACEHOLDER = '00000000-0000-0000-0000-000000000000'

# OOXML members whose content carries save-time metadata rather than
# document substance. ``core.xml`` is normalized in place (timestamps
# blanked); the others are excluded from the hash entirely because they
# regenerate with unrelated content changes.
_OOXML_TIMESTAMPED_MEMBERS = ('docProps/core.xml',)
_OOXML_EXCLUDED_MEMBERS = ('calcChain.xml',)

_OOXML_TIMESTAMP_TAGS = (
    'dcterms:created', 'dcterms:modified', 'cp:lastModifiedBy',
)

_OOXML_EXTENSIONS = {'.docx', '.xlsx', '.pptx'}
_TEXT_EXTENSIONS = {
    '.html', '.htm', '.xml', '.txt', '.json', '.csv', '.svg', '.md',
    '.css', '.js',
}

CERTIFIED = 'CERTIFIED'
STALE = 'STALE'
UNCERTIFIED = 'UNCERTIFIED'

STATUS_BADGE = {
    CERTIFIED:   '<span class="badge certified">&#10003; CERTIFIED</span>',
    STALE:       '<span class="badge stale">&#9888; STALE</span>',
    UNCERTIFIED: '<span class="badge uncertified">&#9888; UNCERTIFIED</span>',
}

STATUS_GUIDANCE = {
    CERTIFIED:   "Hash matches - no action needed.",
    STALE:       "Output changed since last approval. Open, review, then re-certify.",
    UNCERTIFIED: "Never reviewed. Open, verify, then certify.",
}


def normalize_uuids(data):
    """Replace embedded UUIDs with a stable placeholder.

    Many report generators embed a runtime UUID in element ``id``
    attributes; normalizing keeps the hash stable across runs.
    """
    text = data.decode('utf-8', errors='replace')
    return _UUID_RE.sub(_UUID_PLACEHOLDER, text).encode('utf-8')


def normalize_ooxml(data):
    """Hash the deterministic content of an Office (OOXML zip) document.

    Members are hashed in sorted order by name, so zip member ordering and
    archive timestamps cannot affect the digest. Members listed in
    ``_OOXML_EXCLUDED_MEMBERS`` are skipped; members listed in
    ``_OOXML_TIMESTAMPED_MEMBERS`` have their timestamp/last-modified-by
    tags blanked before hashing. Returns the raw bytes unchanged if the
    data is not a readable zip archive.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        names = archive.namelist()
    except (zipfile.BadZipFile, OSError):
        return data

    h = hashlib.sha256()
    for name in sorted(names):
        if name in _OOXML_EXCLUDED_MEMBERS:
            continue
        content = archive.read(name)
        if name in _OOXML_TIMESTAMPED_MEMBERS:
            content = _blank_xml_tags(content, _OOXML_TIMESTAMP_TAGS)
        h.update(name.encode('utf-8'))
        h.update(b'\x00')
        h.update(content)
        h.update(b'\x00')
    return h.hexdigest().encode('ascii')


def _blank_xml_tags(content, tag_names):
    """Replace the inner text of the named XML tags with a placeholder."""
    text = content.decode('utf-8', errors='replace')
    for tag in tag_names:
        text = re.sub(
            r'(<%s[^>]*>).*?(</%s>)' % (re.escape(tag), re.escape(tag)),
            r'\g<1>NORMALIZED\g<2>',
            text,
            flags=re.DOTALL,
        )
    return text.encode('utf-8')


def default_normalizers(path):
    """Return the default normalizer pipeline for an artifact path.

    OOXML documents get the document normalizer; known text formats get
    UUID normalization; everything else is hashed raw. Pass an explicit
    ``normalizers`` list to ``check_inspection_hash`` to override.
    """
    ext = Path(path).suffix.lower()
    if ext in _OOXML_EXTENSIONS:
        return [normalize_ooxml]
    if ext in _TEXT_EXTENSIONS:
        return [normalize_uuids]
    return []


def normalized_digest(artifact_path, normalizers=None):
    """Compute the certified digest of an artifact file.

    ``normalizers`` is an ordered list of byte->byte callables applied
    before hashing; ``None`` selects the extension-based defaults.
    """
    artifact_path = Path(artifact_path)
    data = artifact_path.read_bytes()
    pipeline = (
        default_normalizers(artifact_path)
        if normalizers is None
        else list(normalizers)
    )
    for normalizer in pipeline:
        data = normalizer(data)
    return hashlib.sha256(data).hexdigest()


def sidecar_path(artifact_path):
    """The ``.sha256`` certification sidecar for an artifact."""
    artifact_path = Path(artifact_path)
    return artifact_path.with_suffix(artifact_path.suffix + '.sha256')


def artifact_status(artifact_path, normalizers=None):
    """CERTIFIED, STALE, or UNCERTIFIED for the given artifact."""
    sidecar = sidecar_path(artifact_path)
    if not sidecar.exists():
        return UNCERTIFIED
    committed = sidecar.read_text().strip().split()[0]
    current = normalized_digest(artifact_path, normalizers)
    return CERTIFIED if current == committed else STALE


def certify_file(artifact_path, normalizers=None):
    """Write the ``.sha256`` sidecar recording approval of the artifact.

    This is the human stamp of approval. It must only be invoked from the
    human-facing certify tool, never from tests, CI, or automated agents.
    """
    artifact_path = Path(artifact_path)
    digest = normalized_digest(artifact_path, normalizers)
    sidecar = sidecar_path(artifact_path)
    sidecar.write_text('%s  %s\n' % (digest, artifact_path.name))
    print('  Certified: %s  (%s...)' % (artifact_path.name, digest[:12]))


def check_inspection_hash(artifact_path, normalizers=None, certify_hint=None):
    """Assert the artifact matches its committed human-certification hash.

    Any change in rendered output requires a human to open the file,
    verify it looks correct, and re-run the certify tool before the test
    suite will pass again.

    Parameters
    ----------
    artifact_path : Path or str
        Path to the generated artifact. A ``.sha256`` sidecar file must
        exist alongside it containing the committed digest.
    normalizers : list of callables, optional
        Ordered byte->byte transforms applied before hashing; defaults to
        the extension-based pipeline.
    certify_hint : str, optional
        Text of the command a human should run to certify, embedded in
        failure messages. Defaults to a generic instruction.

    Raises
    ------
    AssertionError
        If no sidecar exists (UNCERTIFIED) or the digest has drifted
        (STALE).
    """
    artifact_path = Path(artifact_path)
    certify_cmd = certify_hint or 'the certify tool for this project'
    sidecar = sidecar_path(artifact_path)
    current = normalized_digest(artifact_path, normalizers)

    if not sidecar.exists():
        raise AssertionError(
            "\nNo certification hash found for: %s\n"
            "\n  Steps to certify:"
            "\n    1. Open and review: %s"
            "\n    2. Verify the output looks correct."
            "\n    3. Run: %s"
            "\n    4. Commit the resulting .sha256 file.\n"
            % (artifact_path.name, artifact_path.resolve(), certify_cmd)
        )

    committed = sidecar.read_text().strip().split()[0]
    if current != committed:
        raise AssertionError(
            "\nArtifact has changed since last human certification: %s\n"
            "\n  Steps to re-certify:"
            "\n    1. Open and review: %s"
            "\n    2. Verify the changes are intentional and look correct."
            "\n    3. Run: %s"
            "\n    4. Commit the updated .sha256 file.\n"
            % (artifact_path.name, artifact_path.resolve(), certify_cmd)
        )


def discover_artifacts(root, status_report_name='inspection_status.html'):
    """All certifiable artifacts under ``root``, excluding sidecars and
    the status dashboard itself."""
    root = Path(root)
    return sorted(
        p for p in root.iterdir()
        if p.is_file()
        and not p.name.endswith('.sha256')
        and p.name != status_report_name
    )


def render_status_report(artifacts, certify_command):
    """Self-contained HTML status dashboard for a list of artifacts."""
    rows = ''
    for art in artifacts:
        status = artifact_status(art)
        rows += (
            '<tr><td>%s</td>'
            '<td><a href="%s" target="_blank">%s</a></td>'
            '<td>%s</td></tr>\n'
            % (STATUS_BADGE[status], art.name, art.name,
               STATUS_GUIDANCE[status])
        )

    counts = {
        s: sum(1 for a in artifacts if artifact_status(a) == s)
        for s in (CERTIFIED, STALE, UNCERTIFIED)
    }
    needs_review = counts[STALE] + counts[UNCERTIFIED]
    summary_class = 'ok' if needs_review == 0 else 'warn'
    summary_msg = (
        'All artifacts have been certified by a human reviewer.'
        if needs_review == 0 else
        '%d artifact(s) need human review. Open each linked file, verify '
        'it looks correct, then run <code>%s</code>.'
        % (needs_review, certify_command)
    )

    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Inspection Artifact Review Status</title>
  <style>
    body {{ font-family: sans-serif; max-width: 960px; margin: 40px auto; padding: 0 20px; color: #333; }}
    h1 {{ font-size: 1.6em; }}
    .summary {{ padding: 14px 18px; border-radius: 6px; margin-bottom: 24px; font-size: 1em; }}
    .summary.ok   {{ background: #d4edda; border-left: 4px solid #28a745; }}
    .summary.warn {{ background: #fff3cd; border-left: 4px solid #ffc107; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
    th {{ background: #f1f3f5; padding: 10px 12px; text-align: left; border-bottom: 2px solid #dee2e6; }}
    td {{ padding: 10px 12px; border-bottom: 1px solid #dee2e6; vertical-align: top; }}
    a {{ color: #0066cc; }}
    .badge {{ display: inline-block; padding: 3px 10px; border-radius: 4px; font-size: 0.85em; font-weight: bold; }}
    .badge.certified   {{ background: #28a745; color: white; }}
    .badge.stale       {{ background: #dc3545; color: white; }}
    .badge.uncertified {{ background: #ffc107; color: #333; }}
    .how-to {{ background: #f8f9fa; border-radius: 6px; padding: 18px 22px; }}
    .how-to h2 {{ margin-top: 0; font-size: 1.1em; }}
    .how-to ol {{ margin: 0; padding-left: 20px; }}
    .how-to li {{ margin-bottom: 6px; }}
    code {{ background: #e9ecef; padding: 2px 6px; border-radius: 3px; font-size: 0.92em; }}
  </style>
</head>
<body>
  <h1>Inspection Artifact Review Status</h1>
  <p>{certified} certified &nbsp;|&nbsp; {stale} stale &nbsp;|&nbsp;
     {uncertified} uncertified &nbsp;|&nbsp; {total} total</p>
  <div class="summary {summary_class}">{summary_msg}</div>
  <table>
    <thead><tr><th>Status</th><th>Artifact</th><th>Guidance</th></tr></thead>
    <tbody>
{rows}    </tbody>
  </table>
  <div class="how-to">
    <h2>How to certify</h2>
    <ol>
      <li>Run the test suite to regenerate all artifacts.</li>
      <li>Click each UNCERTIFIED or STALE link above and verify the output.</li>
      <li>When satisfied, stamp your approval:
          <code>{certify_command}</code></li>
      <li>Commit the resulting <code>.sha256</code> files - they are the
          record of your review.</li>
    </ol>
    <p><strong>Never certify from CI or automated scripts.</strong>
       The .sha256 files are your personal stamp. Only update them after a
       human has looked.</p>
  </div>
</body>
</html>
""".format(
        certified=counts[CERTIFIED],
        stale=counts[STALE],
        uncertified=counts[UNCERTIFIED],
        total=len(artifacts),
        summary_class=summary_class,
        summary_msg=summary_msg,
        rows=rows,
        certify_command=certify_command,
    )


def print_status(artifacts, certify_command):
    """Console summary of artifact certification statuses."""
    if not artifacts:
        print('No inspection artifacts found.')
        return
    print('\nInspection Artifact Review Status\n' + '=' * 36)
    needs_review = 0
    icons = {CERTIFIED: 'OK', STALE: 'STALE', UNCERTIFIED: 'UNREVIEWED'}
    for art in artifacts:
        s = artifact_status(art)
        print('  [%s]  %s' % (icons[s].ljust(11), art.name))
        if s != CERTIFIED:
            needs_review += 1
    print()
    if needs_review:
        print('  %d artifact(s) need review.' % needs_review)
        print('  Open each file, verify it, then run: %s' % certify_command)
    else:
        print('  All artifacts certified.')


def certify(targets, normalizers=None):
    """Stamp ``.sha256`` approval files for each target artifact."""
    if not targets:
        print('No artifacts to certify.')
        return
    print('Certifying inspection artifacts:')
    for path in targets:
        path = Path(path)
        if not path.exists():
            print('  SKIP (not found): %s' % path)
            continue
        certify_file(path, normalizers)
    print(
        '\nDone. %d artifact(s) certified.\n'
        'Commit the updated .sha256 files to record your approval.'
        % len(targets)
    )
