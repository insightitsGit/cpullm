"""Generate PYPI_README.md from README.md, turning repository-relative links into absolute GitHub links.

PyPI renders the long description outside the repository, so relative links would break there. Run after
editing README.md:

    python tools/build_pypi_readme.py
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://github.com/insightitsGit/cpullm/blob/main/'


def pypi_readme(text):
    return re.sub(r'\]\((?!https?://|#|mailto:)([^)\s]+)\)', lambda m: '](' + BASE + m[1] + ')', text)


def main():
    (ROOT / 'PYPI_README.md').write_text(pypi_readme((ROOT / 'README.md').read_text(encoding='utf-8')),
                                         encoding='utf-8')


if __name__ == '__main__':
    main()
