"""Run security and affected regression suites without connecting to MongoDB.

Install backend/requirements.txt plus pytest and mongomock, then run:
    python backend/test/run_security_regressions.py
HTTP/TLS tests use loopback servers; scanner and deployment actions are mocked.
"""

import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import mongomock
import pytest


def main():
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    sys.path[:0] = [str(root / 'backend'), str(root / 'backend/ARL-NPoC')]
    suites = [
        'test_security_backup.py', 'test_security_network.py', 'test_security_auth.py',
        'test_security_mcp_updater.py', 'test_backup_restore.py', 'test_telegram_tls.py',
        'test_task_scope.py', 'test_system_config_cache_invalidation.py',
        'test_http_status_filter.py', 'test_issue_49_vhost_amnesty.py',
        'test_wih_api_probe.py', 'test_fofa_runtime_config.py',
    ]
    with patch('pymongo.MongoClient', mongomock.MongoClient), tempfile.TemporaryDirectory() as temp:
        from app.services import backup_service
        with patch.object(backup_service, 'STATUS_FILE', str(Path(temp) / 'backup-status.json')):
            return pytest.main(['-q', '--disable-warnings', *[f'backend/test/{name}' for name in suites]])


if __name__ == '__main__':
    raise SystemExit(main())
