"""离线源码函数测试与回环 aiohttp 测试，不连接 MongoDB 或情报服务。"""
import ast
import asyncio
import copy
import importlib.util
import json
import logging
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger(__name__)
TID = 'a' * 24


def extract(path, names, env, cls=None):
    nodes = ast.parse((ROOT / path).read_text()).body
    if cls:
        nodes = next(n for n in nodes if isinstance(n, ast.ClassDef) and n.name == cls).body
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            node = copy.deepcopy(node)
            node.decorator_list = []
            exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(path), 'exec'), env)
    return env


class Collection:
    def __init__(self, docs=None):
        self.docs = copy.deepcopy(docs or [])
    def matches(self, doc, query):
        for key, value in query.items():
            current = doc.get(key)
            if isinstance(value, dict):
                if '$in' in value and current not in value['$in']: return False
                if '$nin' in value and current in value['$nin']: return False
            elif current != value: return False
        return True
    def find_one(self, query, *args):
        return next((d for d in self.docs if self.matches(d, query)), None)
    def find(self, query, *args): return [d for d in self.docs if self.matches(d, query)]
    def update_one(self, query, update):
        doc = self.find_one(query)
        if doc is not None:
            doc.update(update.get('$set', {}))
            for key in update.get('$unset', {}): doc.pop(key, None)
        return types.SimpleNamespace(matched_count=int(doc is not None))
    def insert_one(self, doc):
        doc = dict(doc, _id=doc.get('_id', TID))
        self.docs.append(doc)
        return types.SimpleNamespace(inserted_id=doc['_id'])
    def delete_one(self, query):
        doc = self.find_one(query)
        if doc: self.docs.remove(doc)
        return types.SimpleNamespace(deleted_count=int(doc is not None))
    def delete_many(self, query): self.docs[:] = [d for d in self.docs if not self.matches(d, query)]
    def update_many(self, query, update): pass


class AsyncCollection:
    def __init__(self, collection): self.collection = collection
    async def find_one(self, *args): return self.collection.find_one(*args)
    async def update_one(self, *args): return self.collection.update_one(*args)
    async def insert_one(self, *args): return self.collection.insert_one(*args)
    async def insert_many(self, docs, **kwargs):
        for doc in docs: self.collection.insert_one(doc)


def database(status='waiting'):
    return {'icp_task': Collection([{'_id': TID, 'status': status}]), 'icp_asset': Collection(),
            'syslog': Collection(), 'asset_scope': Collection()}


def runner(db):
    env = {'db': {k: AsyncCollection(v) for k, v in db.items()}, 'ObjectId': lambda x: x,
           'curr_date': lambda: '2026-10-12 12:00:00', 'logger': LOG,
           '__file__': str(ROOT / 'osint_service/clients/job_runner.py'), 'asyncio': asyncio, 're': re}
    return extract('osint_service/clients/job_runner.py',
                   ['_claim_recon_task', '_task_is_running', '_sync_scope_after_task_completion',
                    '_finish_recon_task', 'run_icp_job', 'run_tyc_job', '_upsert_task_asset'], env)


