"""Verify current source/resources and installed entry points in release archives."""
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import tarfile
import tomllib
from zipfile import ZipFile
import argparse

ROOT=Path(__file__).resolve().parents[1]


def check(directory):
    project=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']
    version=project['version'];wheel=directory/f'cpu_llm-{version}-py3-none-any.whl';sdist=directory/f'cpu_llm-{version}.tar.gz'
    required={p.relative_to(ROOT/'src').as_posix():p for package in ('cpu_llm','fact_bridge') for p in (ROOT/'src'/package).rglob('*.py')}
    required.update({p.relative_to(ROOT/'src').as_posix():p for p in (ROOT/'src/cpu_llm/data').rglob('*') if p.is_file()})
    required.update({p.relative_to(ROOT/'src').as_posix():p for p in (ROOT/'src/cpu_llm/checkpoints').glob('*') if p.is_file()})
    with ZipFile(wheel) as archive:
        names=archive.namelist()
        metadata=BytesParser().parsebytes(archive.read(f'cpu_llm-{version}.dist-info/METADATA'))
        assert metadata['Name']=='cpu-llm' and metadata['Version']==version
        assert metadata['License-Expression']=='Apache-2.0'
        assert metadata['Description-Content-Type']=='text/markdown'
        entries=archive.read(f'cpu_llm-{version}.dist-info/entry_points.txt').decode()
        for name,entry in project['scripts'].items():assert f'{name} = {entry}' in entries,name
        for name,path in required.items():assert archive.read(name)==path.read_bytes(),name
        requirements=metadata.get_all('Requires-Dist') or []
        assert any('prismrag-patch[graph]' in r for r in requirements)
        assert any('tabulate' in r for r in requirements) and any('Jinja2' in r for r in requirements)
        assert not any('debug.log' in n or '.pypirc' in n or '/build/' in n for n in names)
    with tarfile.open(sdist,'r:gz') as archive:
        members={m.name:m for m in archive.getmembers() if m.isfile()}
        prefix=f'cpu_llm-{version}/'
        for name,path in required.items():
            assert archive.extractfile(members[prefix+'src/'+name]).read()==path.read_bytes(),name
        for name in ('README.md','PYPI_README.md','pyproject.toml','LICENSE','examples/healthcare/dataset.json',
                     'examples/conversation/run_demo.py','docs/releases/'+version+'.md'):
            assert prefix+name in members,name
        assert not any(n.endswith('debug.log') or '/build/' in n or '.pypirc' in n for n in members)
    return dict(version=version,verified_runtime_and_resource_files=len(required),entry_points=project['scripts'],
                artifacts={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (wheel,sdist)})


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    args=parser.parse_args();print(json.dumps(check(args.directory),indent=2))


if __name__=='__main__':main()
