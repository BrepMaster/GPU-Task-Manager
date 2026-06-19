"""
TaskThread 单元测试：进度解析、生命周期。
测试 parse_output_line（纯逻辑）；不真正启动子进程。
"""
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt5.QtWidgets import QApplication

from gpu_manager.core.task_thread import TaskThread
from gpu_manager.core.models import TaskConfig

_app = QApplication.instance() or QApplication(sys.argv)


class TestParseOutputLine:
    """parse_output_line 应正确解析 Epoch X/Y 格式"""

    def _make_thread(self):
        cfg = TaskConfig(max_epochs=100)
        t = TaskThread(task_id=1, config=cfg, gpu_id=0)
        t.progress_update_interval = 0  # 禁用节流，方便测试
        return t

    def test_epoch_pattern_updates_progress(self):
        t = self._make_thread()
        t.parse_output_line("Epoch 10/100 - loss: 0.5")
        assert t.progress_info.epoch == 10
        assert t.progress_info.total_epochs == 100
        assert abs(t.progress_info.progress_percent - 10.0) < 0.01
        assert 'Epoch 10/100' in t.progress_info.status_text

    def test_no_epoch_pattern_no_change(self):
        t = self._make_thread()
        t.progress_info.epoch = 5
        t.parse_output_line("Some other log line")
        assert t.progress_info.epoch == 5  # 未变

    def test_zero_total_epochs_no_crash(self):
        t = self._make_thread()
        t.parse_output_line("Epoch 1/0")  # 异常：总数为 0
        assert t.progress_info.progress_percent == 0.0

    def test_large_epoch_numbers(self):
        t = self._make_thread()
        t.parse_output_line("Epoch 9999/10000")
        assert t.progress_info.epoch == 9999
        assert abs(t.progress_info.progress_percent - 99.99) < 0.01


class TestTaskThreadInit:
    """TaskThread 初始化应正确读取 TaskConfig"""

    def test_progress_info_from_config(self):
        cfg = TaskConfig(max_epochs=300)
        t = TaskThread(task_id=1, config=cfg, gpu_id=0)
        assert t.progress_info.total_epochs == 300
        assert t.progress_info.epoch == 0
        assert t.progress_info.status_text == "准备中"

    def test_config_attributes_accessible(self):
        cfg = TaskConfig(
            env_name='testenv',
            script_path='/tmp/train.py',
            experiment_name='myexp',
        )
        t = TaskThread(task_id=1, config=cfg, gpu_id=2)
        assert t.config.env_name == 'testenv'
        assert t.config.script_path == '/tmp/train.py'
        assert t.gpu_id == 2
