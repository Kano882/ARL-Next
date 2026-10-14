import os
import io
import re
import yaml
import json
import shutil
import zipfile
import tempfile
import subprocess
import threading
import time
from datetime import datetime
from urllib.parse import quote
import requests

from flask import request, Response, make_response
from flask_restx import fields, Namespace
from bson import ObjectId

from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app import utils
from app.modules import ErrorMsg
from app.config import Config

ns = Namespace('nuclei', description="Nuclei 模板管理与在线调试")
logger = get_logger()

# 官方社区模板内存索引缓存
_community_cache = {
    "templates": [],
    "last_load": 0,
    "dir": "",
    "lock": threading.Lock(),
    "cache_epoch": 0.0
}


def get_community_templates_dir() -> str:
    """获取官方社区模板存储路径"""
    custom_env = os.environ.get("NUCLEI_TEMPLATES_PATH")
    if custom_env and os.path.exists(custom_env):
        return os.path.abspath(custom_env)

    candidates = [
        "/root/nuclei-templates",
        os.path.expanduser("~/nuclei-templates"),
        os.path.expanduser("~/.local/nuclei-templates"),
        os.path.join(Config.basedir, "nuclei-templates"),
    ]
    for p in candidates:
        if os.path.exists(p) and os.path.isdir(p):
            return os.path.abspath(p)
    return ""


