from aiohttp import web
import asyncio
import logging

logger = logging.getLogger(__name__)

background_tasks = set()

async def watchdog_task(app):
    """异步看门狗：定时轮询 MongoDB 获取最新并发配置并热更新"""
    task_manager = app.get('task_manager')
    # 第一次获取动态信号量，设置兜底默认值 1
    semaphore = task_manager.get_semaphore("recon_task", 1, dynamic=True)
    try:
        from clients.job_runner import db
        while True:
            try:
                db_config = await db.system_config.find_one({"_id": "performance"})
                limit = db_config.get("osint_concurrency", 1) if db_config else 1
                if hasattr(semaphore, "set_limit"):
                    await semaphore.set_limit(limit)
            except Exception as e:
                logger.error(f"Watchdog failed to fetch config: {e}")
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        pass

def submit_recon_job(task_manager, data):
    """将 Recon 任务提交至受信号量限制的协程池"""
    task_id = data.get("task_id")
    semaphore = task_manager.get_semaphore("recon_task", 1, dynamic=True)
    from clients.job_runner import run_recon_job

    async def bounded_recon_job():
        async with semaphore:
            await run_recon_job(data)

    task = asyncio.create_task(bounded_recon_job())
    background_tasks.add(task)
    task_manager.add_task(task_id, task)

    def handle_task_result(t):
        background_tasks.discard(t)
        try:
            t.result()
        except Exception as e:
            logger.error(f"Background task {task_id} crashed: {e}", exc_info=True)

    task.add_done_callback(handle_task_result)
    return task


async def start_recon(request):
    try:
        data = await request.json()
        task_id = data.get("task_id")
        if not task_id:
            return web.json_response({"code": 400, "msg": "Missing task_id"})

        task_manager = request.app.get('task_manager')
        submit_recon_job(task_manager, data)
        return web.json_response({"code": 200, "msg": "Task accepted", "task_id": task_id})
    except Exception as e:
        return web.json_response({"code": 500, "msg": str(e)})

async def stop_recon(request):
    try:
        data = await request.json()
        task_id = data.get("task_id")
        if not task_id:
            return web.json_response({"code": 400, "msg": "Missing task_id"})
        
        task_manager = request.app.get('task_manager')
        task_manager.remove_task(task_id)
        logger.info(f"Task {task_id} cancel requested via API.")
        return web.json_response({"code": 200, "msg": "Task stopped", "task_id": task_id})
    except Exception as e:
        return web.json_response({"code": 500, "msg": str(e)})


async def reconcile_orphan_tasks(app):
    """
    服务启动自愈机制：
    1. 将服务异常重启导致中断的 running 任务置为已停止 (stop)，附注说明供按需手动重启。
    2. 扫描 MongoDB 中残留的 waiting 任务（按创建时间 FIFO 排序），自动重新构建参数并入队排队。
    """
    await asyncio.sleep(1)
    task_manager = app.get('task_manager')
    try:
        from clients.job_runner import db, curr_date

        # 1. 处置服务异常重启前中断的 running 任务 -> 置为已停止 (stop)
        interrupted_tasks = await db['icp_task'].find({"status": "running"}).to_list(length=200)
        for it in interrupted_tasks:
            try:
                it_id = str(it["_id"])
                logger.warning(f"Reconciling interrupted running task {it_id} -> stop")
                await db['icp_task'].update_one(
                    {"_id": it["_id"]},
                    {"$set": {
                        "status": "stop",
                        "end_time": curr_date(),
                        "error_msg": "服务异常重启中断，已自动置为已停止，可按需手动重启"
                    }}
                )
            except Exception as it_err:
                logger.error(f"Failed to reconcile interrupted task {it.get('_id')}: {it_err}")

        # 2. 扫描残留的 waiting 任务并重新入队排队 (按 FIFO 启动时间正序)
        waiting_tasks = await db['icp_task'].find({"status": "waiting"}).sort("start_time", 1).to_list(length=500)
        if not waiting_tasks:
            logger.info("Startup reconciliation completed: no waiting tasks found.")
            return

        logger.info(f"Startup reconciliation: found {len(waiting_tasks)} waiting tasks to re-enqueue.")

        # 查询天眼查全局配置备用
        general_config = await db['system_config'].find_one({"_id": "general_config"})
        tyc_id = general_config.get("tyc_id", "") if general_config else ""
        tyc_token = general_config.get("tyc_token", "") if general_config else ""

        for wt in waiting_tasks:
            try:
                tid = str(wt["_id"])
                if task_manager.get_task(tid):
                    continue

                query_type = wt.get("query_type", [])
                if isinstance(query_type, str):
                    query_type = [q.strip() for q in query_type.split(',') if q.strip()]

                is_tyc = wt.get("task_type") == "tyc" or "gid" in wt

                if is_tyc:
                    if not tyc_id or not tyc_token:
                        logger.warning(f"Task {tid} requires TYC credentials but none configured. Marking as error.")
                        await db['icp_task'].update_one(
                            {"_id": wt["_id"]},
                            {"$set": {"status": "error", "error_msg": "系统未配置天眼查凭据，自愈恢复失败"}}
                        )
                        continue

                    options = {
                        "task_id": tid,
                        "gid": wt.get("gid"),
                        "depth": wt.get("depth", 1),
                        "invest_ratio": wt.get("invest_ratio", 0),
                        "query_type": query_type,
                        "enable_icp": wt.get("enable_icp", True),
                        "company_name": wt.get("company_name", ""),
                        "name": wt.get("name", ""),
                        "type": "tyc",
                        "tyc_id": tyc_id,
                        "tyc_token": tyc_token
                    }
                else:
                    options = {
                        "task_id": tid,
                        "target": wt.get("target"),
                        "query_type": query_type,
                        "type": "icp"
                    }

                submit_recon_job(task_manager, options)
                logger.info(f"Re-enqueued waiting task {tid} ({wt.get('name')}) successfully.")
            except Exception as wt_err:
                logger.error(f"Failed to re-enqueue waiting task {wt.get('_id')}: {wt_err}")

    except Exception as e:
        logger.error(f"Failed to reconcile orphan tasks: {e}", exc_info=True)


def setup_recon_routes(app):
    app.router.add_post("/api/v1/recon/start", start_recon)
    app.router.add_post("/api/v1/recon/stop", stop_recon)

    async def start_watchdog(app):
        app["watchdog_task"] = asyncio.create_task(watchdog_task(app))

    async def cleanup_watchdog(app):
        if "watchdog_task" in app:
            app["watchdog_task"].cancel()
            try:
                await app["watchdog_task"]
            except asyncio.CancelledError:
                pass

    async def start_reconciliation(app):
        app["reconciliation_task"] = asyncio.create_task(reconcile_orphan_tasks(app))

    async def cleanup_reconciliation(app):
        if "reconciliation_task" in app:
            app["reconciliation_task"].cancel()
            try:
                await app["reconciliation_task"]
            except asyncio.CancelledError:
                pass

    app.on_startup.append(start_watchdog)
    app.on_startup.append(start_reconciliation)
    app.on_cleanup.append(cleanup_watchdog)
    app.on_cleanup.append(cleanup_reconciliation)
