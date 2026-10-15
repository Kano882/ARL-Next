from app.utils.conn import conn_db
from app.config import Config
import time

_cache = {
    "black_ips": None,
    "forbidden_domains": None,
    "last_update": 0,
    # 跨进程版本号，用于让其他 worker 的进程内缓存失效
    "version": None
}
CACHE_TTL = 60  # Cache for 60 seconds

def get_security_policy():
    now = time.time()
    fresh = _cache["last_update"] > 0 and now - _cache["last_update"] < CACHE_TTL
    if fresh:
        # 版本比对：其他 worker 更新过安全策略时，本地缓存作废
        try:
            from app.config import _read_config_version
            # seen is None 表示本地缓存是在版本机制生效前填充的，不能按
            # "无法判定"放过，否则该 worker 会一直返回旧值直到 TTL 到期。
            seen = _cache.get("version")
            current = _read_config_version()
            if current is not None and seen != current:
                fresh = False
        except Exception:
            pass
    if fresh:
        return _cache["black_ips"], _cache["forbidden_domains"]
        
    doc = conn_db('system_config').find_one({"_id": "security_policy"})
    if not doc:
        black_ips = Config.BLACK_IPS
        forbidden_domains = Config.FORBIDDEN_DOMAINS
        # Seeding database with initial config
        conn_db('system_config').insert_one({
            "_id": "security_policy",
            "black_ips": black_ips,
            "forbidden_domains": forbidden_domains
        })
    else:
        black_ips = doc.get("black_ips", Config.BLACK_IPS)
        forbidden_domains = doc.get("forbidden_domains", Config.FORBIDDEN_DOMAINS)
        
    _cache["black_ips"] = black_ips
    _cache["forbidden_domains"] = forbidden_domains
    _cache["last_update"] = now
    # 记录填充时的版本号，供后续比对判定是否需要回源
    try:
        from app.config import _read_config_version
        _cache["version"] = _read_config_version()
    except Exception:
        _cache["version"] = None
    
    return black_ips, forbidden_domains

def update_security_policy(black_ips, forbidden_domains):
    doc = {
        "black_ips": black_ips,
        "forbidden_domains": forbidden_domains
    }
    conn_db('system_config').update_one(
        {"_id": "security_policy"}, 
        {"$set": doc}, 
        upsert=True
    )
    # Immediately invalidate cache (this process)
    _cache["last_update"] = 0
    # 跨进程失效：gunicorn 多 worker 各自持有进程内缓存，仅清本地会导致
    # "保存成功但立即刷新仍是旧值"。递增版本号让其他 worker 下次读取时回源。
    try:
        from app.config import bump_system_config_version
        bump_system_config_version()
    except Exception:
        pass
