import bson
from app import utils
from app.modules import TaskTag


def get_options_by_policy_id(policy_id, task_tag):
    if not policy_id or not bson.ObjectId.is_valid(str(policy_id)):
        return None

    query = {
        "_id": bson.ObjectId(policy_id)
    }
    data = utils.conn_db("policy").find_one(query)
    if not data:
        return None

    policy = dict(data.get("policy") or {})
    options = {
        "policy_name": data.get("name", "")
    }
    domain_config = dict(policy.pop("domain_config", None) or {})
    ip_config = dict(policy.pop("ip_config", None) or {})
    site_config = dict(policy.pop("site_config", None) or {})

    # 移除死字段与无效字段
    policy.pop("scope_config", None)
    site_config.pop("site_capture", None)

    """仅仅资产发现任务需要这些"""
    if task_tag == TaskTag.TASK:
        options.update(domain_config)
        options.update(ip_config)

    options.update(site_config)
    options.update(policy)

    # 🛡️ 双轨服务识别统一：若开启 service_detection，自动协同开启 npoc_service_detection
    is_service_detect = bool(options.get("service_detection") or options.get("npoc_service_detection"))
    if is_service_detect:
        options["service_detection"] = True
        options["npoc_service_detection"] = True

    # 🛡️ 兼容文件泄露字段双向回退（真值与自定义字典优先）
    if site_config.get("file_leak") and not options.get("file_leak"):
        options["file_leak"] = site_config["file_leak"]
    if site_config.get("file_leak_dict") and (not options.get("file_leak_dict") or options.get("file_leak_dict") == "file_top_2000.txt"):
        options["file_leak_dict"] = str(site_config["file_leak_dict"])

    return options
