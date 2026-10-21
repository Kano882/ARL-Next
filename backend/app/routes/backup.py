import os
import threading
from flask import request, send_file
from flask_restx import Namespace, fields, reqparse
from . import ARLResource
from app.utils import auth
from app.services.backup_service import (
    create_backup_archive,
    restore_backup_archive,
    list_all_backups,
    delete_backup_file,
    read_archive_manifest,
    get_backup_dir,
    get_running_task_count,
    progress_tracker
)

ns = Namespace("backup", description="系统全量数据备份与恢复 API")

create_backup_model = ns.model('CreateBackup', {
    'include_screenshots': fields.Boolean(default=True, description='是否包含站点资产截图文件'),
    'note': fields.String(default='', description='备份备注说明')
})

restore_model = ns.model('RestoreBackup', {
    'filename': fields.String(required=True, description='备份归档文件名'),
    'force': fields.Boolean(default=False, description='若存在运行中任务，是否强制终止并继续恢复')
})


@ns.route('/create')
class CreateBackup(ARLResource):
    @auth
    @ns.expect(create_backup_model)
    def post(self):
        """
        异步触发一键全量备份
        """
        state = progress_tracker.get_state()
        if state["status"] in ["backing_up", "restoring"]:
            return {
                "code": 409,
                "message": f"当前已有进行中的任务 ({state['action']})，请等待其完成后再发起。",
                "data": state
            }

        data = request.json or {}
        include_screenshots = data.get('include_screenshots', True)
        note = data.get('note', '')

        # 启动后台异步线程执行备份，避免超大备份包耗时过长导致网关 HTTP 504 超时
        def run_backup_async():
            try:
                create_backup_archive(include_screenshots=include_screenshots, note=note)
            except Exception:
                pass

        thread = threading.Thread(target=run_backup_async, daemon=True)
        thread.start()

        return {
            "code": 200,
            "message": "备份任务已成功在后台启动",
            "data": {
                "include_screenshots": include_screenshots,
                "note": note
            }
        }


@ns.route('/status')
class BackupStatus(ARLResource):
    @auth
    def get(self):
        """
        获取当前备份或恢复任务的实时进度与状态
        """
        state = progress_tracker.get_state()
        return {
            "code": 200,
            "message": "success",
            "data": state
        }


@ns.route('/list')
class BackupList(ARLResource):
    @auth
    def get(self):
        """
        获取服务器上现存的所有备份文件列表与元数据
        """
        backups = list_all_backups()
        running_tasks = get_running_task_count()
        return {
            "code": 200,
            "message": "success",
            "data": {
                "items": backups,
                "running_tasks": running_tasks
            }
        }


@ns.route('/download/<string:filename>')
class DownloadBackup(ARLResource):
    @auth
    def get(self, filename):
        """
        下载指定的备份归档文件
        """
        safe_name = os.path.basename(filename)
        if not (safe_name.startswith("arl_backup_") and safe_name.endswith(".tar.gz")):
            return {"code": 400, "message": "非法的备份文件名"}, 400

        backup_dir = get_backup_dir()
        file_path = os.path.join(backup_dir, safe_name)
        if not os.path.isfile(file_path):
            return {"code": 404, "message": "备份文件不存在"}, 404

        try:
            return send_file(
                file_path,
                as_attachment=True,
                download_name=safe_name,
                mimetype="application/gzip"
            )
        except TypeError:
            # 兼容低版本 Flask 的 attachment_filename 参数名
            return send_file(
                file_path,
                as_attachment=True,
                attachment_filename=safe_name,
                mimetype="application/gzip"
            )


@ns.route('/delete/<string:filename>')
class DeleteBackup(ARLResource):
    @auth
    def delete(self, filename):
        """
        删除指定的备份文件
        """
        try:
            success = delete_backup_file(filename)
            if success:
                return {"code": 200, "message": "备份文件已成功删除"}
            return {"code": 404, "message": "备份文件不存在"}
        except ValueError as ve:
            return {"code": 400, "message": str(ve)}
        except Exception as e:
            return {"code": 500, "message": f"删除备份文件失败: {str(e)}"}


