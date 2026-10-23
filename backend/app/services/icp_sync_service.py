import bson
from app.utils import get_logger, curr_date, conn_db
from app.modules import ErrorMsg

logger = get_logger()


def enrich_icp_tasks_with_scopes(items):
    """为企业测绘任务列表批量关联并回填资产组状态与增量标识"""
    if not items:
        return

    scope_col = conn_db('asset_scope')
    scope_names = [t.get('synced_scope_name') or t.get('name') for t in items if t.get('name')]
    scope_ids = []
    for t in items:
        sid = t.get('synced_scope_id')
        if sid:
            try:
                scope_ids.append(bson.ObjectId(sid))
            except Exception:
                pass

    query_or = []
    if scope_ids:
        query_or.append({"_id": {"$in": scope_ids}})
    if scope_names:
        query_or.append({"name": {"$in": scope_names}})

    matched_scopes = []
    if query_or:
        matched_scopes = list(scope_col.find(
            {"$or": query_or},
            {"_id": 1, "name": 1, "group_name": 1, "domain_array": 1, "scope_array": 1}
        ))

    scope_by_id = {str(s["_id"]): s for s in matched_scopes}
    scope_by_name = {s["name"]: s for s in matched_scopes}

    for item in items:
        stat = item.get('statistic') or {}
        web_cnt = stat.get('web_cnt', 0)

        if web_cnt == 0:
            item['sync_badge_status'] = 'no_web'
            item['has_increment'] = False
            continue

        scope = None
        if item.get('synced_scope_id'):
            scope = scope_by_id.get(str(item['synced_scope_id']))
        if not scope and item.get('name'):
            scope = scope_by_name.get(item['name'])
            if scope:
                item['synced_scope_id'] = str(scope['_id'])
                item['synced_scope_name'] = scope.get('name', '')
                item['synced_group_name'] = scope.get('group_name', '')

        if scope:
            item['sync_badge_status'] = 'synced'
            scope_domains = set((scope.get('domain_array') or scope.get('scope_array') or []))
            item['has_increment'] = bool(web_cnt > len(scope_domains))
        else:
            item['sync_badge_status'] = 'unsynced'
            item['has_increment'] = False


def build_icp_asset_compat_query(query: dict) -> dict:
    """针对跨数据源 (ICP vs TYC) 的核心字段构建多路兼容 ($or) 查询"""
    or_groups = []

    # 1. 域名 (domain vs ym)
    if 'domain' in query:
        val = query.pop('domain')
        query.pop('ym', None)
        or_groups.append([{'domain': val}, {'ym': val}])
    elif 'ym' in query:
        val = query.pop('ym')
        or_groups.append([{'domain': val}, {'ym': val}])

    # 2. 单位名称 (unitName vs companyName)
    if 'unitName' in query:
        val = query.pop('unitName')
        query.pop('companyName', None)
        or_groups.append([{'unitName': val}, {'companyName': val}])
    elif 'companyName' in query:
        val = query.pop('companyName')
        or_groups.append([{'unitName': val}, {'companyName': val}])

    # 3. 业务/资产名称 (serviceName, webName, name, title)
    matched_name_val = None
    for k in ['serviceName', 'name', 'webName', 'title']:
        if k in query:
            matched_name_val = query.pop(k)
            break
    if matched_name_val:
        for k in ['serviceName', 'name', 'webName', 'title']:
            query.pop(k, None)
        or_groups.append([
            {'serviceName': matched_name_val},
            {'name': matched_name_val},
            {'webName': matched_name_val},
            {'title': matched_name_val}
        ])

    # 4. 主体备案号 (mainLicence vs liscense)
    if 'mainLicence' in query:
        val = query.pop('mainLicence')
        query.pop('liscense', None)
        or_groups.append([{'mainLicence': val}, {'liscense': val}])
    elif 'liscense' in query:
        val = query.pop('liscense')
        or_groups.append([{'mainLicence': val}, {'liscense': val}])

    # 5. 服务/应用备案号 (serviceLicence vs serviceFilingNumber)
    if 'serviceLicence' in query:
        val = query.pop('serviceLicence')
        query.pop('serviceFilingNumber', None)
        or_groups.append([{'serviceLicence': val}, {'serviceFilingNumber': val}])
    elif 'serviceFilingNumber' in query:
        val = query.pop('serviceFilingNumber')
        or_groups.append([{'serviceLicence': val}, {'serviceFilingNumber': val}])

    # 6. 法定代表人 (legalPerson vs legalPersonName)
    if 'legalPerson' in query:
        val = query.pop('legalPerson')
        query.pop('legalPersonName', None)
        or_groups.append([{'legalPerson': val}, {'legalPersonName': val}])
    elif 'legalPersonName' in query:
        val = query.pop('legalPersonName')
        or_groups.append([{'legalPerson': val}, {'legalPersonName': val}])

    # 7. 企业状态 (status vs regStatus)
    if 'status' in query:
        val = query.pop('status')
        query.pop('regStatus', None)
        or_groups.append([{'status': val}, {'regStatus': val}])
    elif 'regStatus' in query:
        val = query.pop('regStatus')
        or_groups.append([{'status': val}, {'regStatus': val}])

    # 8. 分类/性质 (category vs classes vs type vs companyType vs natureName)
    matched_cat_val = None
    for k in ['category', 'classes', 'type', 'companyType', 'natureName']:
        if k in query:
            matched_cat_val = query.pop(k)
            break
    if matched_cat_val:
        for k in ['category', 'classes', 'type', 'companyType', 'natureName']:
            query.pop(k, None)
        or_groups.append([
            {'category': matched_cat_val},
            {'classes': matched_cat_val},
            {'type': matched_cat_val},
            {'companyType': matched_cat_val},
            {'natureName': matched_cat_val}
        ])

    # 9. 微信公号 (wechatId vs publicNum)
    if 'wechatId' in query:
        val = query.pop('wechatId')
        query.pop('publicNum', None)
        or_groups.append([{'wechatId': val}, {'publicNum': val}])
    elif 'publicNum' in query:
        val = query.pop('publicNum')
        or_groups.append([{'wechatId': val}, {'publicNum': val}])

    # 10. 简介 (brief vs recommend vs info)
    matched_brief_val = None
    for k in ['brief', 'recommend', 'info']:
        if k in query:
            matched_brief_val = query.pop(k)
            break
    if matched_brief_val:
        for k in ['brief', 'recommend', 'info']:
            query.pop(k, None)
        or_groups.append([
            {'brief': matched_brief_val},
            {'recommend': matched_brief_val},
            {'info': matched_brief_val}
        ])

    if or_groups:
        existing_and = query.get('$and', [])
        for grp in or_groups:
            existing_and.append({'$or': grp})
        query['$and'] = existing_and

    return query
