"""
gpu_manager.ui.main_window — 主窗口模块。
通过 mixin 组合把不同职责的方法拆分到独立文件。
"""
from .base import _MainWindowBase
from .gpu_ops import GPUMixin
from .task_mgmt import TaskMixin
from .task_ops import TaskOpsMixin
from .log_cfg import LogCfgMixin


class MainWindow(GPUMixin, TaskMixin, TaskOpsMixin, LogCfgMixin,
                 _MainWindowBase):
    """GPU 任务管理器主窗口"""
    pass


__all__ = ["MainWindow"]
