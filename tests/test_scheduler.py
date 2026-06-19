"""
TaskScheduler 单元测试：GPU 占用管理、任务队列、stop 清理。
需要 PyQt5 但无需 GUI（offscreen 模式）。
"""
import os
import sys
import threading

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt5.QtWidgets import QApplication

from gpu_manager.core.scheduler import TaskScheduler

# 确保 QApplication 单例存在（pytest 环境下不会自动创建）
_app = QApplication.instance() or QApplication(sys.argv)


class TestSchedulerGpuManagement:
    """gpu_in_use 的增删清理"""

    def setup_method(self):
        self.s = TaskScheduler()
        # 预设一些占用状态
        self.s.gpu_in_use = {1: 0, 2: 1, 3: 0}
        self.s.current_task_id = 1
        self.s.waiting_tasks = [(10, None, 0), (11, None, 1)]

    def test_release_task_gpu_removes_entry(self):
        self.s.release_task_gpu(1)
        assert 1 not in self.s.gpu_in_use
        assert self.s.current_task_id is None

    def test_release_task_gpu_clears_current_only_if_matches(self):
        self.s.current_task_id = 2
        self.s.release_task_gpu(1)  # 释放的不是 current
        assert self.s.current_task_id == 2  # 不变

    def test_release_nonexistent_task_no_crash(self):
        self.s.release_task_gpu(999)  # 应该静默通过
        assert len(self.s.gpu_in_use) == 3

    def test_release_from_another_thread(self):
        """跨线程调用 release_task_gpu 不应崩溃"""
        errors = []
        def worker():
            try:
                self.s.release_task_gpu(2)
            except Exception as e:
                errors.append(e)
        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert not errors
        assert 2 not in self.s.gpu_in_use

    def test_stop_clears_all(self):
        self.s.running_tasks = {}
        self.s.stop()
        assert len(self.s.gpu_in_use) == 0
        assert len(self.s.waiting_tasks) == 0
        assert self.s.current_task_id is None


class TestSchedulerQueue:
    """add_task / waiting_tasks 队列管理"""

    def setup_method(self):
        self.s = TaskScheduler()

    def test_add_task_appends_to_waiting(self):
        self.s.add_task(1, None, 0)
        self.s.add_task(2, None, 1)
        assert len(self.s.waiting_tasks) == 2
        assert self.s.waiting_tasks[0] == (1, None, 0)
        assert self.s.waiting_tasks[1] == (2, None, 1)

    def test_add_task_is_thread_safe(self):
        """并发 add_task 不应丢数据"""
        N = 100
        def add_batch(start):
            for i in range(start, start + N):
                self.s.add_task(i, None, i % 2)
        threads = [
            threading.Thread(target=add_batch, args=(0,)),
            threading.Thread(target=add_batch, args=(N,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(self.s.waiting_tasks) == N * 2
