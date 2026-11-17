#!/usr/bin/env python3
"""Check upstream HEAD revisions without modifying local files."""

import http.client
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


MANIFEST_PATH = Path(__file__).resolve().with_name('upstreams.json')
REVISION = re.compile(r'[0-9a-f]{40}\Z')
REPOSITORY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*\Z')


def main():
    try:
        entries = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
        if not isinstance(entries, list) or not entries:
            raise ValueError('upstreams.json must contain a non-empty list')
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('each entry must be an object')
            repo, revision = entry.get('repo'), entry.get('revision')
            if not isinstance(repo, str) or not REPOSITORY.fullmatch(repo):
                raise ValueError('invalid repo in upstreams.json')
            if not isinstance(revision, str) or not REVISION.fullmatch(revision):
                raise ValueError(f'invalid revision for {repo}')
            if repo.lower() in seen:
                raise ValueError(f'duplicate repo: {repo}')
            seen.add(repo.lower())
    except (OSError, ValueError) as error:
        print(f'Ошибка списка источников: {error}', file=sys.stderr)
        return 2

    failures = 0
    for entry in entries:
        repo, baseline = entry['repo'], entry['revision']
        request = urllib.request.Request(
            f'https://api.github.com/repos/{repo}/commits/HEAD',
            headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'humanizer2-upstream-check'},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                result = json.load(response)
            revision = result.get('sha') if isinstance(result, dict) else None
            if not isinstance(revision, str) or not REVISION.fullmatch(revision):
                raise ValueError('invalid commit SHA in GitHub response')
        except (OSError, ValueError, http.client.HTTPException, urllib.error.URLError) as error:
            print(f'Ошибка проверки {repo}: {error}', file=sys.stderr)
            failures += 1
            continue

        if revision == baseline:
            print(f'{repo}: изменений нет ({baseline})')
        else:
            print(f'{repo}: найдены изменения\n'
                  f'  Было: {baseline}\n'
                  f'  Стало: {revision}\n'
                  f'  Для проверки: https://github.com/{repo}/compare/{baseline}...{revision}')

    if failures:
        print(f'Не удалось проверить источников: {failures}', file=sys.stderr)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
