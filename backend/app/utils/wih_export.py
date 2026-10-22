"""保留 WIH 文本导出的原格式，为接口候选补充请求来源。"""


def format_wih_export(item, content_field="content"):
    record_type = item.get("record_type") or item.get("recordType", "unknown")
    site = item.get("site", "unknown_site")
    text = "{} [{}] {}".format(site, record_type, item.get(content_field, ""))
    if record_type == "api_endpoint" and isinstance(item.get("api_request"), dict):
        text += " [source: {}]".format(item.get("source") or "-")
    return text
