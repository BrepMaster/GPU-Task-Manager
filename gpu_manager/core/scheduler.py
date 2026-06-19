"""
任务调度器：按 GPU 占用情况调度待运行任务，后台线程运行。
"""
import time
import threading

from PyQt5.QtCore import QThread, pyqtSignal

from .gpu_manager import GPUManager
from .logger import get_logger

logger = get_logger('scheduler')


class TaskScheduler(QThread):
    task_ready = pyqtSignal(int, int)
    scheduler_stopped = pyqtSignal()
    scheduler_started = pyqtSignal()

    def __init__(self, max_concurrent_gpus=0):
        super().__init__()
        self._is_running = True
        self._stop_event = threading.Event()
        self.waiting_tasks = []
        self.running_tasks = {}
        self.current_task_id = None
        self.gpu_in_use = {}
        self._queue_lock = threading.RLock()
        self.last_schedule_time = 0
        self.schedule_interval = 2.0
        # max_concurrent_gpus=0 means use all available GPUs
        self.max_concurrent_gpus = max_concurrent_gpus

    def run(self):
        self.scheduler_started.emit()
        last_check = time.time()
        while self._is_running and not self._stop_event.is_set():
            try:
                now = time.time()
                if now - last_check >= 1.0:
                    with self._queue_lock:
                        self.check_completed_tasks()
                        if now - self.last_schedule_time >= self.schedule_interval:
                            self.schedule_next_task()
                    last_check = now
                time.sleep(0.5)
            except Exception as e:
                logger.warning("Scheduler loop error: %s", e)
                time.sleep(2)
        self.scheduler_stopped.emit()

    def schedule_next_task(self):
        if not self.waiting_tasks:
            return
        total_gpus = GPUManager.get_available_gpus()
        locked = GPUManager._locked_gpus
        limit = (
            self.max_concurrent_gpus
            if self.max_concurrent_gpus > 0
            else max(0, total_gpus - len(locked))
        )
        busy_gpus = set(self.gpu_in_use.values())
        if len(busy_gpus) >= limit:
            return
        for task_info in self.waiting_tasks[:]:
            task_id, config, gpu_id = task_info
            # 处理"自动选择"：调度时实时查询最低使用率 GPU
            if gpu_id == -1:
                gpu_id = self._pick_best_gpu(total_gpus, locked, busy_gpus)
                if gpu_id < 0:
                    # 没有可用 GPU，跳过此任务等下一轮
                    continue
                # 更新 task_info 中的 gpu_id
                idx = self.waiting_tasks.index(task_info)
                self.waiting_tasks[idx] = (task_id, config, gpu_id)
            if gpu_id in busy_gpus or gpu_id in locked:
                continue
            self.gpu_in_use[task_id] = gpu_id
            self.current_task_id = task_id
            self.waiting_tasks.remove(task_info)
            self.last_schedule_time = time.time()
            self.task_ready.emit(task_id, gpu_id)
            break

    @staticmethod
    def _pick_best_gpu(total_gpus, locked, busy_gpus):
        """实时查询 GPU 使用率，返回使用率最低的可用 GPU 索引。
        没有可用 GPU 时返回 -1。"""
        try:
            usages, _, _, _, _ = GPUManager.get_all_gpu_info()
            if not usages:
                usages = GPUManager.get_gpu_usage() or [0]
            candidates = [
                (u, i) for i, u in enumerate(usages)
                if i not in locked and i not in busy_gpus
            ]
            if not candidates:
                return -1
            return min(candidates, key=lambda x: x[0])[1]
        except (ValueError, IndexError):
            # 回退：选第一个未被占用且未锁定的 GPU
            for i in range(total_gpus):
                if i not in locked and i not in busy_gpus:
                    return i
            return -1

    def release_task_gpu(self, task_id):
        """外部调用：立即释放任务占用的 GPU（stop_task 时同步调用）"""
        with self._queue_lock:
            self.gpu_in_use.pop(task_id, None)
            if self.current_task_id == task_id:
                self.current_task_id = None

    def check_completed_tasks(self):
        completed = []
        for tid, thread in list(self.running_tasks.items()):
            if not thread.isRunning():
                completed.append(tid)
        for tid in completed:
            if tid in self.running_tasks:
                del self.running_tasks[tid]
            if tid in self.gpu_in_use:
                del self.gpu_in_use[tid]
            if tid == self.current_task_id:
                self.current_task_id = None

    def add_task(self, task_id, config, gpu_id=0):
        with self._queue_lock:
            self.waiting_tasks.append((task_id, config, gpu_id))

    def stop(self):
        self._is_running = False
        self._stop_event.set()
        for tid, thread in list(self.running_tasks.items()):
            try:
                thread.stop()
            except Exception as e:
                logger.warning("Error stopping task thread %s: %s", tid, e)
        with self._queue_lock:
            self.gpu_in_use.clear()
            self.waiting_tasks.clear()
            self.current_task_id = None
        if self.isRunning():
            self.wait(5000)
            if self.isRunning():
                logger.warning("Scheduler thread did not exit within 5s")
        logger.info("Scheduler stopped")