@ns.route('/upload')
class UploadBackup(ARLResource):
    @auth
    def post(self):
        """
        上传外部备份包至服务器
        """
        if 'file' not in request.files:
            return {"code": 400, "message": "未找到上传文件字段 'file'"}

        file_obj = request.files['file']
        orig_filename = os.path.basename(file_obj.filename or "")

        if not (orig_filename.startswith("arl_backup_") and orig_filename.endswith(".tar.gz")):
            return {"code": 400, "message": "文件名格式不正确，必须为 arl_backup_*.tar.gz 格式"}

        backup_dir = get_backup_dir()
        dest_path = os.path.join(backup_dir, orig_filename)

        # 保存文件
        file_obj.save(dest_path)

        # 校验 manifest 有效性
        try:
            manifest = read_archive_manifest(dest_path)
            return {
                "code": 200,
                "message": "备份包上传并校验成功",
                "data": {
                    "filename": orig_filename,
                    "size": os.path.getsize(dest_path),
                    "created_at": manifest.get("created_at"),
                    "arl_version": manifest.get("arl_version"),
                    "include_screenshots": manifest.get("include_screenshots", True),
                    "summary": manifest.get("mongo_stats", {}).get("summary", {})
                }
            }
        except Exception as e:
            if os.path.isfile(dest_path):
                os.remove(dest_path)
            return {"code": 400, "message": f"上传的备份包无效或已损坏: {str(e)}"}


@ns.route('/restore')
class RestoreBackup(ARLResource):
    @auth
    @ns.expect(restore_model)
    def post(self):
        """
        异步触发一键全量恢复
        """
        state = progress_tracker.get_state()
        if state["status"] in ["backing_up", "restoring"]:
            return {
                "code": 409,
                "message": f"当前已有进行中的任务 ({state['action']})，请等待其完成后再发起。",
                "data": state
            }

        data = request.json or {}
        filename = data.get('filename')
        force = data.get('force', False)

        if not filename:
            return {"code": 400, "message": "缺少必要的 filename 参数"}

        safe_name = os.path.basename(filename)
        backup_dir = get_backup_dir()
        archive_path = os.path.join(backup_dir, safe_name)

        if not os.path.isfile(archive_path):
            return {"code": 404, "message": "指定的备份归档文件不存在"}

        # 检查运行中的任务
        running_tasks = get_running_task_count()
        if running_tasks > 0 and not force:
            return {
                "code": 409,
                "message": f"系统当前有 {running_tasks} 个正在进行的扫描任务，执行覆盖恢复将中断这些任务。",
                "data": {
                    "running_tasks": running_tasks,
                    "require_force": True
                }
            }

        # 启动后台异步线程执行恢复
        def run_restore_async():
            try:
                restore_backup_archive(archive_path=archive_path, force=force)
            except Exception:
                pass

        thread = threading.Thread(target=run_restore_async, daemon=True)
        thread.start()

        return {
            "code": 200,
            "message": "数据覆盖恢复任务已在后台启动",
            "data": {
                "filename": safe_name,
                "force": force
            }
        }


@ns.route('/info/<string:filename>')
class BackupInfo(ARLResource):
    @auth
    def get(self, filename):
        """
        读取并返回指定备份包的完整元数据与资产大盘统计
        """
        safe_name = os.path.basename(filename)
        backup_dir = get_backup_dir()
        file_path = os.path.join(backup_dir, safe_name)
        if not os.path.isfile(file_path):
            return {"code": 404, "message": "备份文件不存在"}, 404

        try:
            manifest = read_archive_manifest(file_path)
            return {
                "code": 200,
                "message": "success",
                "data": {
                    "filename": safe_name,
                    "size": os.path.getsize(file_path),
                    "manifest": manifest
                }
            }
        except Exception as e:
            return {"code": 500, "message": f"解析元数据失败: {str(e)}"}
