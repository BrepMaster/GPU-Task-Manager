"""
GPU 任务管理器启动器。
直接运行：python run.py
"""
import sys
import os

# 让 python 能找到当前目录下的 gpu_manager 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication

from gpu_manager.core import ConsoleHider
from gpu_manager.ui import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    ConsoleHider.hide_console()
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
