"""Validate backup archives before extracting or replacing application data."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile


COMPONENTS = {
    'mongo_dump': 'mongo_dump.archive.gz',
    'screenshots': 'screenshots.tar.gz',
    'dicts': 'dicts.tar.gz',
    'pocs': 'pocs.tar.gz',
    'config': 'config.yaml',
}
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_MEMBERS = 1_000_000


def regular_backup_member(member):
    if not (member.isfile() or member.isdir()) or member.issym() or member.islnk():
        raise ValueError(f'备份源包含链接或特殊文件，无法安全恢复: {member.name}')
    return member


def _members(tar, *, prefix=None, allowed_names=None):
    """Reject links, devices, ambiguous paths and duplicate entries as a unit."""
    seen = set()
    members = []
    for member in tar:
        name = member.name
        parts = PurePosixPath(name).parts
        if (not parts or name.startswith('/') or '\\' in name or '\x00' in name
                or '..' in parts or member.size < 0 or not (member.isfile() or member.isdir())
                or member.issym() or member.islnk()):
            raise ValueError(f'备份包含不安全的归档成员: {name}')
        normalized = '/'.join(parts)
        if normalized in seen or len(members) >= MAX_MEMBERS:
            raise ValueError('备份包含重复成员或成员数量超限')
        if prefix and parts[0] != prefix:
            raise ValueError(f'备份成员不属于允许的 {prefix} 目录: {name}')
        if allowed_names is not None and (normalized not in allowed_names or not member.isfile()):
            raise ValueError(f'备份包含未声明的构件: {name}')
        seen.add(normalized)
        members.append(member)
    return members


def read_manifest(archive_path):
    with tarfile.open(archive_path, 'r:gz') as tar:
        members = _members(tar, allowed_names={'manifest.json', *COMPONENTS.values()})
        manifests = [m for m in members if m.name == 'manifest.json']
        if len(manifests) != 1 or manifests[0].size > MAX_MANIFEST_BYTES:
            raise ValueError('非法备份包：manifest.json 缺失或超过 1MB')
        with tar.extractfile(manifests[0]) as stream:
            manifest = json.load(stream)
        if not isinstance(manifest, dict) or manifest.get('format_version') != '1.0':
            raise ValueError('不支持的备份格式版本')
        files = manifest.get('files')
        checksums = manifest.get('checksums')
        if not isinstance(files, dict) or not isinstance(checksums, dict) or 'mongo_dump' not in files:
            raise ValueError('备份缺少构件清单、MongoDB 归档或校验和')
        for kind, name in files.items():
            if kind not in COMPONENTS or name != COMPONENTS[kind]:
                raise ValueError(f'非法的备份构件: {kind}')
            if not isinstance(checksums.get(name), str) or not re.fullmatch(r'[0-9a-f]{64}', checksums[name]):
                raise ValueError(f'备份构件缺少有效 SHA256 校验和: {name}')
        if set(checksums) != set(files.values()):
            raise ValueError('备份校验和与构件清单不一致')
        if {m.name for m in members} != {'manifest.json', *files.values()}:
            raise ValueError('备份归档与构件清单不一致')
        return manifest


def safe_extract(archive_path, destination, *, prefix=None, allowed_names=None):
    """Extract only regular files/directories, with no archive-controlled modes."""
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, 'r:gz') as tar:
        members = _members(tar, prefix=prefix, allowed_names=allowed_names)
        required = sum(member.size for member in members if member.isfile())
        if required > max(0, shutil.disk_usage(root).free - 16 * 1024 * 1024):
            raise ValueError('备份解压所需空间超过可用空间')
        # Validate all destinations before creating the first member.
        for member in members:
            _safe_destination(root, PurePosixPath(member.name).parts)
        for member in members:
            target = _safe_destination(root, PurePosixPath(member.name).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as src, target.open('xb') as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                target.chmod(0o600)


def _safe_destination(root, parts):
    current = Path(root)
    if current.is_symlink():
        raise ValueError(f'恢复目标不能是符号链接: {current}')
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f'恢复目标包含符号链接: {current}')
    if os.path.commonpath([root.resolve(), current.resolve()]) != str(root.resolve()):
        raise ValueError('恢复目标越界')
    return current


def stage_restore(archive_path, work_dir, destinations):
    """Validate and stage *all* components before mongorestore --drop is allowed."""
    manifest = read_manifest(archive_path)
    files = manifest['files']
    safe_extract(archive_path, work_dir, allowed_names={'manifest.json', *files.values()})
    for name, expected in manifest['checksums'].items():
        digest = hashlib.sha256()
        with open(os.path.join(work_dir, name), 'rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError(f'备份构件 SHA256 校验失败: {name}')
    staged = []
    for kind, (prefix, destination) in destinations.items():
        if kind not in files:
            continue
        stage = Path(work_dir) / ('stage_' + kind)
        safe_extract(os.path.join(work_dir, files[kind]), stage, prefix=prefix)
        source = stage / prefix
        if not source.is_dir():
            raise ValueError(f'备份缺少 {prefix} 目录')
        validate_install(source, destination)
        staged.append((source, Path(destination)))
    return manifest, staged


def validate_install(source, destination):
    root = Path(destination)
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError(f'非法恢复目录: {root}')
    for entry in Path(source).rglob('*'):
        target = _safe_destination(root, entry.relative_to(source).parts)
        if target.exists() and entry.is_dir() != target.is_dir():
            raise ValueError(f'恢复目标文件类型冲突: {target}')


def install_staged(source, destination):
    """Replace files atomically inside the specific data directory, never its parent."""
    validate_install(source, destination)
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    for entry in Path(source).rglob('*'):
        target = _safe_destination(root, entry.relative_to(source).parts)
        if entry.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix='.restore_', dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as dst, entry.open('rb') as src:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
