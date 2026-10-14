"""原路由处理器、真实 Flask 测试客户端及 mongomock 聚合验证。"""
import ast
import copy
import functools
import importlib.util
import logging
from pathlib import Path
import types
import unittest
from unittest.mock import patch

from flask import Flask, request
from flask_restx import Api, Namespace, Resource, fields, reqparse
import mongomock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('task_statistics_fixture', ROOT / 'app/utils/task_statistics.py')
statistics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(statistics)


def load_function(path, name, env):
    tree = ast.parse((ROOT / path).read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(node)], type_ignores=[])), str(path), 'exec'), env)
    return env[name]


def load_field_model(path, name):
    env = {'fields': fields}
    tree = ast.parse((ROOT / path).read_text())
    node = next(n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == name for target in n.targets))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(node)], type_ignores=[])), str(path), 'exec'), env)
    return env[name]


class AggregateCollection:
    def __init__(self, collection):
        self.collection = collection
        self.calls = []
    def aggregate(self, pipeline):
        self.calls.append(pipeline)
        return self.collection.aggregate(pipeline)
    def __getattr__(self, name):
        if name in ('find', 'find_one', 'update_one', 'update_many'):
            raise AssertionError('Statistics must not load or mutate task records')
        return getattr(self.collection, name)


class StatisticsFixture(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().arl
        statuses = ['waiting', 'running', 'port_scan', 'site_identify', 'done', 'done', 'error', 'stop', None]
        for collection in ('task', 'icp_task'):
            self.db[collection].insert_many([{'status': status, 'name': 'fixture'} for status in statuses])
        self.collections = {name: AggregateCollection(self.db[name]) for name in ('task', 'icp_task')}


class StatisticsTests(StatisticsFixture):
    def test_scan_counts_match_existing_stage_and_waiting_semantics(self):
        result = statistics.get_task_statistics(self.collections['task'], include_stage_statuses=True)
        self.assertEqual(result, {'total': 9, 'running': 4, 'waiting': 1, 'done': 2,
                                  'error': 1, 'stop': 1, 'active': 5, 'abnormal': 2})
        expected = self.db.task.count_documents({'status': {'$nin': ['done', 'error', 'stop', 'waiting']}})
        self.assertEqual(result['running'], expected)
        self.assertEqual(len(self.collections['task'].calls), 1)

    def test_enterprise_active_counts_remain_literal_running_and_waiting(self):
        result = statistics.get_task_statistics(self.collections['icp_task'])
        self.assertEqual(result['total'], 9)
        self.assertEqual(result['running'], 1)
        self.assertEqual(result['active'], 2)

    def test_empty_collection_provides_all_zero_fields(self):
        self.assertEqual(set(statistics.get_task_statistics(self.db.empty).values()), {0})

    def test_missing_status_remains_a_scan_stage(self):
        self.db.empty.insert_one({'name': 'legacy'})
        self.assertEqual(statistics.get_task_statistics(self.db.empty, True)['running'], 1)


class HTTPTests(StatisticsFixture):
    def setUp(self):
        super().setUp()
        self.app = Flask(__name__)
        self.api = Api(self.app, prefix='/api')
        self.last_args = None
        log = logging.getLogger(__name__)
        log.addHandler(logging.NullHandler())

        auth_env = {'functools': functools, 'Config': types.SimpleNamespace(AUTH=True),
                    'user_login_header': lambda: request.headers.get('Token') == 'fixture-token'}
        auth = load_function('app/utils/user.py', 'auth', auth_env)
        outer = self

        class Base(Resource):
            def build_db_query(self, args):
                return {key: value for key, value in args.items()
                        if key not in ('page', 'size', 'order') and value is not None and value != ''}
            def build_data(self, args, collection):
                outer.last_args = dict(args)
                query = self.build_db_query(args)
                return {'code': 200, 'items': [], 'total': outer.db[collection].count_documents(query)}

        def parser_factory(model, location='args'):
            parser = reqparse.RequestParser()
            for key, field in model.items():
                parser.add_argument(key, type=field.format, required=field.required, location=location)
            return parser

        base_fields = load_field_model('app/routes/__init__.py', 'base_query_fields')
        task_model = load_field_model('app/routes/task.py', 'base_search_task_fields')
        icp_model = load_field_model('app/routes/icp.py', 'base_search_icp_task_fields')
        task_model.update(base_fields)
        icp_model.update(base_fields)
        errors = types.SimpleNamespace(Success={'code': 200}, Error={'code': 500})
        build_ret = lambda error, data: dict(error, data=data)
        utils = types.SimpleNamespace(conn_db=self.collections.__getitem__, build_ret=build_ret)
        env = {'ARLResource': Base, 'auth': auth, 'utils': utils, 'logger': log,
               'conn_db': self.collections.__getitem__, 'build_ret': build_ret, 'ErrorMsg': errors,
               'get_arl_parser': parser_factory, 'search_task_fields': task_model, 'search_icp_task_fields': icp_model,
               'get_task_statistics': statistics.get_task_statistics, 'attach_task_statistics': statistics.attach_task_statistics}
        for path, namespace, names in (
            ('app/routes/task.py', Namespace('task'), ['ARLTask', 'TaskStatistics']),
            ('app/routes/icp.py', Namespace('icp'), ['IcpTask', 'IcpTaskStatistics']),
        ):
            env['ns'] = namespace
            tree = ast.parse((ROOT / path).read_text())
            for cls in tree.body:
                if isinstance(cls, ast.ClassDef) and cls.name in names:
                    cls = copy.deepcopy(cls)
                    cls.body = [node for node in cls.body if not isinstance(node, ast.FunctionDef) or node.name in ('get', 'build_db_query')]
                    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(path), 'exec'), env)
            self.api.add_namespace(namespace)
        self.client = self.app.test_client()
        self.headers = {'Token': 'fixture-token'}

    def test_statistics_endpoints_are_authenticated(self):
        for path in ('/api/task/statistics', '/api/icp/task/statistics'):
            self.assertEqual(self.client.get(path).get_json()['code'], 401)
        self.assertEqual(sum(len(col.calls) for col in self.collections.values()), 0)

    def test_statistics_only_paths_run_one_aggregate_and_do_not_load_lists(self):
        for path, name in (('/api/task/statistics', 'task'), ('/api/icp/task/statistics', 'icp_task')):
            result = self.client.get(path, headers=self.headers).get_json()
            self.assertEqual(result['code'], 200)
            self.assertEqual(result['data']['total'], 9)
            self.assertEqual(len(self.collections[name].calls), 1)
        self.assertIsNone(self.last_args)

    def test_list_opt_in_returns_global_statistics_beside_filtered_total(self):
        for path, name in (('/api/task/', 'task'), ('/api/icp/task', 'icp_task')):
            result = self.client.get(path, query_string={'include_statistics': 1, 'status': 'done'}, headers=self.headers).get_json()
            self.assertEqual(result['code'], 200)
            self.assertEqual(result['total'], 2)
            self.assertEqual(result['statistics']['total'], 9)
            self.assertNotIn('include_statistics', self.last_args)
            self.assertEqual(len(self.collections[name].calls), 1)

    def test_legacy_list_requests_do_not_aggregate(self):
        for path in ('/api/task/', '/api/icp/task'):
            result = self.client.get(path, headers=self.headers).get_json()
            self.assertEqual(result['code'], 200)
            self.assertNotIn('statistics', result)
        self.assertEqual(sum(len(col.calls) for col in self.collections.values()), 0)

    def test_aggregation_failure_preserves_successful_list_response(self):
        with patch.object(self.collections['task'], 'aggregate', side_effect=RuntimeError('fixture')), self.assertLogs(__name__, level='ERROR'):
            result = self.client.get('/api/task/?include_statistics=1', headers=self.headers).get_json()
        self.assertEqual(result['code'], 200)
        self.assertEqual(result['total'], 9)
        self.assertTrue(result['statistics_error'])
        self.assertNotIn('statistics', result)

    def test_statistics_only_failure_returns_business_error(self):
        with patch.object(self.collections['task'], 'aggregate', side_effect=RuntimeError('fixture')), self.assertLogs(__name__, level='ERROR'):
            result = self.client.get('/api/task/statistics', headers=self.headers).get_json()
        self.assertEqual(result['code'], 500)

    def test_invalid_opt_in_flag_is_rejected_by_parser(self):
        response = self.client.get('/api/task/?include_statistics=invalid', headers=self.headers)
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
