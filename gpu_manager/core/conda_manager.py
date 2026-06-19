"""
Conda 环境管理：扫描 conda 环境、定位 Python 可执行文件。
"""
import os
import sys
import json
import threading
import subprocess

from .utils import ConsoleHider
from .logger import get_logger

logger = get_logger('conda_manager')


class CondaManager:
    _conda_path_cache = None
    _envs_cache = None
    _envs_lock = threading.Lock()

    @staticmethod
    def _find_conda_executable():
        if 'CONDA_EXE' in os.environ:
            conda_exe = os.environ['CONDA_EXE']
            if os.path.exists(conda_exe):
                return conda_exe
        path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        for path_dir in path_dirs:
            conda_exe = os.path.join(path_dir, 'conda.exe')
            if os.path.exists(conda_exe):
                return conda_exe
            conda_bat = os.path.join(path_dir, 'conda.bat')
            if os.path.exists(conda_bat):
                return conda_bat
        common = [
            os.path.expanduser("~/anaconda3/Scripts/conda.exe"),
            os.path.expanduser("~/miniconda3/Scripts/conda.exe"),
            "C:/ProgramData/Anaconda3/Scripts/conda.exe",
        ]
        for loc in common:
            if os.path.exists(loc):
                return loc
        return None

    @staticmethod
    def _run_conda_command(args):
        startupinfo = ConsoleHider.get_subprocess_startupinfo()
        creationflags = ConsoleHider.get_subprocess_creationflags()
        try:
            result = subprocess.run(
                ['conda'] + args, capture_output=True, text=True, shell=True,
                startupinfo=startupinfo, creationflags=creationflags)
            if result.returncode == 0:
                return result.stdout
        except FileNotFoundError:
            logger.debug("'conda' not found in PATH")
        except OSError as e:
            logger.warning("conda command I/O error: %s", e)
        conda_exe = CondaManager._find_conda_executable()
        if conda_exe:
            try:
                result = subprocess.run(
                    [conda_exe] + args, capture_output=True, text=True, shell=True,
                    startupinfo=startupinfo, creationflags=creationflags)
                if result.returncode == 0:
                    return result.stdout
            except FileNotFoundError:
                logger.warning("Conda executable not found: %s", conda_exe)
            except OSError as e:
                logger.warning("Conda executable I/O error: %s", e)
        return None

    @staticmethod
    def get_conda_environments():
        with CondaManager._envs_lock:
            if CondaManager._envs_cache:
                return CondaManager._envs_cache.copy()
        envs = []
        output = CondaManager._run_conda_command(['env', 'list', '--json'])
        if output:
            try:
                env_data = json.loads(output)
                for env_path in env_data.get("envs", []):
                    env_name = os.path.basename(env_path)
                    if env_path != env_data.get("conda_prefix"):
                        envs.append({'name': env_name, 'path': env_path})
            except json.JSONDecodeError as e:
                logger.warning("Conda env list JSON parse error: %s", e)
        base_env = {'name': 'base', 'path': sys.prefix}
        if base_env not in envs:
            envs.insert(0, base_env)
        with CondaManager._envs_lock:
            CondaManager._envs_cache = envs
        return envs.copy()

    @staticmethod
    def get_python_executable(env_name='base'):
        envs = CondaManager.get_conda_environments()
        for env in envs:
            if env['name'] == env_name:
                if sys.platform == 'win32':
                    python_exe = os.path.join(env['path'], 'python.exe')
                else:
                    python_exe = os.path.join(env['path'], 'bin', 'python')
                if os.path.exists(python_exe):
                    return python_exe
                else:
                    raise FileNotFoundError(
                        f"Python executable not found in environment '{env_name}': {python_exe}")
        raise FileNotFoundError(
            f"Conda environment '{env_name}' not found. "
            f"Available: {[e['name'] for e in envs]}")
