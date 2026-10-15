from app.utils.conn import conn_db

def get_performance_config():
    """读取三队列的 Worker 进程数配置。

    语义限定：三项均为 Celery Worker 的进程数（启动参数 -c），
    与单任务内部的 DNS 爆破并发度（massdns -s，见 Config.DOMAIN_BRUTE_CONCURRENT）
    不是同一量级的指标，勿混用。
    """
    doc = conn_db('system_config').find_one({"_id": "performance"})
    if not doc:
        return {"celery_heavy_concurrency": 1, "celery_light_concurrency": 1, "osint_concurrency": 1}
    return {
        "celery_heavy_concurrency": doc.get("celery_heavy_concurrency", 1),
        "celery_light_concurrency": doc.get("celery_light_concurrency", 1),
        "osint_concurrency": doc.get("osint_concurrency", 1)
    }

def update_performance_config(celery_heavy_concurrency, celery_light_concurrency, osint_concurrency):
    conn_db('system_config').update_one(
        {"_id": "performance"}, 
        {"$set": {
            "celery_heavy_concurrency": celery_heavy_concurrency,
            "celery_light_concurrency": celery_light_concurrency,
            "osint_concurrency": osint_concurrency
        }}, 
        upsert=True
    )
