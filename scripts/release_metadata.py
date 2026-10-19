"""Describe a tested source-only research prerelease without shipping datasets."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def git(root, *args, check=True):
    return subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                          text=True, check=check)


def build_metadata(root, source_commit):
    root = Path(root)
    if not re.fullmatch(r'[0-9a-f]{40}', source_commit):
        raise ValueError('source must identify the tested commit')
    if git(root, 'rev-parse', 'HEAD').stdout.strip() != source_commit:
        raise ValueError('source differs from tested checkout')
    if git(root, 'status', '--porcelain', '--untracked-files=no').stdout.strip():
        raise ValueError('tracked source has uncommitted changes')
    matches = re.findall(r'^version\s*=\s*"(\d+\.\d+\.\d+)"\s*$',
                         (root / 'pyproject.toml').read_text(), re.MULTILINE)
    if len(matches) != 1:
        raise ValueError('expected one stable numeric project version')
    version = matches[0]
    tag = 'v' + version
    existing = git(root, 'rev-parse', '--verify', f'refs/tags/{tag}^{{commit}}', check=False)
    skip = existing.returncode == 0 and existing.stdout.strip() != source_commit
    allowed_roots = {'src', 'tests', 'scripts', 'config', 'docs', '.github'}
    allowed_files = {'.gitignore', 'README.md', 'pyproject.toml', 'requirements.txt', 'requirements.lock.txt'}
    hashes = {}
    for name in git(root, 'ls-files', '-z').stdout.split('\0'):
        if not name:
            continue
        path = Path(name)
        if name not in allowed_files and path.parts[0] not in allowed_roots:
            raise ValueError(f'non-source release path: {name}')
        hashes[name] = hashlib.sha256((root / path).read_bytes()).hexdigest()
    return {'version': version, 'tag': tag, 'source_commit': source_commit,
            'managed_files': hashes, 'skip_publish': skip,
            'release_type': 'RESEARCH_PRERELEASE', 'historical_claims_status': 'UNVERIFIED',
            'SIGNAL_STATUS': 'DATA_HOLD', 'SAFE_TO_ACT': False}


def main():
    if os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('only tested main commits may publish')
    root = Path(__file__).resolve().parents[1]
    manifest = build_metadata(root, os.environ['GITHUB_SHA'])
    Path('release.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    with open(os.environ['GITHUB_OUTPUT'], 'a') as handle:
        handle.write(f"tag={manifest['tag']}\nsource_commit={manifest['source_commit']}\n")
        handle.write(f"skip_publish={str(manifest['skip_publish']).lower()}\n")


if __name__ == '__main__':
    main()
