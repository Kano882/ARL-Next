"""backend/test 采集总控。

- stale/ 为待修复归档（坏导入/坏路径/僵尸用例），默认不参与采集，逐个修好后移回本目录。
- live/ 为生产回归脚本（模块级直连生产/真机），默认不参与采集，需显式指定文件运行。
- integration/ 为在线 API 集成测试，后端不可达时自动 skip，不影响默认采集结果。
- manual/ 为手工脚本（基准/覆盖率/探测），文件名不参与 pytest 采集。
"""
import os
import sys

# xing 仅在容器/Py虚环境中 pip 安装；本机直跑时把 ARL-NPoC 源码目录加入路径兜底。
_XING_DIR = os.path.join(os.path.dirname(__file__), "..", "ARL-NPoC")
if os.path.isdir(_XING_DIR) and _XING_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_XING_DIR))

collect_ignore = ["stale", "live", "manual"]
