"""
gpu_manager.ui — 界面层：对话框、自定义组件、主窗口。
"""
from .dialogs import TaskEditDialog, TaskDetailDialog
from .ops_widget import make_ops_widget, make_progress_widget
from .gpu_card import GPUCardsPanel
from .main_window import MainWindow

__all__ = [
    "TaskEditDialog", "TaskDetailDialog",
    "make_ops_widget", "make_progress_widget",
    "GPUCardsPanel", "MainWindow",
]