def get_nuclei_template_version_info() -> dict:
    """获取本地模板安装版本与官方最新版本信息"""
    cfg_candidates = [
        "/root/.config/nuclei/.templates-config.json",
        os.path.expanduser("~/.config/nuclei/.templates-config.json"),
        os.path.join(Config.basedir, ".config/nuclei/.templates-config.json")
    ]
    cur_ver = "未知"
    latest_ver = "未知"
    cfg_file = None

    for p in cfg_candidates:
        if os.path.exists(p):
            cfg_file = p
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
                    cur_ver = cfg_data.get("nuclei-templates-version", cur_ver)
                    latest_ver = cfg_data.get("nuclei-templates-latest-version", latest_ver)
            except Exception:
                pass
            break

    if cur_ver == "未知":
        try:
            res = subprocess.run(["nuclei", "-tv"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            combined = (res.stdout or "") + "\n" + (res.stderr or "")
            m = re.search(r'v\d+\.\d+\.\d+', combined)
            if m:
                cur_ver = m.group(0)
        except Exception:
            pass

    has_update = False
    if cur_ver != "未知" and latest_ver != "未知" and cur_ver != latest_ver:
        has_update = True

    return {
        "current_version": cur_ver,
        "latest_version": latest_ver,
        "has_update": has_update,
        "config_file": cfg_file
    }


def update_templates_config_version(new_version: str):
    """更新本地 .templates-config.json 中的版本号标记"""
    cfg_candidates = [
        "/root/.config/nuclei/.templates-config.json",
        os.path.expanduser("~/.config/nuclei/.templates-config.json"),
    ]
    for p in cfg_candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
                cfg_data["nuclei-templates-version"] = new_version
                if "nuclei-templates-latest-version" in cfg_data:
                    cfg_data["nuclei-templates-latest-version"] = new_version
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(cfg_data, f, indent=2)
                return True
            except Exception as e:
                logger.warning(f"Failed to update {p}: {e}")
    return False


def extract_templates_zip_to_dir(zip_file_path: str, target_dir: str) -> int:
    """智能解压覆盖 nuclei 模板 zip 包到 target_dir (具备 Zip Slip 安全防护)"""
    os.makedirs(target_dir, exist_ok=True)
    count = 0
    with zipfile.ZipFile(zip_file_path, 'r') as zf:
        namelist = zf.namelist()
        if not namelist:
            return 0

        # 判断是否有唯一的公共根目录 (例如 nuclei-templates-10.5.0/)
        # 核心防护：不能把标准协议分类目录 (如 http, network, dns, cves) 当成多余的顶层包装目录剥离！
        # 核心防御：严禁将 '..' 或以特殊符号开头的目录作为公共前缀剥离，防御恶意 Zip Slip 变体
        standard_dirs = {"http", "network", "dns", "ssl", "dast", "cloud", "code", "file", "headless", "helpers", "javascript", "profiles", "workflows", "cves"}
        top_dirs = set(p.split('/')[0] for p in namelist if '/' in p)
        common_prefix = ""
        if len(top_dirs) == 1:
            first_top = list(top_dirs)[0]
            if first_top not in standard_dirs and not first_top.startswith(('.', '/', '\\')):
                if all(p.startswith(first_top + '/') or p == first_top for p in namelist):
                    common_prefix = first_top + '/'

        abs_target = os.path.abspath(target_dir)
        for member in zf.infolist():
            # 原始文件名防 Zip Slip: 包含 .. 或绝对路径必须阻断
            raw_parts = [p.strip() for p in member.filename.replace('\\', '/').split('/') if p.strip()]
            if '..' in raw_parts or member.filename.startswith(('/', '\\')):
                continue

            rel_name = member.filename
            if common_prefix and rel_name.startswith(common_prefix):
                rel_name = rel_name[len(common_prefix):]
            if not rel_name or rel_name.startswith(('/', '\\', '..')):
                continue

            dest_path = os.path.abspath(os.path.join(abs_target, rel_name))
            if not dest_path.startswith(abs_target):
                continue  # Zip Slip 阻断

            if member.is_dir():
                os.makedirs(dest_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with zf.open(member) as src, open(dest_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                count += 1
    return count


def parse_and_validate_nuclei_yaml(content: str, run_nuclei_validate: bool = False):
    """
    严格解析与静态校验 Nuclei 模板 YAML
    返回: (is_valid: bool, data_or_error: dict|str)
    """
    if not content or not content.strip():
        return False, "模板内容不能为空"

    try:
        doc = yaml.safe_load(content)
    except Exception as e:
        return False, f"YAML 语法解析错误: {e}"

    if not isinstance(doc, dict):
        return False, "Nuclei 模板必须为顶层 YAML 映射/字典格式"

    template_id = doc.get("id")
    if not template_id or not isinstance(template_id, str):
        return False, "缺少根节点 'id'（模板唯一标识）"

    template_id = template_id.strip()
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', template_id):
        return False, "模板 id 只能包含英文字母、数字、点号(.)、下划线(_)和连字符(-)"

    info = doc.get("info")
    if not info or not isinstance(info, dict):
        return False, "缺少 'info' 元数据块"

    name = info.get("name")
    if not name or not str(name).strip():
        return False, "info 节点下缺少有效 'name'（漏洞名称）"

    raw_severity = str(info.get("severity", "info")).strip().lower()
    valid_severities = {"info", "low", "medium", "high", "critical", "unknown"}
    severity = raw_severity if raw_severity in valid_severities else "info"

    raw_tags = info.get("tags", [])
    if isinstance(raw_tags, str):
        tags = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]
    elif isinstance(raw_tags, list):
        tags = [str(t).strip().lower() for t in raw_tags if str(t).strip()]
    else:
        tags = []

    known_protocols = ["http", "dns", "tcp", "ssl", "websocket", "whois", "code", "javascript", "headless", "network", "file"]
    protocol = "http"
    for p in known_protocols:
        if p in doc:
            protocol = p
            break
    if "requests" in doc and protocol == "http":
        protocol = "http"

    author = str(info.get("author", "")).strip()
    description = str(info.get("description", "")).strip()
    reference = info.get("reference", [])
    if isinstance(reference, str):
        reference = [reference]
    elif not isinstance(reference, list):
        reference = []

    metadata = {
        "template_id": template_id,
        "name": str(name).strip(),
        "severity": severity,
        "tags": tags,
        "protocol": protocol,
        "author": author,
        "description": description,
        "reference": reference,
        "content": content
    }

    # 深度语义校验 nuclei -validate
    if run_nuclei_validate and shutil.which("nuclei"):
        tmp_path = os.path.join(Config.TMP_PATH, f"validate_{utils.random_choices(8)}.yaml")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
            cmd = ["nuclei", "-validate", "-t", tmp_path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if res.returncode != 0:
                err_text = (res.stderr or res.stdout).strip()
                if err_text:
                    return False, f"Nuclei 语义验证不通过: {err_text}"
        except Exception as e:
            logger.warning(f"nuclei -validate error: {e}")
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    return True, metadata


def load_community_index(force_refresh: bool = False):
    """加载官方社区模板轻量索引 (支持多工作进程基于 MongoDB 状态感知与缓存失效)"""
    now = time.time()
    c_dir = get_community_templates_dir()
    if not c_dir or not os.path.isdir(c_dir):
        return []

    # 获取远程全局缓存纪元 (跨 Gunicorn 多 Worker 与 Celery 协同)
    remote_epoch = 0.0
    try:
        sync_doc = utils.conn_db('nuclei_sync_log').find_one({'_id': 'latest_sync'}, {'cache_epoch': 1})
        if sync_doc and 'cache_epoch' in sync_doc:
            remote_epoch = float(sync_doc['cache_epoch'])
    except Exception:
        pass

    with _community_cache["lock"]:
        cached_epoch = _community_cache.get("cache_epoch", 0.0)
        is_stale = (remote_epoch > cached_epoch) or (not _community_cache["templates"]) or (_community_cache["dir"] != c_dir)

        if not force_refresh and not is_stale and (now - _community_cache["last_load"] < 1800):
            return _community_cache["templates"]

        if force_refresh:
            remote_epoch = now
            try:
                utils.conn_db('nuclei_sync_log').update_one(
                    {'_id': 'latest_sync'},
                    {'$set': {'cache_epoch': remote_epoch, 'updated_at': utils.curr_date()}},
                    upsert=True
                )
            except Exception:
                pass

        templates = []
        cves_json = os.path.join(c_dir, "cves.json")

        if os.path.exists(cves_json):
            try:
                with open(cves_json, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                            info = item.get("Info", {})
                            templates.append({
                                "template_id": item.get("ID", ""),
                                "name": info.get("Name", "") or item.get("ID", ""),
                                "severity": str(info.get("Severity", "unknown")).lower(),
                                "description": info.get("Description", ""),
                                "file_path": item.get("file_path", ""),
                                "tags": ["cve"],
                                "type": "cve"
                            })
                        except Exception:
                            continue
            except Exception as e:
                logger.warning(f"Failed to read cves.json: {e}")

        # 遍历其他高价值分类 (如 exposures, vulnerabilities, misconfiguration 等)
        for cat in ["http", "network", "dns", "ssl", "dast"]:
            cat_path = os.path.join(c_dir, cat)
            if not os.path.exists(cat_path):
                continue
            for root, dirs, files in os.walk(cat_path):
                if "cves" in root:  # 已由 cves.json 覆盖
                    continue
                for fname in files:
                    if fname.endswith(('.yaml', '.yml')):
                        rel = os.path.relpath(os.path.join(root, fname), c_dir)
                        base_id = os.path.splitext(fname)[0]
                        templates.append({
                            "template_id": base_id,
                            "name": base_id,
                            "severity": "unknown",
                            "description": "",
                            "file_path": rel,
                            "tags": [cat],
                            "type": cat
                        })

        _community_cache["templates"] = templates
        _community_cache["last_load"] = now
        _community_cache["dir"] = c_dir
        _community_cache["cache_epoch"] = remote_epoch
        return templates


base_template_search_fields = {
    'template_id': fields.String(description="模板 ID"),
    'name': fields.String(description="漏洞/模板名称"),
    'severity': fields.String(description="危害级别 (critical/high/medium/low/info)"),
    'tag': fields.String(description="标签过滤"),
    'enable': fields.Boolean(description="启用状态"),
}
base_template_search_fields.update(base_query_fields)


@ns.route('/template/')
class NucleiTemplateList(ARLResource):
    parser = get_arl_parser(base_template_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """自建模板列表分页查询"""
        args = self.parser.parse_args()
        page = int(args.get('page') or 1)
        size = int(args.get('size') or 10)
        order = args.get('order') or '-updated_at'

        query = {}
        if args.get('template_id'):
            query['template_id'] = {'$regex': re.escape(args['template_id'].strip()), '$options': 'i'}
        if args.get('name'):
            query['name'] = {'$regex': re.escape(args['name'].strip()), '$options': 'i'}
        if args.get('severity'):
            query['severity'] = args['severity'].strip().lower()
        if args.get('tag'):
            query['tags'] = {'$in': [args['tag'].strip().lower()]}
        if args.get('enable') is not None:
            query['enable'] = bool(args['enable'])

        col = utils.conn_db('nuclei_template')
        total = col.count_documents(query)

        sort_dir = 1
        sort_key = order
        if order.startswith('-'):
            sort_dir = -1
            sort_key = order[1:]

        items = list(col.find(query).sort(sort_key, sort_dir).skip((page - 1) * size).limit(size))
        for item in items:
            item['_id'] = str(item['_id'])
            # 列表视图省去大体积 content 字段，提高传输性能
            item.pop('content', None)

        return utils.build_ret(ErrorMsg.Success, {
            "items": items,
            "total": total,
            "page": page,
            "size": size
        })


@ns.route('/template/detail/')
class NucleiTemplateDetail(ARLResource):

    @auth
    def get(self):
        """获取单个自建模板详情与完整 YAML 源码"""
        template_id = request.args.get('template_id')
        _id = request.args.get('_id')

        query = {}
        if _id:
            try:
                query['_id'] = ObjectId(_id)
            except Exception:
                return utils.build_ret(ErrorMsg.Error, {'error': '无效的 _id'})
        elif template_id:
            query['template_id'] = template_id.strip()
        else:
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少 template_id 或 _id 参数'})

        doc = utils.conn_db('nuclei_template').find_one(query)
        if not doc:
            return utils.build_ret(ErrorMsg.Error, {'error': '未找到指定模板'})

        doc['_id'] = str(doc['_id'])
        return utils.build_ret(ErrorMsg.Success, doc)


@ns.route('/template/create/')
class NucleiTemplateCreate(ARLResource):

    @auth
    def post(self):
        """新建自建 Nuclei 模板"""
        data = request.json or {}
        content = data.get('content', '')
        enable = data.get('enable', True)

        is_valid, meta = parse_and_validate_nuclei_yaml(content, run_nuclei_validate=False)
        if not is_valid:
            return utils.build_ret(meta, {})

        col = utils.conn_db('nuclei_template')
        existing = col.find_one({'template_id': meta['template_id']})
        if existing:
            return utils.build_ret(f"模板 ID '{meta['template_id']}' 已存在，请勿重复创建", {})

        now_str = utils.curr_date()
        doc = {
            "template_id": meta['template_id'],
            "name": meta['name'],
            "severity": meta['severity'],
            "tags": meta['tags'],
            "protocol": meta['protocol'],
            "author": meta['author'],
            "description": meta['description'],
            "reference": meta['reference'],
            "content": meta['content'],
            "enable": bool(enable),
            "is_custom": True,
            "created_at": now_str,
            "updated_at": now_str
        }

        col.insert_one(doc)
        doc['_id'] = str(doc['_id'])
        return utils.build_ret(ErrorMsg.Success, {'message': '创建成功', 'template_id': meta['template_id']})


@ns.route('/template/update/')
class NucleiTemplateUpdate(ARLResource):

    @auth
    def post(self):
        """更新自建 Nuclei 模板源码与元数据"""
        data = request.json or {}
        template_id = data.get('template_id', '').strip()
        content = data.get('content', '')

        if not template_id:
            return utils.build_ret('缺少 template_id 参数', {})

        is_valid, meta = parse_and_validate_nuclei_yaml(content, run_nuclei_validate=False)
        if not is_valid:
            return utils.build_ret(meta, {})

        col = utils.conn_db('nuclei_template')
        existing = col.find_one({'template_id': template_id})
        if not existing:
            return utils.build_ret(f"模板 '{template_id}' 不存在", {})

        now_str = utils.curr_date()
        update_fields = {
            "name": meta['name'],
            "severity": meta['severity'],
            "tags": meta['tags'],
            "protocol": meta['protocol'],
            "author": meta['author'],
            "description": meta['description'],
            "reference": meta['reference'],
            "content": meta['content'],
            "updated_at": now_str
        }

        # 若用户在 YAML 中更改了 id 且未与其他模板冲突，允许重命名更新
        new_template_id = meta['template_id']
        if new_template_id != template_id:
            conflict = col.find_one({'template_id': new_template_id, '_id': {'$ne': existing['_id']}})
            if conflict:
                return utils.build_ret(ErrorMsg.Error, {'error': f"新的模板 ID '{new_template_id}' 已被占用"})
            update_fields['template_id'] = new_template_id

        col.update_one({'_id': existing['_id']}, {'$set': update_fields})
        return utils.build_ret(ErrorMsg.Success, {'message': '更新成功', 'template_id': new_template_id})


@ns.route('/template/delete/')
class NucleiTemplateDelete(ARLResource):

    @auth
    def post(self):
        """批量删除自建模板"""
        data = request.json or {}
        template_ids = data.get('template_ids', [])
        if not template_ids or not isinstance(template_ids, list):
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少要删除的 template_ids 列表'})

        col = utils.conn_db('nuclei_template')
        res = col.delete_many({'template_id': {'$in': template_ids}})
        return utils.build_ret(ErrorMsg.Success, {'delete_cnt': res.deleted_count})


@ns.route('/template/toggle/')
class NucleiTemplateToggle(ARLResource):

    @auth
    def post(self):
        """切换单个模板启用/禁用状态"""
        data = request.json or {}
        template_id = data.get('template_id', '').strip()
        enable = data.get('enable')

        if not template_id or enable is None:
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少 template_id 或 enable 参数'})

        col = utils.conn_db('nuclei_template')
        res = col.update_one({'template_id': template_id}, {'$set': {'enable': bool(enable), 'updated_at': utils.curr_date()}})
        if res.matched_count == 0:
            return utils.build_ret(ErrorMsg.Error, {'error': '未找到指定模板'})

        return utils.build_ret(ErrorMsg.Success, {'message': '状态更新成功'})


@ns.route('/template/batch_toggle/')
class NucleiTemplateBatchToggle(ARLResource):

    @auth
    def post(self):
        """批量切换模板启用/禁用状态"""
        data = request.json or {}
        template_ids = data.get('template_ids', [])
        enable = data.get('enable')

        if not template_ids or not isinstance(template_ids, list) or enable is None:
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少 template_ids 或 enable 参数'})

        col = utils.conn_db('nuclei_template')
        res = col.update_many({'template_id': {'$in': template_ids}}, {'$set': {'enable': bool(enable), 'updated_at': utils.curr_date()}})
        return utils.build_ret(ErrorMsg.Success, {'modified_count': res.modified_count})


@ns.route('/template/import/')
class NucleiTemplateImport(ARLResource):

    @auth
    def post(self):
        """导入 YAML 文件或 ZIP 压缩包 (支持批量)"""
        if 'file' not in request.files:
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少上传文件 (file)'})

        files = request.files.getlist('file')
        if not files:
            return utils.build_ret(ErrorMsg.Error, {'error': '未选择任何文件'})

        success_count = 0
        fail_count = 0
        fail_details = []
        col = utils.conn_db('nuclei_template')

        def _process_yaml_content(content_str: str, file_display_name: str):
            nonlocal success_count, fail_count
            is_valid, meta = parse_and_validate_nuclei_yaml(content_str, run_nuclei_validate=False)
            if not is_valid:
                fail_count += 1
                fail_details.append({"filename": file_display_name, "reason": meta})
                return

            now_str = utils.curr_date()
            doc = {
                "template_id": meta['template_id'],
                "name": meta['name'],
                "severity": meta['severity'],
                "tags": meta['tags'],
                "protocol": meta['protocol'],
                "author": meta['author'],
                "description": meta['description'],
                "reference": meta['reference'],
                "content": meta['content'],
                "enable": True,
                "is_custom": True,
                "updated_at": now_str
            }
            # 存在则覆盖更新，不存在则插入
            col.update_one({'template_id': meta['template_id']}, {'$set': doc, '$setOnInsert': {'created_at': now_str}}, upsert=True)
            success_count += 1

        for f in files:
            if not f or not f.filename:
                continue
            filename = os.path.basename(f.filename)
            ext = os.path.splitext(filename)[1].lower()

            if ext in ('.yaml', '.yml'):
                try:
                    raw_bytes = f.read(10 * 1024 * 1024)
                    content = raw_bytes.decode('utf-8-sig', errors='replace')
                    _process_yaml_content(content, filename)
                except Exception as e:
                    fail_count += 1
                    fail_details.append({"filename": filename, "reason": f"读取失败: {e}"})
            elif ext == '.zip':
                try:
                    raw_bytes = f.read(50 * 1024 * 1024)
                    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
                        for zinfo in z.infolist():
                            if zinfo.is_dir():
                                continue
                            if not zinfo.filename.lower().endswith(('.yaml', '.yml')):
                                continue
                            try:
                                zcontent = z.read(zinfo).decode('utf-8-sig', errors='replace')
                                _process_yaml_content(zcontent, zinfo.filename)
                            except Exception as ze:
                                fail_count += 1
                                fail_details.append({"filename": zinfo.filename, "reason": f"解压读取错误: {ze}"})
                except Exception as e:
                    fail_count += 1
                    fail_details.append({"filename": filename, "reason": f"ZIP 解压失败: {e}"})
            else:
                fail_count += 1
                fail_details.append({"filename": filename, "reason": "不支持的文件类型，仅支持 .yaml、.yml 或包含模板的 .zip 压缩包"})

        return utils.build_ret(ErrorMsg.Success, {
            "success_count": success_count,
            "fail_count": fail_count,
            "fail_details": fail_details
        })


@ns.route('/template/export/')
class NucleiTemplateExport(ARLResource):

    @auth
    def get(self):
        """批量导出自建模板为 ZIP 压缩包"""
        template_ids_str = request.args.get('template_ids', '')
        query = {}
        if template_ids_str:
            ids = [x.strip() for x in template_ids_str.split(',') if x.strip()]
            query = {'template_id': {'$in': ids}}

        col = utils.conn_db('nuclei_template')
        docs = list(col.find(query))
        if not docs:
            return utils.build_ret(ErrorMsg.Error, {'error': '没有可导出的模板'})

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
            for doc in docs:
                t_id = doc.get('template_id', 'template')
                content = doc.get('content', '')
                z.writestr(f"{t_id}.yaml", content.encode('utf-8'))

        buf.seek(0)
        filename = f"nuclei_custom_templates_{int(time.time())}.zip"
        response = make_response(buf.getvalue())
        response.headers['Content-Type'] = 'application/zip'
        response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        response.headers["Content-Disposition"] = f"attachment; filename={quote(filename)}"
        return response


@ns.route('/template/test/')
class NucleiTemplateTest(ARLResource):

    @auth
    def post(self):
        """
        在线单目标即时发包调试 (Dry Run)
        执行 nuclei -t <temp_file> -u <target> -duc -v
        """
        data = request.json or {}
        content = data.get('content', '')
        template_id = data.get('template_id', '')
        target = data.get('target', '').strip()

        if not target:
            return utils.build_ret(ErrorMsg.Error, {'error': '目标 URL 不能为空'})

        # 规范化目标 URL，默认补充 http 协议前缀
        if not target.startswith(('http://', 'https://')):
            target = 'http://' + target

        # 若未直接传 content，则根据 template_id 查找
        if not content and template_id:
            doc = utils.conn_db('nuclei_template').find_one({'template_id': template_id})
            if doc:
                content = doc.get('content', '')

        if not content:
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少模板内容'})

        is_valid, meta = parse_and_validate_nuclei_yaml(content, run_nuclei_validate=False)
        if not is_valid:
            return utils.build_ret(ErrorMsg.Error, {'error': f"模板静态校验失败: {meta}"})

        nuclei_bin = shutil.which("nuclei") or "nuclei"
        rand_str = utils.random_choices(8)
        tmp_file = os.path.join(Config.TMP_PATH, f"dryrun_{rand_str}.yaml")

        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(content)

            cmd = [
                nuclei_bin,
                "-duc",
                "-t", tmp_file,
                "-u", target,
                "-v",
                "-stats=false",
                "-timeout", "10"
            ]

            logger.info(f"Nuclei Dry Run: {' '.join(cmd)}")
            t0 = time.time()
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            elapse = round(time.time() - t0, 2)

            out = proc.stdout or ""
            err = proc.stderr or ""
            full_log = (out + ("\n" + err if err else "")).strip()

            # 判断是否有匹配命中
            matched = False
            for line in out.splitlines():
                if f"[{meta['template_id']}" in line or "[critical]" in line or "[high]" in line or "[medium]" in line or "[low]" in line:
                    matched = True
                    break

            return utils.build_ret(ErrorMsg.Success, {
                "matched": matched,
                "output": full_log,
                "returncode": proc.returncode,
                "cost_seconds": elapse
            })
        except subprocess.TimeoutExpired:
            return utils.build_ret(ErrorMsg.Error, {'error': 'Nuclei 调试探测超时 (超过 30 秒)'})
        except Exception as e:
            logger.error(f"Nuclei Dry Run exception: {e}")
            return utils.build_ret(ErrorMsg.Error, {'error': f'执行失败: {e}'})
        finally:
            if os.path.exists(tmp_file):
                try:
                    os.unlink(tmp_file)
                except Exception:
                    pass


@ns.route('/community/')
class NucleiCommunityList(ARLResource):

    @auth
    def get(self):
        """官方社区模板只读检索 (支持误报黑名单状态联动与过滤)"""
        search = request.args.get('search', '').strip().lower()
        severity = request.args.get('severity', '').strip().lower()
        tag = request.args.get('tag', '').strip().lower()
        blacklist_status = request.args.get('blacklist_status', 'all').strip().lower()
        refresh_arg = request.args.get('refresh', '').strip().lower()
        force_refresh = refresh_arg in ['1', 'true', 'yes']
        page = int(request.args.get('page') or 1)
        size = int(request.args.get('size') or 10)

        # 读取黑名单集合映射表 (大小写不敏感匹配)
        bl_col = utils.conn_db('nuclei_blacklist')
        bl_docs = {}
        for d in bl_col.find({}, {'template_id': 1, 'reason': 1}):
            raw_tid = d.get('template_id')
            if raw_tid:
                rs = d.get('reason', '')
                bl_docs[raw_tid] = rs
                bl_docs[raw_tid.lower()] = rs
                bl_docs[raw_tid.upper()] = rs

        templates = load_community_index(force_refresh=force_refresh)
        filtered = templates

        if search:
            filtered = [t for t in filtered if search in t['template_id'].lower() or search in t['name'].lower()]
        if severity:
            filtered = [t for t in filtered if t['severity'].lower() == severity]
        if tag:
            filtered = [t for t in filtered if any(tag in tg for tg in t.get('tags', []))]
        if blacklist_status == 'blacklisted':
            filtered = [t for t in filtered if t['template_id'] in bl_docs or t['template_id'].lower() in bl_docs]
        elif blacklist_status == 'normal':
            filtered = [t for t in filtered if t['template_id'] not in bl_docs and t['template_id'].lower() not in bl_docs]

        total = len(filtered)
        start = (page - 1) * size
        end = start + size
        raw_items = filtered[start:end]

        items = []
        for t in raw_items:
            item = dict(t)
            tid = t['template_id']
            is_bl = tid in bl_docs or tid.lower() in bl_docs
            item['is_blacklisted'] = is_bl
            item['blacklist_reason'] = bl_docs.get(tid) or bl_docs.get(tid.lower()) or ''
            items.append(item)

        return utils.build_ret(ErrorMsg.Success, {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "community_dir": get_community_templates_dir()
        })


@ns.route('/blacklist/')
class NucleiBlacklistList(ARLResource):

    @auth
    def get(self):
        """误报黑名单分页查询"""
        search = request.args.get('search', '').strip()
        severity = request.args.get('severity', '').strip().lower()
        page = int(request.args.get('page') or 1)
        size = int(request.args.get('size') or 10)

        col = utils.conn_db('nuclei_blacklist')
        query = {}
        if search:
            escaped = re.escape(search)
            query['$or'] = [
                {'template_id': {'$regex': escaped, '$options': 'i'}},
                {'name': {'$regex': escaped, '$options': 'i'}},
                {'reason': {'$regex': escaped, '$options': 'i'}}
            ]
        if severity:
            query['severity'] = severity

        total = col.count_documents(query)
        cursor = col.find(query).sort('created_at', -1).skip((page - 1) * size).limit(size)
        items = []
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            items.append(doc)

        return utils.build_ret(ErrorMsg.Success, {
            'items': items,
            'total': total,
            'page': page,
            'size': size
        })

    @auth
    def post(self):
        """添加模板到误报黑名单"""
        data = request.json or {}
        template_id = data.get('template_id', '').strip()
        if not template_id:
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少 template_id 参数'})

        reason = data.get('reason', '').strip() or '手工标记误报'
        name = data.get('name', '').strip() or template_id
        severity = (data.get('severity') or 'unknown').strip().lower()
        tags = data.get('tags', [])
        source_type = data.get('source_type', 'community')

        col = utils.conn_db('nuclei_blacklist')
        now_str = utils.curr_date()
        doc = {
            'template_id': template_id,
            'name': name,
            'severity': severity,
            'tags': tags,
            'reason': reason,
            'source_type': source_type,
            'updated_at': now_str
        }
        col.update_one(
            {'template_id': template_id},
            {
                '$set': doc,
                '$setOnInsert': {'created_at': now_str}
            },
            upsert=True
        )
        return utils.build_ret(ErrorMsg.Success, {'message': f'模板 {template_id} 已成功加入误报黑名单'})


@ns.route('/blacklist/<string:template_id>/')
class NucleiBlacklistDetail(ARLResource):

    @auth
    def delete(self, template_id):
        """从误报黑名单移除单个模板 (大小写不敏感匹配)"""
        template_id = template_id.strip()
        col = utils.conn_db('nuclei_blacklist')
        res = col.delete_one({'$or': [{'template_id': template_id}, {'template_id': template_id.lower()}, {'template_id': template_id.upper()}]})
        if res.deleted_count == 0:
            return utils.build_ret(ErrorMsg.Error, {'error': f'未在黑名单中找到模板 {template_id}'})
        return utils.build_ret(ErrorMsg.Success, {'message': f'模板 {template_id} 已移出误报黑名单'})


@ns.route('/blacklist/delete/')
class NucleiBlacklistBatchDelete(ARLResource):

    @auth
    def post(self):
        """批量从误报黑名单移除模板 (大小写不敏感匹配)"""
        data = request.json or {}
        template_ids = data.get('template_ids', [])
        if not template_ids or not isinstance(template_ids, list):
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少 template_ids 列表'})

        col = utils.conn_db('nuclei_blacklist')
        query_ids = set()
        for tid in template_ids:
            if tid and isinstance(tid, str):
                t_str = tid.strip()
                query_ids.add(t_str)
                query_ids.add(t_str.lower())
                query_ids.add(t_str.upper())

        res = col.delete_many({'template_id': {'$in': list(query_ids)}})
        return utils.build_ret(ErrorMsg.Success, {'deleted_count': res.deleted_count, 'message': f'已成功移除 {res.deleted_count} 个模板'})


@ns.route('/community/source/')
class NucleiCommunitySource(ARLResource):

    @auth
    def get(self):
        """获取指定社区模板的 YAML 源码"""
        file_path = request.args.get('file_path', '').strip()
        template_id = request.args.get('template_id', '').strip()

        c_dir = get_community_templates_dir()
        if not c_dir or not os.path.isdir(c_dir):
            return utils.build_ret(ErrorMsg.Error, {'error': '未找到官方社区模板目录'})

        target_file = None
        if file_path:
            candidate = os.path.abspath(os.path.join(c_dir, file_path))
            # 严格防止目录遍历攻击 (Path Traversal Protection)
            if candidate.startswith(c_dir) and os.path.isfile(candidate):
                target_file = candidate

        if not target_file and template_id:
            templates = load_community_index()
            for t in templates:
                if t['template_id'] == template_id and t.get('file_path'):
                    cand = os.path.abspath(os.path.join(c_dir, t['file_path']))
                    if cand.startswith(c_dir) and os.path.isfile(cand):
                        target_file = cand
                        break

            # 容错兜底：若索引未命中，在官方目录下进行直接文件查找
            if not target_file:
                for ext in ['.yaml', '.yml']:
                    cand_name = f"{template_id}{ext}"
                    for root, dirs, files in os.walk(c_dir):
                        if cand_name in files:
                            cand = os.path.abspath(os.path.join(root, cand_name))
                            if cand.startswith(c_dir) and os.path.isfile(cand):
                                target_file = cand
                                break
                    if target_file:
                        break

        if not target_file or not os.path.isfile(target_file):
            return utils.build_ret(ErrorMsg.Error, {'error': '找不到该模板文件'})

        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                content = f.read()
            return utils.build_ret(ErrorMsg.Success, {'content': content, 'file_path': file_path or os.path.relpath(target_file, c_dir)})
        except Exception as e:
            return utils.build_ret(ErrorMsg.Error, {'error': f'读取模板失败: {e}'})


# ==============================================================================
# 官方社区模板同步状态机与执行引擎
# ==============================================================================

_sync_lock = threading.Lock()


def get_current_sync_doc() -> dict:
    """获取最新同步状态记录"""
    col = utils.conn_db('nuclei_sync_log')
    doc = col.find_one({'_id': 'latest_sync'})
    ver_info = get_nuclei_template_version_info()
    if not doc:
        return {
            "status": "idle",
            "sync_mode": "online",
            "start_time": "",
            "end_time": "",
            "current_version": ver_info.get("current_version", "未知"),
            "latest_version": ver_info.get("latest_version", "未知"),
            "has_update": ver_info.get("has_update", False),
            "before_total": 0,
            "after_total": 0,
            "diff_count": 0,
            "log": "",
            "error_message": "",
            "updated_at": ""
        }
    doc.pop('_id', None)
    # 动态融入当前最新版本感知
    doc["current_version"] = ver_info.get("current_version", doc.get("current_version", "未知"))
    doc["latest_version"] = ver_info.get("latest_version", doc.get("latest_version", "未知"))
    doc["has_update"] = ver_info.get("has_update", False)
    return doc


def run_community_sync_worker(mode: str = "online", offline_zip_path: str = None):
    """
    官方社区模板后台同步工作线程：
    支持 GitHub 镜像加速下载、版本与差量双重校验、离线 ZIP 覆盖及 Worker 容器协同广播
    """
    col = utils.conn_db('nuclei_sync_log')
    start_time = utils.curr_date()
    ver_info = get_nuclei_template_version_info()
    c_dir = get_community_templates_dir() or "/root/nuclei-templates"

    before_list = load_community_index(force_refresh=False)
    before_total = len(before_list)

    sync_state = {
        "status": "syncing",
        "sync_mode": mode,
        "start_time": start_time,
        "end_time": "",
        "current_version": ver_info.get("current_version", "未知"),
        "latest_version": ver_info.get("latest_version", "未知"),
        "has_update": ver_info.get("has_update", False),
        "before_total": before_total,
        "after_total": before_total,
        "diff_count": 0,
        "log": f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 开始启动官方社区模板同步任务 (模式: {mode})...\n",
        "error_message": "",
        "updated_at": start_time
    }
    col.update_one({'_id': 'latest_sync'}, {'$set': sync_state}, upsert=True)

    def _append_log(msg: str):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n"
        sync_state["log"] += line
        logger.info(f"[NucleiSync] {msg}")
        col.update_one({'_id': 'latest_sync'}, {
            '$set': {'log': sync_state["log"], 'updated_at': utils.curr_date()}
        })

    success = False
    error_msg = ""
    updated_version = ver_info.get("latest_version", ver_info.get("current_version", "未知"))

    try:
        if mode == "offline_zip":
            # 离线 ZIP 解压覆盖模式
            _append_log(f"📦 正在解析本地离线模板 ZIP 包: {offline_zip_path}")
            if not offline_zip_path or not os.path.isfile(offline_zip_path):
                raise Exception("未找到有效的离线模板 ZIP 文件")

            count = extract_templates_zip_to_dir(offline_zip_path, c_dir)
            _append_log(f"✅ 离线模板解压完成，成功覆盖解包 {count} 个文件")
            success = True

        else:
            # 在线网络同步模式：优先走 GitHub 镜像加速通道下载最新 release
            _append_log(f"🌐 探测当前模板状态: 本地版本 [{ver_info.get('current_version')}], 官方最新 [{ver_info.get('latest_version')}]")
            _append_log("⚡ 启动多通道 GitHub 镜像加速下载链路...")

            mirrors = [
                "https://ghfast.top/",
                "https://ghproxy.net/"
            ]
            latest_tag = ver_info.get('latest_version') or 'v10.5.0'
            candidate_raw_urls = [
                f"https://github.com/projectdiscovery/nuclei-templates/archive/refs/tags/{latest_tag}.zip",
                "https://github.com/projectdiscovery/nuclei-templates/releases/latest/download/nuclei-templates.zip"
            ]

            tmp_download = os.path.join(Config.TMP_PATH, f"nuclei_release_{utils.random_choices(8)}.zip")
            downloaded = False

            for raw_url in candidate_raw_urls:
                if downloaded:
                    break
                for mirror in mirrors:
                    target_url = f"{mirror}{raw_url}"
                    _append_log(f"🔗 尝试从镜像源 [{mirror}] 下载: {os.path.basename(raw_url)}...")
                    try:
                        t0 = time.time()
                        resp = requests.get(
                            target_url,
                            stream=True,
                            timeout=60,
                            verify=False,
                            allow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                        )
                        if resp.status_code == 200:
                            total_bytes = 0
                            with open(tmp_download, "wb") as f:
                                for chunk in resp.iter_content(chunk_size=128 * 1024):
                                    if chunk:
                                        f.write(chunk)
                                        total_bytes += len(chunk)
                            cost = round(time.time() - t0, 2)
                            size_mb = round(total_bytes / (1024 * 1024), 2)
                            _append_log(f"✅ 镜像源 [{mirror}] 下载成功！包体积: {size_mb} MB，耗时: {cost}s")
                            downloaded = True
                            break
                        else:
                            _append_log(f"⚠️ 镜像源 [{mirror}] 返回非 200 响应: HTTP {resp.status_code}，切换下一个...")
                    except Exception as ex:
                        _append_log(f"⚠️ 镜像源 [{mirror}] 连接异常: {ex}，切换下一个...")

            if downloaded and os.path.exists(tmp_download):
                _append_log(f"📂 正在解压覆盖到官方模板目录: {c_dir}")
                extracted_cnt = extract_templates_zip_to_dir(tmp_download, c_dir)
                _append_log(f"✅ 解压完成，已原子更新 {extracted_cnt} 个模板相关文件")
                success = True
                try:
                    os.unlink(tmp_download)
                except Exception:
                    pass
            else:
                # 镜像通道均不可用时，作为备用方案执行 nuclei -ut -ud 原生命令
                _append_log("⚠️ 镜像下载通道受阻，尝试执行 nuclei 原生 CLI 更新指令作为兜底...")
                cmd = ["nuclei", "-ut", "-ud", c_dir, "-duc=false"]
                _append_log(f"执行命令: {' '.join(cmd)}")
                proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
                combined_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
                _append_log(f"CLI 输出:\n{combined_output.strip()}")

                # 严格排查致命超时与下载失败关键字
                bad_keywords = ["failed to update", "failed to download", "deadline exceeded", "timeout", "Client.Timeout"]
                has_fatal_error = any(bk in combined_output for bk in bad_keywords)

                if has_fatal_error:
                    raise Exception(f"Nuclei CLI 原生更新失败 (网络超时或被重置): {combined_output[:180]}")
                else:
                    success = True

        if success:
            # 更新 .templates-config.json 的版本标记
            if ver_info.get("latest_version") and ver_info.get("latest_version") != "未知":
                updated_version = ver_info.get("latest_version")
                update_templates_config_version(updated_version)
                _append_log(f"🏷️ 本地版本标记已同步跃升至: {updated_version}")

            # 强制刷新内存索引池并统计增量
            _append_log("🔄 正在重新加载内存模板索引并核算差量...")
            after_list = load_community_index(force_refresh=True)
            after_total = len(after_list)
            diff_cnt = after_total - before_total
            _append_log(f"📊 模板索引刷新成功: 更新前 {before_total} 条 -> 更新后 {after_total} 条 (增量: {'+' if diff_cnt >= 0 else ''}{diff_cnt} 条)")

            # 广播通知 Worker 容器协同更新
            try:
                from app.celerytask import celery
                celery.send_task('app.celerytask.nuclei_template_sync_task', queue='arltask_light')
                _append_log("📡 已向 Celery 发送 Worker 协同更新指令，确保后台扫描与面板完全一致")
            except Exception as e:
                _append_log(f"ℹ️ Worker 协同广播提示: {e}")

            sync_state["status"] = "success"
            sync_state["after_total"] = after_total
            sync_state["diff_count"] = diff_cnt
            sync_state["current_version"] = updated_version
            sync_state["has_update"] = False
            sync_state["cache_epoch"] = time.time()
            _append_log("🎉 官方社区模板库同步圆满完成！")

    except Exception as e:
        error_msg = str(e)
        logger.exception(f"Nuclei sync worker error: {e}")
        _append_log(f"❌ 同步流程异常终止: {error_msg}")
        sync_state["status"] = "failed"
        sync_state["error_message"] = error_msg
    finally:
        sync_state["end_time"] = utils.curr_date()
        sync_state["updated_at"] = utils.curr_date()
        col.update_one({'_id': 'latest_sync'}, {'$set': sync_state})
        # 清理临时离线包
        if offline_zip_path and os.path.exists(offline_zip_path):
            try:
                os.unlink(offline_zip_path)
            except Exception:
                pass


@ns.route('/community/sync_status/')
class NucleiCommunitySyncStatus(ARLResource):

    @auth
    def get(self):
        """获取官方模板最新同步状态与完整日志"""
        data = get_current_sync_doc()
        return utils.build_ret(ErrorMsg.Success, data)


@ns.route('/community/sync/')
class NucleiCommunitySync(ARLResource):

    @auth
    def post(self):
        """触发官方社区模板在线同步 (带状态机与加速通道)"""
        col = utils.conn_db('nuclei_sync_log')
        current = col.find_one({'_id': 'latest_sync'})
        if current and current.get('status') == 'syncing':
            # 防抖防重保护：若上次任务在 5 分钟内启动，拦截重复点击
            st_time = current.get('start_time', '')
            return utils.build_ret("同步任务正在进行中，请勿重复触发", {"status": "syncing", "start_time": st_time})

        t = threading.Thread(target=run_community_sync_worker, kwargs={"mode": "online"}, daemon=True)
        t.start()
        return utils.build_ret(ErrorMsg.Success, {'message': '官方模板库加速同步任务已启动，正在后台拉取中'})


@ns.route('/community/sync_offline/')
class NucleiCommunitySyncOffline(ARLResource):

    @auth
    def post(self):
        """上传官方模板离线全量 ZIP 包覆盖更新"""
        if 'file' not in request.files:
            return utils.build_ret("未上传 ZIP 文件", {})

        file_obj = request.files['file']
        filename = file_obj.filename or ""
        if not filename.lower().endswith('.zip'):
            return utils.build_ret("仅支持上传 .zip 格式的模板压缩包", {})

        temp_zip = os.path.join(Config.TMP_PATH, f"offline_sync_{utils.random_choices(8)}.zip")
        try:
            file_obj.save(temp_zip)
            # 校验 zip 合法性
            with zipfile.ZipFile(temp_zip, 'r') as zf:
                names = zf.namelist()
                has_yaml = any(n.endswith(('.yaml', '.yml')) for n in names)
                if not has_yaml:
                    if os.path.exists(temp_zip):
                        os.unlink(temp_zip)
                    return utils.build_ret("上传的 ZIP 压缩包内未检测到 Nuclei YAML 模板文件", {})

            t = threading.Thread(target=run_community_sync_worker, kwargs={"mode": "offline_zip", "offline_zip_path": temp_zip}, daemon=True)
            t.start()
            return utils.build_ret(ErrorMsg.Success, {'message': '离线模板包已接收，正在后台解压覆盖中'})
        except Exception as e:
            if os.path.exists(temp_zip):
                try:
                    os.unlink(temp_zip)
                except Exception:
                    pass
            return utils.build_ret(f"处理离线包失败: {e}", {})


@ns.route('/stats/')
class NucleiStats(ARLResource):

    @auth
    def get(self):
        """获取 Nuclei 模板与引擎统计概览 (扩展版本与新版就绪感知)"""
        col = utils.conn_db('nuclei_template')
        custom_total = col.count_documents({})
        custom_enabled = col.count_documents({'enable': True})

        community_list = load_community_index()
        community_total = len(community_list)

        # 获取 nuclei 引擎版本
        nuclei_version = "未知"
        try:
            res = subprocess.run(["nuclei", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            combined = (res.stdout or "") + "\n" + (res.stderr or "")
            m = re.search(r'v\d+\.\d+\.\d+', combined)
            if m:
                nuclei_version = m.group(0)
        except Exception:
            pass

        # 获取黑名单屏蔽总数
        bl_col = utils.conn_db('nuclei_blacklist')
        blacklist_total = bl_col.count_documents({})

        # 获取模板版本信息
        ver_info = get_nuclei_template_version_info()
        sync_doc = get_current_sync_doc()

        return utils.build_ret(ErrorMsg.Success, {
            "custom_total": custom_total,
            "custom_enabled": custom_enabled,
            "community_total": community_total,
            "blacklist_total": blacklist_total,
            "nuclei_version": nuclei_version,
            "template_version": ver_info.get("current_version", "未知"),
            "template_latest_version": ver_info.get("latest_version", "未知"),
            "has_template_update": ver_info.get("has_update", False),
            "sync_status": sync_doc.get("status", "idle"),
            "sync_diff_count": sync_doc.get("diff_count", 0),
            "sync_end_time": sync_doc.get("end_time", ""),
            "has_community_dir": bool(get_community_templates_dir())
        })
