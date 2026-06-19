"""
工具函数：控制台窗口隐藏、subprocess 的 startupinfo / creationflags。
"""
import sys
import ctypes
import subprocess


class ConsoleHider:
    @staticmethod
    def hide_console():
        if sys.platform == 'win32':
            try:
                kernel32 = ctypes.WinDLL('kernel32')
                user32 = ctypes.WinDLL('user32')
                hWnd = kernel32.GetConsoleWindow()
                if hWnd:
                    user32.ShowWindow(hWnd, 0)
                    return True
            except Exception:
                pass
        return False

    @staticmethod
    def get_subprocess_startupinfo():
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            return startupinfo
        return None

    @staticmethod
    def get_subprocess_creationflags():
        if sys.platform == 'win32':
            return subprocess.CREATE_NO_WINDOW
        return 0
