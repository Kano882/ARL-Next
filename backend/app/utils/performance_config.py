from app.utils.conn import conn_db

# 各队列并发默认值。统一在此声明，避免启动脚本与配置读取各写一份导致漂移。
# github 队列原先在 start_worker_prod.sh 中硬编码为 2，既不经过系统设置页也无法调节，
# 现纳入统一配置；默认值取 1，与该脚本的保守基线一致。
DEFAULT_CONCURRENCY = {
    "celery_heavy_concurrency": 1,
    "celery_light_concurrency": 1,
    "osint_concurrency": 1,
    "github_concurrency": 1,
}

# 各队列的合法上限，供接口层校验，避免写入异常值导致进程数失控。
CONCURRENCY_BOUNDS = {
    "celery_heavy_concurrency": (1, 128),
    "celery_light_concurrency": (1, 256),
    "osint_concurrency": (1, 128),
    "github_concurrency": (1, 64),
}


def get_performance_config():
    """读取各队列的 Worker 进程数配置。

    语义限定：各项均为 Celery Worker 的进程数（启动参数 -c），
    与单任务内部的 DNS 爆破并发度（massdns -s，见 Config.DOMAIN_BRUTE_CONCURRENT）
    不是同一量级的指标，勿混用。

    缺失字段（如存量文档在新增 github_concurrency 之前写入）回退到默认值，
    保证升级过程不需要强制改写数据库即可正常启动。
    """
    doc = conn_db('system_config').find_one({"_id": "performance"})
    if not doc:
        return dict(DEFAULT_CONCURRENCY)
    return {
        key: doc.get(key, default)
        for key, default in DEFAULT_CONCURRENCY.items()
    }


def update_performance_config(celery_heavy_concurrency, celery_light_concurrency,
                              osint_concurrency, github_concurrency=None):
    """写入并发配置。

    github_concurrency 为 None 时保留库中现值（缺失则用默认值），
    使旧版前端/调用方在不传该字段时不会把它意外重置。
    """
    doc = {
        "celery_heavy_concurrency": celery_heavy_concurrency,
        "celery_light_concurrency": celery_light_concurrency,
        "osint_concurrency": osint_concurrency,
    }
    if github_concurrency is not None:
        doc["github_concurrency"] = github_concurrency

    conn_db('system_config').update_one(
        {"_id": "performance"},
        {"$set": doc},
        upsert=True
    )
