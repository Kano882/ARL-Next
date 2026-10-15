#!/bin/bash
# ARL-Next 容器内后端统一自启脚本

set -e

echo "🚀 等待数据库和消息队列就绪..."
/usr/bin/wait-for-it.sh mongodb:27017 -t 60
/usr/bin/wait-for-it.sh rabbitmq:5672 -t 60

cd /code/backend
source /code/backend/.venv-docker/bin/activate
# (可选) 在启动前用 sed 临时将 config.yaml 中的 127.0.0.1 替换为容器内部的网络别名
# 这样你原本的代码完全不用改！
# 确保应用读到正确的配置文件
cp /code/backend/config.yaml /tmp/config.yaml.tmp
sed -i 's/127.0.0.1:27018/mongodb:27017/g' /tmp/config.yaml.tmp
sed -i 's/127.0.0.1:5673/rabbitmq:5672/g' /tmp/config.yaml.tmp
cp -f /tmp/config.yaml.tmp /code/backend/app/config.yaml
rm -f /tmp/config.yaml.tmp

echo "🚀 正在后台拉起 Celery 任务处理器..."
# 获取配置中的并发数量，添加了极强的异常捕获以防止 MongoDB 未就绪时导致的 Bash 崩溃
HEAVY=$(python3 -c "
try:
    from app.utils.performance_config import get_performance_config
    print(get_performance_config().get('celery_heavy_concurrency', 1))
except Exception:
    print(1)
" 2>/dev/null || echo 1)
if ! [[ "$HEAVY" =~ ^[0-9]+$ ]]; then HEAVY=1; fi

LIGHT=$(python3 -c "
try:
    from app.utils.performance_config import get_performance_config
    print(get_performance_config().get('celery_light_concurrency', 1))
except Exception:
    print(1)
" 2>/dev/null || echo 1)
if ! [[ "$LIGHT" =~ ^[0-9]+$ ]]; then LIGHT=1; fi

GITHUB=$(python3 -c "
try:
    from app.utils.performance_config import get_performance_config
    print(get_performance_config().get('github_concurrency', 1))
except Exception:
    print(1)
" 2>/dev/null || echo 1)
if ! [[ "$GITHUB" =~ ^[0-9]+$ ]]; then GITHUB=1; fi

# OOM 优先级分层：三个队列共用本容器（compose 的 oom_score_adj 是每容器属性，
# 无法在容器层面区分），实测三者 adj 同为 500、oom_score 同为 1010，内存耗尽时
# 内核对它们的取舍取决于 PID 等无关因素。
#
# ⚠️ oom_score_adj 的语义是「被牺牲的优先度」而非「重要性」：
#    **数值越大越先被杀**（内核选择 oom_score 最高的进程）。
#    因此"让某队列更早被牺牲"要把它调**大**，"更晚被牺牲"要调**小**。
#
# 分层意图（按失败重跑代价）：
#   - github 队列是短周期 API 轮询，失败重试代价低 → adj 提升到 700，优先被牺牲
#   - 扫描队列（heavy/light）承载长耗时任务，被杀需从头重跑 → 保持容器基线 500
#
# 为何不反过来（把扫描队列调低）：容器内非特权用户只能**提升** adj、
# 不能低于容器基线（写低值返回 Permission denied），故只能通过提升 github 来表达。
OOM_ADJ_SCAN=500        # 扫描队列（heavy / light）：保持容器基线，更晚被牺牲
OOM_ADJ_GITHUB=700      # GitHub 队列：优先被牺牲（失败重试代价低）
OOM_ADJ_WRAPPER="python3 /code/backend/run_worker_with_oom_adj.py"

if [ "$HEAVY" -gt 0 ] || [ "$LIGHT" -gt 0 ]; then
    echo "Starting HEAVY workers: $HEAVY, LIGHT workers: $LIGHT"

    if [ "$LIGHT" -gt 0 ]; then
        # 后台启动轻任务队列，并给它更大的 tasks-per-child 与 300MB 内存熔断
        $OOM_ADJ_WRAPPER "$OOM_ADJ_SCAN" python3 /code/backend/.venv-docker/bin/celery -A app.celerytask.celery worker -Q arltask_light -n arltask_light -c "$LIGHT" --max-tasks-per-child=50 --max-memory-per-child=300000 -l info &
    fi
    
    if [ "$HEAVY" -gt 0 ]; then
        # 后台启动重任务队列，并且严格限制 max-tasks-per-child=5 与 500MB 内存优雅熔断（任务执行后回收）
        $OOM_ADJ_WRAPPER "$OOM_ADJ_SCAN" python3 /code/backend/.venv-docker/bin/celery -A app.celerytask.celery worker -Q arltask,arltask_heavy -n arltask_heavy -c "$HEAVY" --max-tasks-per-child=5 --max-memory-per-child=500000 -l info &
    fi
else
    echo "Both Concurrency is 0, sleep"
    sleep 3600000000
fi

# 后台启动 GitHub 扫描 Celery worker (配置 300MB 内存熔断)
# 并发数由系统设置统一控制（github_concurrency），不再硬编码，避免该队列游离于治理之外
if [ "$GITHUB" -gt 0 ]; then
    echo "Starting GitHub workers: $GITHUB"
    $OOM_ADJ_WRAPPER "$OOM_ADJ_GITHUB" python3 /code/backend/.venv-docker/bin/celery -A app.celerytask.celery worker -Q arlgithub -n arlgithub -c "$GITHUB" --max-tasks-per-child=100 --max-memory-per-child=300000 -l info &
else
    # 允许通过配置为 0 显式停用 GitHub 扫描，避免在内存紧张时占用常驻进程
    echo "GitHub worker disabled (github_concurrency=0)"
fi
# 后台启动 Celery 定时任务调度器 (Scheduler)
python3 /code/backend/.venv-docker/bin/celery -A app.celerytask.celery beat -l info &

echo "🚀 正在前台拉起 ARL 监控任务调度引擎..."
python3 -m app.scheduler
