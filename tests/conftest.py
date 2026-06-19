"""
pytest 配置：将项目根目录加入 sys.path，便于直接 pytest 运行。
"""
import sys
import os

# 让 `from gpu_manager.core.models import ...` 可以在测试里直接使用
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
