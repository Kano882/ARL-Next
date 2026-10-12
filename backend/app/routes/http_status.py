"""HTTP 状态码多选参数，仅用于 HTTP 资产查询。"""
import re
from flask import has_request_context, request
from flask_restx import fields
from . import ARLResource


def parse_http_status_codes(value):
    """解析逗号分隔的状态码；无效输入必须报错，避免扩大查询范围。"""
    if not isinstance(value, str) or not value.strip() or len(value) > 2000:
        raise ValueError("请提供逗号分隔的 HTTP 状态码，例如 200,301,403")
    tokens = value.split(',')
    if len(tokens) > 500:
        raise ValueError("一次最多提供 500 个状态码")
    codes = []
    for token in tokens:
        token = token.strip()
        if not re.fullmatch(r'[1-5][0-9]{2}', token):
            raise ValueError("HTTP 状态码必须是 100 到 599 的整数")
        codes.append(int(token))
    return sorted(set(codes))


class HttpStatusCodes(fields.String):
    def format(self, value, name=None, op=None):
        if name and has_request_context() and len(request.args.getlist(name)) > 1:
            raise ValueError("请用一个逗号分隔参数提交多个状态码")
        return parse_http_status_codes(value)


class HttpStatusResource(ARLResource):
    def build_db_query(self, args):
        # 显式限制字段，不支持任意字段或 MongoDB 操作符输入。
        filters = {key: args.get(key) for key in ('status__in', 'status_code__in')}
        query = super().build_db_query({key: value for key, value in args.items()
                                       if key not in filters})
        for key, codes in filters.items():
            if codes is None:
                continue
            field = key.removesuffix('__in')
            existing = query.get(field)
            if field in query:
                # 同时传旧单值条件时取交集，结果不依赖参数顺序。
                condition = existing.copy() if isinstance(existing, dict) else {'$eq': existing}
                condition['$in'] = codes
                query[field] = condition
            else:
                query[field] = {'$in': codes}
        return query
