# -*- mode: python ; coding: utf-8 -*-
"""
GPU 任务管理器 — PyInstaller 打包配置 (onedir 模式)
用法: pyinstaller build.spec
产出: dist/GPU任务管理器/ 文件夹（内含 exe + 依赖 DLL，启动快）
"""

block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'gpu_manager',
        'gpu_manager.core',
        'gpu_manager.core.config',
        'gpu_manager.core.conda_manager',
        'gpu_manager.core.gpu_manager',
        'gpu_manager.core.logger',
        'gpu_manager.core.models',
        'gpu_manager.core.scheduler',
        'gpu_manager.core.task_thread',
        'gpu_manager.core.utils',
        'gpu_manager.ui',
        'gpu_manager.ui.main_window',
        'gpu_manager.ui.main_window.base',
        'gpu_manager.ui.main_window.task_mgmt',
        'gpu_manager.ui.main_window.task_ops',
        'gpu_manager.ui.main_window.gpu_ops',
        'gpu_manager.ui.main_window.log_cfg',
        'gpu_manager.ui.dialogs',
        'gpu_manager.ui.gpu_card',
        'gpu_manager.ui.ops_widget',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'pandas',
        'tkinter', '_tkinter',
        'unittest', 'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,       # onedir: 二进制放外部文件夹
    name='GPU任务管理器',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,               # 不弹控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GPU任务管理器',
)
