"""
GPU 任务管理器入口。
用法：python -m gpu_manager
"""
import sys
from PyQt5.QtWidgets import QApplication

from .core import ConsoleHider
from .ui import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    ConsoleHider.hide_console()
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
