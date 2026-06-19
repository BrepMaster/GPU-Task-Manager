"""
任务执行线程：运行训练脚本，解析进度输出，管理子进程生命周期。
"""
import os
import sys
import re
import time
import threading
import subprocess

import psutil
from PyQt5.QtCore import QThread, pyqtSignal

from .utils import ConsoleHider
from .conda_manager import CondaManager
from .logger import get_logger
from .models import TaskConfig, ProgressInfo

logger = get_logger('task_thread')


class TaskThread(QThread):
    task_finished = pyqtSignal(int, str, str)
    task_output = pyqtSignal(int, str)
    task_progress = pyqtSignal(int, object)

    def __init__(self, task_id, config: TaskConfig, gpu_id=0):
        super().__init__()
        self.task_id = task_id
        self.config = config
        self.gpu_id = gpu_id
        self._is_running = True
        self._stop_event = threading.Event()
        self.process = None
        self.log_lines = []
        self.max_log_lines = 500
        self.progress_info = ProgressInfo(
            total_epochs=config.max_epochs,
            status_text="准备中",
        )
        self.last_progress_update = 0
        self.progress_update_interval = 2.0
        self._has_epoch_progress = False  # 是否曾匹配到 epoch 级别进度

    def run(self):
        try:
            python_exe = CondaManager.get_python_executable(self.config.env_name)
            script_path = self.config.script_path
            work_dir = self.config.work_dir
            if not os.path.exists(python_exe):
                self.task_output.emit(
                    self.task_id,
                    f"❌ Python解释器不存在: {python_exe}")
                self.task_finished.emit(
                    self.task_id, "failed", "Python解释器不存在")
                return
            if not script_path or not os.path.exists(script_path):
                self.task_output.emit(
                    self.task_id, f"❌ 脚本文件不存在: {script_path}")
                self.task_finished.emit(
                    self.task_id, "failed", "脚本文件不存在")
                return
            if not work_dir or not os.path.exists(work_dir):
                work_dir = os.path.dirname(os.path.abspath(script_path))

            gpu_param = (
                f'{self.gpu_id},' if self.gpu_id == 0 else str(self.gpu_id)
            )
            cmd_args = [
                python_exe, script_path, 'train',
                f'--dataset={self.config.dataset}',
                f'--dataset_path={self.config.dataset_path}',
                f'--max_epochs={self.config.max_epochs}',
                f'--batch_size={self.config.batch_size}',
                f'--experiment_name={self.config.experiment_name}',
                f'--gpus={gpu_param}',
            ]
            cmd_display = ' '.join(cmd_args)
            self.task_output.emit(self.task_id, f"🚀 启动: {cmd_display}")

            env = os.environ.copy()
            env['CUDA_VISIBLE_DEVICES'] = str(self.gpu_id)
            creationflags = ConsoleHider.get_subprocess_creationflags()
            startupinfo = ConsoleHider.get_subprocess_startupinfo()

            self.process = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=False,
                creationflags=creationflags,
                startupinfo=startupinfo,
                start_new_session=(sys.platform != 'win32'),
                env=env,
                cwd=(work_dir if work_dir and os.path.exists(work_dir) else None),
            )
            self._monitor_process()
        except FileNotFoundError as e:
            logger.error("Task %s missing dependency: %s", self.task_id, e)
            self.task_output.emit(self.task_id, f"❌ 依赖缺失: {e}")
            self.task_finished.emit(self.task_id, "failed", str(e))
        except (OSError, RuntimeError, ValueError) as e:
            logger.error("Task %s execution error: %s", self.task_id, e)
            self.task_output.emit(self.task_id, f"❌ 执行异常: {e}")
            self.task_finished.emit(self.task_id, "failed", str(e))

    def _monitor_process(self):
        buffer = []
        buffer_size = 20
        last_flush = time.time()
        while (self._is_running
               and not self._stop_event.is_set()
               and self.process.poll() is None):
            try:
                raw_line = self.process.stdout.readline()
                if raw_line:
                    line = None
                    try:
                        line = raw_line.decode('utf-8', errors='replace').rstrip()
                    except UnicodeDecodeError as e:
                        logger.debug("UTF-8 decode error: %s", e)
                    if line:
                        if len(self.log_lines) >= self.max_log_lines:
                            self.log_lines = self.log_lines[-300:]
                        self.log_lines.append(line)
                        self.parse_output_line(line)
                        buffer.append(line)
                        now = time.time()
                        if (len(buffer) >= buffer_size
                                or (now - last_flush >= 1.0)):
                            if buffer:
                                self.task_output.emit(
                                    self.task_id, '\n'.join(buffer))
                                buffer.clear()
                            last_flush = now
                time.sleep(0.05)
            except OSError as e:
                logger.warning("Monitor loop I/O error: %s", e)
                break
        if buffer:
            self.task_output.emit(self.task_id, '\n'.join(buffer))

        rc = self.process.returncode
        if rc == 0:
            self.task_output.emit(self.task_id, "✅ 任务完成")
            self.progress_info.status_text = "已完成"
            self.progress_info.progress_percent = 100.0
            self.task_progress.emit(self.task_id, self.progress_info.copy())
            self.task_finished.emit(
                self.task_id, "completed", "任务成功完成")
        else:
            self.task_output.emit(self.task_id, f"❌ 退出码: {rc}")
            self.progress_info.status_text = f"失败(退出码:{rc})"
            self.task_progress.emit(self.task_id, self.progress_info.copy())
            self.task_finished.emit(
                self.task_id, "failed", f"退出码: {rc}")

    # ── 进度解析正则（预编译，支持多种框架） ────────────────────────
    _RE_EPOCH_STD = re.compile(r'Epoch\s+(\d+)\s*/\s*(\d+)')
    _RE_EPOCH_LIGHTNING = re.compile(r'Epoch\s+(\d+):\s*(\d+)%')
    _RE_HF_EPOCH = re.compile(r"'epoch'\s*:\s*([\d.]+)")
    _RE_HF_LOSS = re.compile(r"'loss'\s*:\s*([\d.]+)")
    _RE_STEP = re.compile(r'(?:step|Step|iter)\s*(\d+)[/\s]+(\d+)')
    _RE_FASTAI_EPOCH = re.compile(r'^\s*(\d+)\s+\d+\.\d+')  # fastai table row

    def parse_output_line(self, line):
        """解析训练输出行，支持多种框架格式。"""
        updated = False

        # 1. 标准格式: Epoch 5/200
        m = self._RE_EPOCH_STD.search(line)
        if m:
            epoch = int(m.group(1))
            total = int(m.group(2))
            self.progress_info.epoch = epoch
            self.progress_info.total_epochs = total
            self.progress_info.progress_percent = (
                (epoch / total * 100) if total > 0 else 0)
            self.progress_info.status_text = f"Epoch {epoch}/{total}"
            self._has_epoch_progress = True
            updated = True

        # 2. PyTorch Lightning: Epoch 12: 100%|████| 1234/1234
        #    进度条只跟 epoch/total 走，不用 batch 内的百分比
        if not updated:
            m = self._RE_EPOCH_LIGHTNING.search(line)
            if m:
                epoch = int(m.group(1))
                self.progress_info.epoch = epoch
                total = self.progress_info.total_epochs
                if total > 0:
                    self.progress_info.progress_percent = (
                        epoch / total * 100)
                self.progress_info.status_text = f"Epoch {epoch}/{total}"
                self._has_epoch_progress = True
                updated = True

        # 3. HuggingFace: {'epoch': 1.0, 'loss': 0.123, ...}
        if not updated:
            m = self._RE_HF_EPOCH.search(line)
            if m:
                epoch_val = float(m.group(1))
                total = self.progress_info.total_epochs
                if total > 0:
                    pct = min(epoch_val / total * 100, 100.0)
                    self.progress_info.progress_percent = pct
                    self.progress_info.status_text = f"Epoch {epoch_val:.1f}/{total}"
                else:
                    self.progress_info.status_text = f"Epoch {epoch_val:.1f}"
                self.progress_info.epoch = int(epoch_val)
                self._has_epoch_progress = True
                # 如果有 loss 信息，附加到状态
                lm = self._RE_HF_LOSS.search(line)
                if lm:
                    loss = float(lm.group(1))
                    self.progress_info.status_text += f" loss={loss:.4f}"
                updated = True

        # 4. 通用 step 格式: step 500/10000 or Step 500/10000
        #    仅当从未匹配到 epoch 级别进度时，才驱动进度条（fallback）
        if not updated:
            m = self._RE_STEP.search(line)
            if m:
                step = int(m.group(1))
                total = int(m.group(2))
                self.progress_info.status_text = f"Step {step}/{total}"
                if not self._has_epoch_progress and total > 0:
                    # step 作为 fallback 驱动进度条
                    pct = min(step / total * 100, 100.0)
                    self.progress_info.progress_percent = pct
                    updated = True

        # 5. fastai 表格行: "  1   0.123456  0.234567  00:12"
        if not updated:
            m = self._RE_FASTAI_EPOCH.search(line)
            if m:
                epoch = int(m.group(1))
                self.progress_info.epoch = epoch
                total = self.progress_info.total_epochs
                if total > 0:
                    pct = (epoch / total * 100)
                    self.progress_info.progress_percent = pct
                self.progress_info.status_text = f"Epoch {epoch}/{total}"
                self._has_epoch_progress = True
                updated = True

        # 节流发送信号
        if updated:
            now = time.time()
            if now - self.last_progress_update > self.progress_update_interval:
                self.task_progress.emit(
                    self.task_id, self.progress_info.copy())
                self.last_progress_update = now

    def stop(self):
        self._is_running = False
        self._stop_event.set()
        if self.process:
            try:
                parent = psutil.Process(self.process.pid)
                children = parent.children(recursive=True)
                for child in children:
                    child.terminate()
                parent.terminate()
                gone, alive = psutil.wait_procs(
                    children + [parent], timeout=3)
                for p in alive:
                    p.kill()
            except psutil.NoSuchProcess:
                logger.debug("Process %s already exited", self.process.pid)
            except (psutil.AccessDenied, OSError) as e:
                logger.warning("Error terminating process: %s", e)
