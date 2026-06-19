"""
gpu_manager — 深度学习 GPU 任务管理器（拆分后的包结构）。

核心模块：
  gpu_manager.core   : 业务逻辑与数据层（配置、GPU/Conda 管理、任务线程、调度器）
  gpu_manager.ui     : 界面层（主窗口、对话框、自定义组件）
"""
from .core import (
    APP_TITLE, APP_VERSION, Colors, STATUS_NAMES,
    ConsoleHider, CondaManager, GPUManager,
    TaskThread, TaskScheduler,
)
from .ui import (
    MainWindow,
    TaskEditDialog, TaskDetailDialog,
    make_ops_widget, make_progress_widget,
    GPUCardsPanel,
)

__all__ = [
    # 核心
    "APP_TITLE", "APP_VERSION", "Colors", "STATUS_NAMES",
    "ConsoleHider", "CondaManager", "GPUManager",
    "TaskThread", "TaskScheduler",
    # UI
    "MainWindow",
    "TaskEditDialog", "TaskDetailDialog",
    "make_ops_widget", "make_progress_widget",
    "GPUCardsPanel",
]
