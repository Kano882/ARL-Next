"""状态统计只读取分组数量，不加载任务记录或补算资产数据。"""


def get_task_statistics(collection, include_stage_statuses=False):
    counts = {key: 0 for key in ('total', 'running', 'waiting', 'done', 'error', 'stop')}
    groups = collection.aggregate([{'$group': {'_id': '$status', 'count': {'$sum': 1}}}])
    for group in groups:
        status, count = group['_id'], group['count']
        counts['total'] += count
        if status in ('waiting', 'done', 'error', 'stop'):
            counts[status] += count
        elif status == 'running' or include_stage_statuses:
            counts['running'] += count
    counts['active'] = counts['running'] + counts['waiting']
    counts['abnormal'] = counts['error'] + counts['stop']
    return counts


def attach_task_statistics(data, collection, logger, include_stage_statuses=False):
    try:
        data['statistics'] = get_task_statistics(collection, include_stage_statuses)
    except Exception:
        logger.exception('Failed to aggregate task status statistics')
        # 列表仍可用；不以零值覆盖客户端已显示的统计。
        data['statistics_error'] = True
    return data
