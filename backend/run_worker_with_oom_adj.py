#!/usr/bin/env python3
"""以指定 oom_score_adj 启动 Celery worker。

用法:
    run_worker_with_oom_adj.py <oom_score_adj> <celery 命令及其参数...>

为什么需要这层包装：
    oom_score_adj 是**每容器**属性（compose 的 `oom_score_adj: 500`），
    但三个队列（heavy / light / github）共用同一个 arl-worker-prod 容器，
    无法在容器层面区分优先级——内存耗尽时内核对一个 celery 子进程的取舍
    与其兄弟进程完全同分（实测 adj 均为 500、oom_score 均为 1010），
    选择结果取决于 PID 等无关因素。

    本脚本在 **fork 出子进程之前**设置主进程的 adj，Celery 的 prefork 子进程
    会继承该值。这一点很关键：子进程会因 --max-tasks-per-child 被回收重建，
    只有从主进程继承才能保证重建后仍然生效，逐个子进程设置的做法会失效。

约束（实测，容器内非特权用户）：
    - 只能**提升** adj（>= 容器基线），不能降低；写低于基线的值返回 Permission denied
    - 有效范围 [-1000, 1000]，超出被内核拒绝
    因此"让某个队列先于其他队列被牺牲"只能通过**提升其他队列**来表达。

设置失败不应阻断 worker 启动：OOM 优先级是优化项，而非任务执行的必要条件。
"""
import os
import sys

OOM_SCORE_ADJ_PATH = '/proc/self/oom_score_adj'
OOM_SCORE_ADJ_MIN, OOM_SCORE_ADJ_MAX = -1000, 1000


def normalize(value):
    """把输入钳制到内核允许的范围。非法输入返回 None。"""
    try:
        adj = int(value)
    except (TypeError, ValueError):
        return None
    return max(OOM_SCORE_ADJ_MIN, min(OOM_SCORE_ADJ_MAX, adj))


def apply_oom_score_adj(value, path=OOM_SCORE_ADJ_PATH):
    """写入 oom_score_adj。成功返回 (True, 规范化后的值)，失败返回 (False, 原因)。"""
    adj = normalize(value)
    if adj is None:
        return False, f'无法解析为整数: {value!r}'
    try:
        with open(path, 'w', encoding='ascii') as fh:
            fh.write(str(adj))
    except PermissionError:
        # 容器内非特权场景：只允许提升、不允许降低
        return False, f'权限不足（容器内只能提升 adj，不能低于基线）: {adj}'
    except OSError as exc:
        return False, f'写入失败: {exc}'
    except Exception as exc:  # noqa: BLE001
        # 兜底：OOM 优先级是优化项，任何异常都不得阻断 worker 启动
        return False, f'设置失败: {exc}'
    return True, adj


def main(argv):
    if len(argv) < 3:
        print('用法: run_worker_with_oom_adj.py <oom_score_adj> <command...>',
              file=sys.stderr)
        return 2

    raw_adj, command = argv[1], argv[2:]

    ok, info = apply_oom_score_adj(raw_adj)
    if ok:
        print(f'[oom_adj] 本队列 oom_score_adj = {info}', flush=True)
    else:
        # 降级而非失败：worker 仍须启动，只是失去 OOM 优先级区分
        print(f'[oom_adj] 未能设置 oom_score_adj（{info}），继续以容器默认值启动',
              flush=True)

    # 以 exec 替换自身，保持 PID 不变——Celery 主进程即本进程，
    # 子进程由它 fork，从而继承上面的 adj 设置。
    try:
        os.execvp(command[0], command)
    except OSError as exc:
        print(f'[oom_adj] 无法启动 {command[0]!r}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
