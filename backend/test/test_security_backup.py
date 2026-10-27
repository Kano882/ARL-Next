"""Backup security tests use only temporary archives, never a live database."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest


SOURCE = Path(__file__).resolve().parents[1] / 'app/services/backup_archive.py'
spec = importlib.util.spec_from_file_location('backup_archive_test', SOURCE)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def make_tar(entries):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w:gz') as tar:
        for name, content in entries:
            member = tarfile.TarInfo(name)
            if isinstance(content, tuple):
                member.type, member.linkname = content
                tar.addfile(member)
            else:
                member.size = len(content)
                tar.addfile(member, io.BytesIO(content))
    return data.getvalue()


def make_backup(tmp_path, inner=None, manifest_change=None):
    components = {'mongo_dump.archive.gz': b'dummy dump'}
    files = {'mongo_dump': 'mongo_dump.archive.gz'}
    if inner:
        components['dicts.tar.gz'] = make_tar(inner)
        files['dicts'] = 'dicts.tar.gz'
    manifest = {'format_version': '1.0', 'files': files,
                'checksums': {name: hashlib.sha256(body).hexdigest() for name, body in components.items()}}
    if manifest_change:
        manifest_change(manifest)
    path = tmp_path / 'arl_backup_fixture.tar.gz'
    path.write_bytes(make_tar([('manifest.json', json.dumps(manifest).encode()), *components.items()]))
    return path


@pytest.mark.parametrize('name,content', [
    ('../escaped', b'bad'), ('/absolute', b'bad'), ('dicts/../../escaped', b'bad'),
    ('dicts\\..\\escaped', b'bad'), ('dicts/link', (tarfile.SYMTYPE, '../../escaped')),
    ('dicts/link', (tarfile.LNKTYPE, '../../escaped')), ('dicts/device', (tarfile.CHRTYPE, '')),
    ('routes/user.py', b'bad'),
])
def test_nested_unsafe_members_rejected_before_any_install(tmp_path, name, content):
    path = make_backup(tmp_path, [('dicts/good.txt', b'good'), (name, content)])
    destination = tmp_path / 'app/dicts'
    with pytest.raises(ValueError):
        archive.stage_restore(path, tmp_path / 'stage', {'dicts': ('dicts', destination)})
    assert not destination.exists()
    assert not (tmp_path / 'escaped').exists()


@pytest.mark.parametrize('name', ['../escaped', '/absolute', 'other.txt'])
def test_outer_extra_members_rejected(tmp_path, name):
    path = tmp_path / 'backup.tar.gz'
    path.write_bytes(make_tar([('manifest.json', b'{}'), (name, b'bad')]))
    with pytest.raises(ValueError):
        archive.read_manifest(path)


def test_manifest_paths_and_missing_checksums_rejected(tmp_path):
    for mutate in [lambda m: m['files'].update(mongo_dump='../outside'),
                   lambda m: m['checksums'].clear(),
                   lambda m: m.update(format_version='unknown')]:
        with pytest.raises(ValueError):
            archive.read_manifest(make_backup(tmp_path, manifest_change=mutate))


def test_duplicate_archive_members_rejected(tmp_path):
    path = tmp_path / 'duplicate.tar.gz'
    path.write_bytes(make_tar([('dicts/a', b'one'), ('dicts/a', b'two')]))
    with pytest.raises(ValueError):
        archive.safe_extract(path, tmp_path / 'stage', prefix='dicts')
    assert not (tmp_path / 'stage/dicts/a').exists()


def test_hash_mismatch_rejected(tmp_path):
    path = make_backup(tmp_path, manifest_change=lambda m: m['checksums'].update({'mongo_dump.archive.gz': '0' * 64}))
    with pytest.raises(ValueError, match='SHA256'):
        archive.stage_restore(path, tmp_path / 'stage', {})


def test_archive_cannot_exceed_available_disk_space(tmp_path, monkeypatch):
    from types import SimpleNamespace
    path = tmp_path / 'full.tar.gz'
    path.write_bytes(make_tar([('dicts/a', b'content')]))
    monkeypatch.setattr(archive.shutil, 'disk_usage', lambda _: SimpleNamespace(free=0))
    with pytest.raises(ValueError, match='空间'):
        archive.safe_extract(path, tmp_path / 'stage', prefix='dicts')
    assert not (tmp_path / 'stage/dicts/a').exists()


def test_valid_backup_stages_and_restores_only_data_directory(tmp_path):
    path = make_backup(tmp_path, [('dicts/a.txt', b'new value')])
    destination = tmp_path / 'app/dicts'
    destination.mkdir(parents=True)
    (destination / 'a.txt').write_text('old value')
    sibling = tmp_path / 'app/code.py'
    sibling.write_text('untouched')
    manifest, staged = archive.stage_restore(path, tmp_path / 'stage', {'dicts': ('dicts', destination)})
    assert manifest['format_version'] == '1.0'
    assert (destination / 'a.txt').read_text() == 'old value'
    for source, dest in staged:
        archive.install_staged(source, dest)
    assert (destination / 'a.txt').read_text() == 'new value'
    assert sibling.read_text() == 'untouched'


def test_existing_destination_symlink_is_rejected(tmp_path):
    path = make_backup(tmp_path, [('dicts/link/value', b'bad')])
    destination = tmp_path / 'app/dicts'
    destination.mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (destination / 'link').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='符号链接'):
        archive.stage_restore(path, tmp_path / 'stage', {'dicts': ('dicts', destination)})
    assert not (outside / 'value').exists()
