"""
MainWindow 的 GPU 监控相关方法：加载 GPU 信息、定时刷新、异步加载 Conda 环境。
"""
from PyQt5.QtCore import QThread, pyqtSignal

from ...core.conda_manager import CondaManager
from ...core.gpu_manager import GPUManager
from ...core.logger import get_logger

logger = get_logger('gpu_ops')


class _CondaEnvLoader(QThread):
    """后台线程：扫描 Conda 环境，完成后通过 envs_ready 信号回传"""
    envs_ready = pyqtSignal(list)

    def run(self):
        try:
            CondaManager._envs_cache = None
            envs = CondaManager.get_conda_environments()
            self.envs_ready.emit(envs or [])
        except OSError as e:
            logger.warning("Conda env scan failed: %s", e)
            self.envs_ready.emit([])


class _GPUInfoWorker(QThread):
    """后台线程：调用 nvidia-smi 获取 GPU 信息，避免阻塞 UI"""
    info_ready = pyqtSignal(tuple)  # (usages, memories, temps, powers, names)

    def run(self):
        try:
            result = GPUManager.get_all_gpu_info()
            self.info_ready.emit(result)
        except Exception as e:
            logger.warning("GPU info worker error: %s", e)
            self.info_ready.emit(([], [], [], [], []))


class GPUMixin:
    """GPU / Conda 相关的方法"""

    def load_gpu_info(self):
        try:
            gpu_count = GPUManager.get_available_gpus()
            gpu_names = GPUManager.get_gpu_names()
            self.gpu_combo.clear()
            self.gpu_combo.addItem("自动选择（最低使用率）", -1)
            for i in range(gpu_count):
                name = gpu_names[i] if i < len(gpu_names) else f"GPU {i}"
                self.gpu_combo.addItem(f"GPU {i} ({name})", i)
            self.add_to_log("系统", f"检测到 {gpu_count} 个GPU")
        except Exception as e:
            self.add_to_log("错误", f"GPU检测失败: {str(e)}")

    def load_conda_envs(self):
        """异步加载 conda 环境：后台扫描，主线程不阻塞"""
        try:
            # 清理旧的 loader
            if hasattr(self, '_conda_loader') and self._conda_loader:
                try:
                    self._conda_loader.envs_ready.disconnect(
                        self._on_conda_envs_loaded)
                except (RuntimeError, TypeError):
                    pass
                self._conda_loader.deleteLater()
            self.conda_env_combo.clear()
            self.conda_env_combo.addItem("⏳ 正在扫描 Conda 环境…")
            self.conda_env_combo.setEnabled(False)
            self.add_to_log("系统", "正在后台扫描 Conda 环境…")
            self._conda_loader = _CondaEnvLoader()
            self._conda_loader.envs_ready.connect(self._on_conda_envs_loaded)
            self._conda_loader.start()
        except Exception as e:
            self.conda_env_combo.setEnabled(True)
            self.conda_env_combo.clear()
            self.conda_env_combo.addItem("base")
            self.add_to_log("错误", f"Conda环境加载失败: {str(e)}")

    def _on_conda_envs_loaded(self, envs):
        try:
            self.conda_env_combo.setEnabled(True)
            self.conda_env_combo.clear()
            for env in envs:
                self.conda_env_combo.addItem(env['name'])
            self.add_to_log("系统", f"已加载 {len(envs)} 个Conda环境")
        except Exception as e:
            self.add_to_log("错误", f"Conda环境填充失败: {str(e)}")

    def _on_gpu_lock_toggle(self, gpu_id, locked):
        """GPU 卡片上的锁定按钮回调，同步到 GPUManager"""
        if locked:
            GPUManager.lock_gpu(gpu_id)
            self.add_to_log("系统", f"GPU {gpu_id} 已锁定，调度器将跳过")
        else:
            GPUManager.unlock_gpu(gpu_id)
            self.add_to_log("系统", f"GPU {gpu_id} 已解锁")

    def refresh_gpu_info(self):
        # 防止并发：上一个 worker 还在跑就跳过
        if hasattr(self, '_gpu_worker') and self._gpu_worker.isRunning():
            return
        self._gpu_worker = _GPUInfoWorker()
        self._gpu_worker.info_ready.connect(self._on_gpu_info_ready)
        self._gpu_worker.start()

    def _on_gpu_info_ready(self, result):
        try:
            usages, memories, temps, powers, names = result
            gpu_count = (
                len(usages) if usages else GPUManager.get_available_gpus())
            if not usages:
                usages = [0] * gpu_count
                memories = [(0, 0)] * gpu_count
                temps = [0] * gpu_count
                powers = [(0, 0)] * gpu_count
                names = ["GPU"] * gpu_count

            parts = [f"共 {gpu_count} 个GPU"]
            for i in range(gpu_count):
                usage = usages[i] if i < len(usages) else 0
                parts.append(f"GPU{i}: {usage}%")
            self.gpu_info_label.setText(" | ".join(parts))

            self._gpu_cards_panel.update(
                gpu_count, usages, memories, temps, powers, names)

            if gpu_count > 0:
                usage0 = usages[0] if len(usages) > 0 else 0
                temp0 = temps[0] if len(temps) > 0 else 0
                self.status_gpu_label.setText(
                    f"GPU: {gpu_count}个 | "
                    f"GPU0使用率 {usage0}% | 温度 {temp0}°C")
        except Exception as e:
            self.gpu_info_label.setText(
                f"GPU信息获取失败: {str(e)[:50]}")