def route(db, cls, method):
    statuses = types.SimpleNamespace(WAITING='waiting', RUNNING='running', STOP='stop')
    errors = types.SimpleNamespace(Success={'code': 200}, Error={'code': 500}, NotFoundTask={'code': 404})
    env = {'conn_db': db.__getitem__, 'bson': types.SimpleNamespace(ObjectId=lambda x: x),
           'TaskStatus': statuses, 'ErrorMsg': errors, 'build_ret': lambda msg, data: dict(msg, data=data),
           'curr_date': lambda: '2026-10-12 12:00:00', 'logger': LOG, 'add_icp_task_fields': None}
    extract('app/routes/icp.py', ['_request_recon'], env)
    return extract('app/routes/icp.py', [method], env, cls)


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_claim_is_atomic_and_does_not_reanimate_terminal_tasks(self):
        db = database()
        env = runner(db)
        self.assertEqual(await asyncio.gather(env['_claim_recon_task'](TID), env['_claim_recon_task'](TID)), [True, False])
        for status in ('stop', 'done', 'error'):
            db['icp_task'].docs[0]['status'] = status
            self.assertFalse(await env['_claim_recon_task'](TID))
            self.assertEqual(db['icp_task'].docs[0]['status'], status)

    async def test_deleted_or_stopped_jobs_do_not_initialize_providers(self):
        for status in ('stop', None):
            db = database(status)
            if status is None: db['icp_task'].docs.clear()
            env = runner(db)
            with self.subTest(status=status):
                await env['run_icp_job']({'task_id': TID, 'target': 'fixture', 'query_type': ['web']})
                await env['run_tyc_job']({'task_id': TID, 'tyc_id': 'fixture', 'tyc_token': 'fixture'})
                self.assertEqual(db['icp_asset'].docs, [])

    async def test_stop_during_provider_request_discards_results(self):
        for stopped in (True, False):
            db = database()
            calls = []
            class Provider:
                async def ymWeb(self, *args, **kwargs):
                    calls.append(1)
                    if stopped: db['icp_task'].docs[0]['status'] = 'stop'
                    return {'code': 200, 'params': {'list': [{'domain': 'alpha.example'}]}}
                ymApp = ymWeb
                ymMiniApp = ymWeb
                ymKuaiApp = ymWeb
            with patch.dict(sys.modules, {'ymicp': types.SimpleNamespace(beian=Provider)}):
                await runner(db)['run_icp_job']({'task_id': TID, 'target': 'fixture', 'query_type': ['web']})
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(db['icp_asset'].docs), 0 if stopped else 1)
            self.assertEqual(db['icp_task'].docs[0]['status'], 'stop' if stopped else 'done')

    async def test_tyc_upsert_rejects_stopped_or_deleted_task(self):
        for status in ('stop', None):
            db = database(status)
            if status is None: db['icp_task'].docs.clear()
            inserted = await runner(db)['_upsert_task_asset'](TID, 'web', {'domain': 'alpha.example'}, 'fixture', {})
            self.assertFalse(inserted)
            self.assertEqual(db['icp_asset'].docs, [])

    async def test_finish_updates_scope_only_for_accepted_completion(self):
        for status in ('running', 'stop', 'error', 'done', None):
            for result_status in ('done', 'error'):
                with self.subTest(status=status, result_status=result_status):
                    db = database(status)
                    if status is None: db['icp_task'].docs.clear()
                    db['asset_scope'].docs = [{'_id': 'scope', 'synced_icp_task_id': 'old',
                                               'updating_icp_task_id': TID}]
                    await runner(db)['_finish_recon_task'](TID, result_status, {'$set': {'status': result_status}})
                    scope = db['asset_scope'].docs[0]
                    self.assertEqual(scope['synced_icp_task_id'],
                                     TID if status == 'running' and result_status == 'done' else 'old')
                    self.assertEqual('updating_icp_task_id' in scope, status != 'running')

    async def test_scope_completion_does_not_replace_a_newer_refresh(self):
        db = database('running')
        db['asset_scope'].docs = [{'_id': 'scope', 'synced_icp_task_id': 'old', 'updating_icp_task_id': TID}]
        env = runner(db)
        collection = env['db']['asset_scope']
        original = collection.find_one
        async def replace_during_lookup(query):
            found = copy.deepcopy(await original(query))
            db['asset_scope'].docs[0]['updating_icp_task_id'] = 'newer'
            return found
        collection.find_one = replace_during_lookup
        await env['_finish_recon_task'](TID, 'done', {'$set': {'status': 'done'}})
        self.assertEqual(db['asset_scope'].docs[0]['synced_icp_task_id'], 'old')
        self.assertEqual(db['asset_scope'].docs[0]['updating_icp_task_id'], 'newer')


