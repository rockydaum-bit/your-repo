from pathlib import Path
import json
import re
import pytest

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "repo_manifest.json"
FILELIST_PATH = ROOT / "repo_file_list.txt"

EXCLUDED_DIRS = [
    "build",
    "ui_dist",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
]
EXCLUDED_PATH_FRAGMENTS = [
    "data/logs",
    "data/state",
]
EXCLUDED_EXTS = [".pyc", ".pyo", ".exe", ".pkg", ".pyz", ".zip", ".tar", ".gz"]
EXACT_EXCLUDES = {
    "repo_file_list.txt",
    "repo_manifest.json",
    "config/yt_token.json",
    "config/yt_client_secrets.json",
    ".coverage",
    ".coverage_threshold",
}

HEX64_RE = re.compile(r"^[A-Fa-f0-9]{64}$")


def load_manifest():
    assert MANIFEST_PATH.exists(), f"Manifest missing: {MANIFEST_PATH}"
    text = MANIFEST_PATH.read_text(encoding="utf8")
    try:
        data = json.loads(text)
    except Exception as e:
        pytest.fail(f"Manifest is not valid JSON: {e}")
    assert isinstance(data, list), "Manifest must be a JSON array"
    return data


def load_filelist():
    assert FILELIST_PATH.exists(), f"File list missing: {FILELIST_PATH}"
    lines = [l.rstrip("\r\n") for l in FILELIST_PATH.read_text(encoding="utf8").splitlines()]
    return lines


def normalize(p: str) -> str:
    p2 = p.replace("\\", "/")
    p2 = re.sub(r'^\./', '', p2)
    p2 = p2.lstrip('/')
    return p2


def is_drive_absolute(p: str) -> bool:
    return bool(re.match(r'^[A-Za-z]:/', p))


def test_manifest_entries_structure_and_types_and_values():
    manifest = load_manifest()
    prev = None
    seen = set()
    for idx, entry in enumerate(manifest):
        assert isinstance(entry, dict), f"manifest[{idx}] must be an object"
        for key in ("path", "size", "sha256"):
            assert key in entry, f"manifest[{idx}] missing key '{key}'"
        path = entry["path"]
        size = entry["size"]
        sha = entry["sha256"]

        # path checks
        assert isinstance(path, str), f"manifest[{idx}].path must be string (offending index {idx})"
        norm = normalize(path)
        assert norm != "", f"manifest[{idx}].path is blank"
        assert norm == path, f"manifest[{idx}].path must be normalized (forward slashes, no leading slash): '{path}'"
        assert not is_drive_absolute(path), f"manifest[{idx}].path must be relative (no drive letter): '{path}'"
        assert not path.startswith('/'), f"manifest[{idx}].path must not start with '/': '{path}'"

        # size checks
        assert isinstance(size, int), f"manifest[{idx}].size must be int for path '{path}'"
        assert size >= 0, f"manifest[{idx}].size must be non-negative for path '{path}'"

        # sha checks
        assert isinstance(sha, str), f"manifest[{idx}].sha256 must be string for path '{path}'"
        assert HEX64_RE.match(sha), f"manifest[{idx}].sha256 invalid for path '{path}': '{sha}'"

        # duplicates
        assert path not in seen, f"Duplicate path in manifest: '{path}'"
        seen.add(path)

        # ordering
        if prev is not None:
            assert prev <= path, f"Manifest not sorted: previous '{prev}' > current '{path}'"
        prev = path


def test_exclusions_not_present_in_manifest():
    manifest = load_manifest()
    for entry in manifest:
        path = entry["path"]
        lc = path.lower()

        # exact excludes (full normalized path)
        if path in EXACT_EXCLUDES:
            pytest.fail(f"Excluded exact path present in manifest: '{path}'")

        # .secrets anywhere
        if '.secrets' in lc:
            pytest.fail(f"Excluded fragment '.secrets' present in manifest path: '{path}'")

        # extensions
        for ext in EXCLUDED_EXTS:
            if lc.endswith(ext):
                pytest.fail(f"Excluded extension '{ext}' present in manifest path: '{path}'")

        # excluded repo-root dirs: two checks
        for seg in EXCLUDED_DIRS:
            # startswith check for repo-root dir
            if path == seg or path.startswith(seg + '/'):
                pytest.fail(f"Excluded directory prefix '{seg}/' matched by manifest path (startswith): '{path}'")
            # segment containment regex
            if re.search(r'(^|/)' + re.escape(seg) + r'(/|$)', path, flags=re.IGNORECASE):
                pytest.fail(f"Excluded directory segment '{seg}' found in manifest path (segment match): '{path}'")

        # excluded path fragments
        for frag in EXCLUDED_PATH_FRAGMENTS:
            frag_norm = frag.rstrip('/')
            if path == frag_norm or path.startswith(frag_norm + '/'):
                pytest.fail(f"Excluded path fragment '{frag}' matched by manifest path (startswith): '{path}'")
            if re.search(r'(^|/)' + re.escape(frag_norm) + r'(/|$)', path, flags=re.IGNORECASE):
                pytest.fail(f"Excluded path fragment '{frag}' found in manifest path (segment match): '{path}'")


def test_repo_file_list_matches_manifest_exactly():
    manifest = load_manifest()
    manifest_paths = [e['path'] for e in manifest]
    filelist = load_filelist()

    # no blank lines in filelist
    for idx, line in enumerate(filelist):
        assert line != '', f"repo_file_list.txt contains blank line at index {idx}"

    filelist_norm = [normalize(l) for l in filelist]

    assert len(filelist_norm) == len(manifest_paths), (
        f"Length mismatch: repo_file_list.txt has {len(filelist_norm)} lines, manifest has {len(manifest_paths)} entries"
    )
    for idx, (fl, mp) in enumerate(zip(filelist_norm, manifest_paths)):
        assert fl == mp, f"Line {idx} mismatch: repo_file_list.txt='{fl}' != manifest.path='{mp}'"


def test_manifest_sorted_and_unique():
    manifest = load_manifest()
    paths = [e['path'] for e in manifest]
    assert paths == sorted(paths), "Manifest paths are not sorted lexicographically"
    assert len(paths) == len(set(paths)), f"Duplicate paths found in manifest: {paths}"
