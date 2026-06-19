"""
GPU 信息获取：封装 nvidia-smi 调用，带缓存避免高频阻塞。
"""
import time
import subprocess

from .utils import ConsoleHider
from .logger import get_logger

logger = get_logger('gpu_manager')


class GPUManager:
    _cached_all_info = None
    _cache_time = 0
    CACHE_TTL = 4.0  # 缓存 4 秒
    _locked_gpus = set()  # 被锁定的 GPU 索引

    @staticmethod
    def _run_nvidia_smi(args):
        try:
            startupinfo = ConsoleHider.get_subprocess_startupinfo()
            creationflags = ConsoleHider.get_subprocess_creationflags()
            result = subprocess.run(
                ['nvidia-smi'] + args,
                capture_output=True, text=True, shell=True,
                startupinfo=startupinfo, creationflags=creationflags)
            if result.returncode == 0:
                return result.stdout
        except FileNotFoundError:
            logger.warning("nvidia-smi not found")
        except OSError as e:
            logger.warning("nvidia-smi I/O error: %s", e)
        return None

    @staticmethod
    def get_available_gpus():
        output = GPUManager._run_nvidia_smi(['-L'])
        if output:
            lines = output.strip().split('\n')
            gpu_count = len([line for line in lines if 'GPU' in line])
            return gpu_count if gpu_count > 0 else 1
        return 1

    @classmethod
    def lock_gpu(cls, gpu_id):
        cls._locked_gpus.add(gpu_id)

    @classmethod
    def unlock_gpu(cls, gpu_id):
        cls._locked_gpus.discard(gpu_id)

    @classmethod
    def is_gpu_locked(cls, gpu_id):
        return gpu_id in cls._locked_gpus

    @classmethod
    def get_available_gpus_unlocked(cls):
        """返回未被锁定的 GPU 数量"""
        total = cls.get_available_gpus()
        return max(0, total - len(cls._locked_gpus))

    @staticmethod
    def get_gpu_usage():
        output = GPUManager._run_nvidia_smi([
            '--query-gpu=utilization.gpu', '--format=csv,noheader'])
        if output:
            usage = []
            for u in output.strip().split('\n'):
                if u.strip():
                    try:
                        usage.append(int(u.replace('%', '').strip()))
                    except ValueError:
                        usage.append(0)
            return usage if usage else [0]
        return [0]

    @staticmethod
    def get_gpu_memory_usage():
        output = GPUManager._run_nvidia_smi([
            '--query-gpu=memory.used,memory.total',
            '--format=csv,noheader,nounits'])
        if output:
            memory_info = []
            for line in output.strip().split('\n'):
                if line.strip():
                    try:
                        used, total = map(int, line.split(','))
                        memory_info.append((used, total))
                    except ValueError:
                        memory_info.append((0, 1))
            return memory_info
        return [(0, 1)]

    @staticmethod
    def get_gpu_names():
        output = GPUManager._run_nvidia_smi([
            '--query-gpu=name', '--format=csv,noheader'])
        if output:
            return [x.strip() for x in output.strip().split('\n') if x.strip()]
        return []

    @staticmethod
    def get_gpu_temperature():
        output = GPUManager._run_nvidia_smi([
            '--query-gpu=temperature.gpu', '--format=csv,noheader'])
        if output:
            temps = []
            for x in output.strip().split('\n'):
                if x.strip():
                    try:
                        temps.append(int(x.strip()))
                    except ValueError:
                        temps.append(0)
            return temps
        return []

    @staticmethod
    def get_gpu_power():
        output = GPUManager._run_nvidia_smi([
            '--query-gpu=power.draw,power.limit',
            '--format=csv,noheader,nounits'])
        if output:
            power_info = []
            for line in output.strip().split('\n'):
                if line.strip():
                    try:
                        parts = line.split(',')
                        draw = float(parts[0].strip()) if len(parts) > 0 else 0.0
                        limit = float(parts[1].strip()) if len(parts) > 1 else 0.0
                        power_info.append((draw, limit))
                    except ValueError:
                        power_info.append((0.0, 0.0))
            return power_info
        return []

    @classmethod
    def get_all_gpu_info(cls):
        """一次 nvidia-smi 调用获取所有 GPU 信息，带缓存避免阻塞 UI"""
        now = time.time()
        if cls._cached_all_info is not None and (now - cls._cache_time) < cls.CACHE_TTL:
            return cls._cached_all_info

        output = cls._run_nvidia_smi([
            '--query-gpu=utilization.gpu,memory.used,memory.total,'
            'temperature.gpu,power.draw,power.limit,name',
            '--format=csv,noheader,nounits'])
        if not output:
            result = ([], [], [], [], [])
            cls._cached_all_info = result
            cls._cache_time = now
            return result

        usages, memories, temps, powers, names = [], [], [], [], []
        for line in output.strip().split('\n'):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(',')]
            try:
                usages.append(int(parts[0]) if len(parts) > 0 else 0)
                mem_used = int(parts[1]) if len(parts) > 1 else 0
                mem_total = int(parts[2]) if len(parts) > 2 else 0
                memories.append((mem_used, mem_total))
                temps.append(int(parts[3]) if len(parts) > 3 else 0)
                draw = float(parts[4]) if len(parts) > 4 else 0.0
                limit = float(parts[5]) if len(parts) > 5 else 0.0
                powers.append((draw, limit))
                names.append(parts[6] if len(parts) > 6 else "GPU")
            except (ValueError, IndexError) as e:
                logger.debug("GPU info parse error: %s", e)
        result = (usages, memories, temps, powers, names)
        cls._cached_all_info = result
        cls._cache_time = now
        return result