class APIContractTests(unittest.TestCase):
    def setUp(self):
        provider = types.SimpleNamespace(TycClient=lambda: types.SimpleNamespace(gid='', token=''))
        patcher = patch.dict(sys.modules, {'app.services.tycClient': provider})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_dispatch_rejection_marks_waiting_error_and_returns_error(self):
        db = database()
        db['icp_task'].docs.clear()
        env = route(db, 'IcpTask', 'post')
        instance = types.SimpleNamespace(parse_args=lambda _: {'name': 'fixture', 'target': 'fixture', 'query_type': ['web']})
        response = types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'code': 500, 'msg': 'dispatch failed'})
        with patch('requests.post', return_value=response):
            result = env['post'](instance)
        self.assertEqual(result['code'], 500)
        self.assertEqual(db['icp_task'].docs[0]['status'], 'error')

    def test_dispatch_timeout_does_not_overwrite_an_already_running_job(self):
        db = database()
        db['icp_task'].docs.clear()
        env = route(db, 'IcpTask', 'post')
        instance = types.SimpleNamespace(parse_args=lambda _: {'name': 'fixture', 'target': 'fixture', 'query_type': ['web']})
        def accepted_but_response_lost(*args, **kwargs):
            db['icp_task'].docs[0]['status'] = 'running'
            raise TimeoutError('fixture response lost')
        with patch('requests.post', side_effect=accepted_but_response_lost) as send:
            self.assertEqual(env['post'](instance)['code'], 500)
        self.assertEqual(db['icp_task'].docs[0]['status'], 'running')
        self.assertEqual(send.call_count, 1)

    def test_acknowledgement_must_match_task(self):
        env = route(database(), 'IcpTask', 'post')
        response = types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'code': 200, 'task_id': 'b' * 24})
        with patch('requests.post', return_value=response), self.assertRaises(RuntimeError):
            env['_request_recon']('start', {'task_id': TID})

    def test_delete_preserves_records_when_stop_not_confirmed(self):
        db = database('stop')
        db['icp_asset'].insert_one({'task_id': TID})
        env = route(db, 'IcpTaskDelete', 'get')
        env['_request_recon'] = lambda *args: (_ for _ in ()).throw(RuntimeError('stop not acknowledged'))
        self.assertEqual(env['get'](None, TID)['code'], 500)
        self.assertEqual(len(db['icp_task'].docs), 1)
        self.assertEqual(len(db['icp_asset'].docs), 1)

    def test_confirmed_stop_allows_delete(self):
        db = database('stop')
        db['icp_asset'].insert_one({'task_id': TID})
        env = route(db, 'IcpTaskDelete', 'get')
        env['_request_recon'] = lambda *args: {'code': 200, 'task_id': TID}
        self.assertEqual(env['get'](None, TID)['data']['deleted_count'], 1)
        self.assertEqual(db['icp_task'].docs, [])
        self.assertEqual(db['icp_asset'].docs, [])

    def test_batch_delete_preserves_all_records_if_stop_fails(self):
        db = database('stop')
        db['icp_asset'].insert_one({'task_id': TID})
        env = route(db, 'IcpTaskBatchDelete', 'post')
        env['_request_recon'] = lambda *args: (_ for _ in ()).throw(RuntimeError('fixture'))
        with patch.dict(sys.modules, {'flask': types.SimpleNamespace(request=types.SimpleNamespace(json={'task_ids': [TID]}))}):
            result = env['post'](None)
        self.assertEqual(result['code'], 500)
        self.assertEqual(len(db['icp_task'].docs), 1)
        self.assertEqual(len(db['icp_asset'].docs), 1)

    def test_stop_failure_is_not_reported_as_success(self):
        db = database('running')
        env = route(db, 'IcpTaskStop', 'get')
        env['_request_recon'] = lambda *args: (_ for _ in ()).throw(RuntimeError('fixture'))
        self.assertEqual(env['get'](None, TID)['code'], 500)
        self.assertEqual(db['icp_task'].docs[0]['status'], 'stop')

    def test_auto_matched_tyc_dispatch_uses_acknowledgement_and_status_guard(self):
        for accepted_before_timeout in (False, True):
            with self.subTest(accepted_before_timeout=accepted_before_timeout):
                db = database()
                db['icp_task'].docs.clear()
                env = route(db, 'IcpTask', 'post')
                provider = types.SimpleNamespace(TycClient=lambda: types.SimpleNamespace(
                    gid='fixture', token='fixture', search_suggest=lambda _: {'gid': '123456', 'company_name': '企业'}))
                instance = types.SimpleNamespace(parse_args=lambda _: {'target': '企业', 'depth': 3, 'invest_ratio': 60})
                def send(*args, **kwargs):
                    self.assertEqual(kwargs['json']['type'], 'tyc')
                    self.assertEqual(kwargs['json']['depth'], 3)
                    self.assertEqual(kwargs['json']['invest_ratio'], 60)
                    if accepted_before_timeout:
                        db['icp_task'].docs[0]['status'] = 'running'
                        raise TimeoutError('fixture response lost')
                    return types.SimpleNamespace(raise_for_status=lambda: None,
                                                 json=lambda: {'code': 500, 'msg': 'rejected'})
                with patch.dict(sys.modules, {'app.services.tycClient': provider}), patch('requests.post', side_effect=send):
                    self.assertEqual(env['post'](instance)['code'], 500)
                self.assertEqual(db['icp_task'].docs[0]['status'], 'running' if accepted_before_timeout else 'error')

    def test_restart_dispatch_failure_clears_only_failed_refresh(self):
        old_id = 'c' * 24
        for outcome in ('rejected', 'running', 'newer'):
            with self.subTest(outcome=outcome):
                db = database('done')
                db['icp_task'].docs[0].update({'_id': old_id, 'target': 'fixture', 'synced_scope_id': 'scope'})
                db['asset_scope'].docs = [{'_id': 'scope', 'synced_icp_task_id': old_id}]
                env = route(db, 'IcpTask', 'post')
                extract('app/routes/icp.py', ['_restart_single_icp_task'], env)
                def fail(*args):
                    if outcome == 'running': db['icp_task'].docs[-1]['status'] = 'running'
                    if outcome == 'newer': db['asset_scope'].docs[0]['updating_icp_task_id'] = 'newer'
                    raise RuntimeError('fixture')
                env['_request_recon'] = fail
                self.assertFalse(env['_restart_single_icp_task'](old_id)[0])
                self.assertEqual(db['asset_scope'].docs[0]['synced_icp_task_id'], old_id)
                expected = {'rejected': None, 'running': TID, 'newer': 'newer'}[outcome]
                self.assertEqual(db['asset_scope'].docs[0].get('updating_icp_task_id'), expected)


class HTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from aiohttp import web
        from aiohttp.test_utils import TestClient, TestServer
        def load(name, path):
            spec = importlib.util.spec_from_file_location(name, ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        with patch.dict(sys.modules, {'mlog': types.SimpleNamespace(logger=LOG)}):
            manager_module = load('recon_manager_fixture', 'osint_service/task_manager.py')
        self.manager = manager_module.TaskManager()
        self.routes = load('recon_routes_fixture', 'osint_service/routes/recon_routes.py')
        app = web.Application()
        app['task_manager'] = self.manager
        app.router.add_post('/start', self.routes.start_recon)
        app.router.add_post('/stop', self.routes.stop_recon)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)

    async def test_real_http_dispatch_failure_has_error_status(self):
        with patch.object(self.routes, 'submit_recon_job', side_effect=RuntimeError('fixture')):
            response = await self.client.post('/start', json={'task_id': TID, 'type': 'icp'})
        self.assertEqual(response.status, 500)
        self.assertEqual((await response.json())['code'], 500)

    async def test_invalid_id_and_type_return_bad_request(self):
        for data in ({}, [], {'task_id': 'bad'}, {'task_id': TID, 'type': 'unknown'}):
            response = await self.client.post('/start', json=data)
            self.assertEqual(response.status, 400)

    async def test_stop_waits_for_cancel_cleanup_and_releases_semaphore(self):
        semaphore = self.manager.get_semaphore('recon_task', 1, dynamic=True)
        started, cleaned = asyncio.Event(), asyncio.Event()
        async def job():
            async with semaphore:
                try:
                    started.set()
                    await asyncio.Event().wait()
                finally:
                    await asyncio.sleep(0)
                    cleaned.set()
        task = asyncio.create_task(job())
        self.manager.add_task(TID, task)
        await started.wait()
        response = await self.client.post('/stop', json={'task_id': TID})
        self.assertEqual(response.status, 200)
        self.assertTrue(cleaned.is_set())
        self.assertTrue(task.cancelled())
        self.assertEqual(semaphore._current, 0)
        self.assertIsNone(self.manager.get_task(TID))

    async def test_duplicate_submission_keeps_one_cancellable_task(self):
        async def run(options): await asyncio.Event().wait()
        fixture = types.SimpleNamespace(run_recon_job=run)
        with patch.dict(sys.modules, {'clients': types.ModuleType('clients'), 'clients.job_runner': fixture}):
            first = self.routes.submit_recon_job(self.manager, {'task_id': TID, 'type': 'icp'})
            second = self.routes.submit_recon_job(self.manager, {'task_id': TID, 'type': 'icp'})
        self.assertIs(first, second)
        await self.manager.cancel_task(TID)
        await asyncio.sleep(0)
        self.assertEqual(self.routes.background_tasks, set())

    async def test_stop_cancels_a_job_waiting_for_the_semaphore(self):
        semaphore = self.manager.get_semaphore('recon_task', 1, dynamic=True)
        await semaphore.acquire()
        async def job():
            async with semaphore:
                self.fail('A cancelled queued job must not run')
        task = asyncio.create_task(job())
        self.manager.add_task(TID, task)
        await asyncio.sleep(0)
        response = await self.client.post('/stop', json={'task_id': TID})
        self.assertEqual(response.status, 200)
        self.assertTrue(task.cancelled())
        self.assertEqual(semaphore._current, 1)
        await semaphore.release()


if __name__ == '__main__':
    unittest.main()
