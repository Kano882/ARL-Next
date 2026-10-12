"""普通扫描与手动同步共用的资产组校验和状态反馈。"""
from bson import ObjectId
from app import utils
from app.modules import TaskSyncStatus
from app.helpers.scope import validate_task_scope


def sync_task_to_scope(task_id, scope_id, push_flag=False):
    # 此处只同步已有扫描结果，不重新派发扫描任务。
    from app.services.syncAsset import sync_asset
    tasks = utils.conn_db('task')
    query = {"_id": ObjectId(task_id)}
    task = tasks.find_one(query)
    if not task:
        return False
    try:
        scope = validate_task_scope(task.get("target", ""), scope_id)
        scope_id = str(scope["_id"])
        tasks.update_one(query, {"$set": {
            "sync_status": TaskSyncStatus.RUNNING, "sync_scope_id": scope_id,
            "sync_scope_name": scope.get("name", "")
        }, "$unset": {"sync_error": ""}})
        sync_asset(task_id=task_id, scope_id=scope_id, push_flag=push_flag)
        tasks.update_one(query, {"$set": {
            "sync_status": TaskSyncStatus.DEFAULT, "synced_scope_id": scope_id,
            "synced_scope_name": scope.get("name", "")
        }, "$unset": {"sync_error": ""}})
        return True
    except Exception as e:
        # 同步失败独立记录，保留任务的扫描状态和原始结果。
        tasks.update_one(query, {"$set": {"sync_status": TaskSyncStatus.ERROR, "sync_error": str(e)}})
        utils.get_logger().exception("task asset sync failed: %s", task_id)
        return False
