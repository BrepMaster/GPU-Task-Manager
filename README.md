<p align="center">
  <h1 align="center">🌸 GPU Task Manager</h1>
  <p align="center">
    <strong>A PyQt5-based deep learning training task queue manager with multi-GPU monitoring, smart scheduling, and multi-framework progress parsing.</strong>
  </p>
  <p align="center">
    <a href="#gpu-task-manager">English</a> | <a href="#gpu-任务管理器">中文</a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.8%2B-blue" alt="Python">
    <img src="https://img.shields.io/badge/PyQt5-5.15%2B-green" alt="PyQt5">
    <img src="https://img.shields.io/badge/license-MIT-orange" alt="License">
    <img src="https://img.shields.io/badge/version-2.1.0-purple" alt="Version">
  </p>
</p>

---

# GPU Task Manager

A desktop application built with PyQt5 for managing deep learning training task queues. It monitors all NVIDIA GPUs in real time, automatically schedules tasks to the least-loaded GPU, and parses training progress from multiple frameworks — all in a clean, modern interface with light/dark themes.

## Screenshots
![System Screenshot](https://github.com/BrepMaster/GPU Task Manager/raw/main/1.png)
## Features

**Real-time GPU Monitoring** — Automatically detects all NVIDIA GPUs and displays utilization, VRAM, temperature, and power consumption. Refreshes every 5 seconds. Individual GPUs can be locked to exclude them from auto-scheduling.

**Task Queue Management** — Add, delete, clone, retry, drag-to-reorder, and clear tasks. A right-click context menu provides full control. Keyboard shortcuts: `Delete`, `Ctrl+D` (clone), `Ctrl+R` (retry).

**Smart Scheduling** — Automatically assigns each task to the GPU with the lowest utilization. Supports scheduled start times (delayed launch). GPU occupation state stays in sync with the scheduler in real time.

**Multi-Framework Progress Parsing** — Five built-in regex patterns cover standard PyTorch (`Epoch X/Y`), PyTorch Lightning, HuggingFace Transformers, fastai, and generic step-based formats. The progress bar color shifts from red → light green → dark green as completion increases.

**Training Duration Display** — Shows real-time `HH:MM:SS` elapsed time for each task, auto-refreshing every second for running tasks.

**Log System** — Filter logs by task source, keyword highlighting, auto-scroll toggle, 150ms throttling + 3,000-line cap to keep the UI responsive. Export logs as plain text.

**Task Detail Dialog** — Single-click a task row to open a non-modal detail window (does not block the main UI). Clicking the same task again just activates the existing window.

**Persistence & Import/Export** — Configuration is auto-saved and restored. Task history archives the last 200 completed/failed/stopped tasks. Task groups can be exported as JSON and shared with others.

**Theme Switching** — One-click toggle between light and dark themes. Window position and size are remembered across sessions.

**Conda Environment Support** — Automatically scans available conda environments so you can assign different environments to different tasks.

## Requirements

| Requirement | Details |
|---|---|
| Python | >= 3.8 |
| PyQt5 | >= 5.15 |
| psutil | >= 5.8 |
| NVIDIA GPU | Required for GPU monitoring (via `nvidia-smi`) |

## Usage

### Adding a Task

1. Enter the training script path (e.g., `train.py`)
2. Select the working directory (where your script lives)
3. Choose a Conda environment (optional)
4. Set the number of GPUs required
5. Optionally set a scheduled start time
6. Click **Add**

The scheduler will automatically pick the least-utilized GPU and start the task when it's its turn.

### GPU Monitoring

The GPU panel at the top shows all detected NVIDIA GPUs with real-time stats. Click the 🔒 button on any GPU card to lock it — the scheduler will skip locked GPUs during auto-assignment.

### Task Operations

| Action | How |
|---|---|
| Delete | Select + `Delete` key, or right-click → Delete |
| Clone | Select + `Ctrl+D`, or right-click → Clone |
| Retry | Select failed/stopped task + `Ctrl+R`, or right-click → Retry |
| Reorder | Drag and drop rows in the task table |
| Details | Single-click any task row |
| View Logs | Select a task and check the log panel below |

### Import / Export

Use the toolbar buttons to export your current task queue as a JSON file, or import a previously saved task group. Handy for sharing training configurations with colleagues.

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Delete` | Delete selected task |
| `Ctrl+D` | Clone selected task |
| `Ctrl+R` | Retry selected task (failed/stopped) |

## Architecture

The main window uses a **Mixin pattern** — split into 5 single-responsibility mixins composed into `MainWindow`:

| Mixin | Responsibility |
|---|---|
| `TaskMixin` | Task CRUD, table rendering, statistics |
| `TaskOpsMixin` | Scheduler control, start/stop, drag-drop, context menu, shortcuts |
| `GPUMixin` | GPU monitoring refresh, Conda environment async loading |
| `LogCfgMixin` | Log filtering/highlighting, config persistence, file dialogs, import/export |

The core layer and UI layer are fully decoupled. Both `TaskScheduler` and `TaskThread` are independent `QThread` subclasses that communicate with the main window via Qt signals.

## Project Structure

```
gpu_manager/
├── core/                   # Core logic
│   ├── config.py           # Theme colors & global config
│   ├── conda_manager.py    # Conda environment scanner
│   ├── gpu_manager.py      # GPU info via nvidia-smi
│   ├── logger.py           # Logging module
│   ├── models.py           # Data models (dataclass + Enum)
│   ├── scheduler.py        # Task scheduler (QThread)
│   ├── task_thread.py      # Task execution thread + progress parser
│   └── utils.py            # Utility functions
├── ui/                     # UI components
│   ├── main_window/        # Main window (mixin architecture)
│   │   ├── base.py         # Skeleton, stylesheets, theme switching
│   │   ├── task_mgmt.py    # Task CRUD, table rendering
│   │   ├── task_ops.py     # Scheduler, drag-drop, context menu
│   │   ├── gpu_ops.py      # GPU monitoring, Conda env loading
│   │   ├── log_cfg.py      # Log filtering, config persistence
│   │   └── __init__.py     # Mixin composition
│   ├── dialogs.py          # Edit / detail dialogs
│   ├── gpu_card.py         # GPU card widget
│   └── ops_widget.py       # Action buttons + progress bar
├── __init__.py
└── __main__.py             # python -m entry point
tests/                      # 32 pytest unit tests
run.py                      # Application entry point
build.spec                  # PyInstaller packaging config
build.bat                   # One-click build script
pyproject.toml              # Project metadata & dependencies
```

## License

This project is licensed under the [MIT License](LICENSE).

---

# GPU 任务管理器

基于 PyQt5 的桌面应用，用于管理深度学习训练任务队列。实时监控所有 NVIDIA GPU，自动将任务调度到负载最低的 GPU，支持多种框架的训练进度解析——浅色/深色主题，界面简洁现代。

## 截图

## 功能一览

**GPU 实时监控** — 自动检测所有 NVIDIA GPU，显示使用率、显存、温度、功耗，5 秒刷新。支持单卡锁定，调度器会自动跳过已锁定的 GPU。

**任务队列管理** — 添加、删除、克隆、重试、拖拽排序、清空队列。右键菜单提供完整操作。快捷键：`Delete`（删除）、`Ctrl+D`（克隆）、`Ctrl+R`（重试）。

**智能调度** — 自动将任务分配到使用率最低的 GPU。支持前置等待时间（定时启动）。GPU 占用状态与调度器实时同步。

**多框架进度解析** — 内置 5 种正则模式，覆盖标准 PyTorch（`Epoch X/Y`）、PyTorch Lightning、HuggingFace Transformers、fastai、通用 step 格式。进度条颜色随完成度从红 → 浅绿 → 深绿渐变。

**训练时长显示** — 实时显示每个任务的训练时长（`HH:MM:SS`），运行中任务每秒自动刷新。

**日志系统** — 按任务来源筛选、关键字高亮、自动滚动开关、150ms 节流 + 3000 条上限防止 UI 卡顿。支持导出纯文本日志。

**任务详情弹窗** — 单击任务行即弹出非模态详情窗口（不阻塞主界面），同一任务再次点击仅激活已有窗口。

**持久化与导入导出** — 配置自动保存和恢复。任务历史归档最近 200 条已完成/失败/已停止的任务。任务组可导出为 JSON 并分享给他人。

**主题切换** — 浅色/深色主题一键切换，窗口位置和大小跨会话自动记忆。

**Conda 环境支持** — 自动扫描可用的 Conda 环境，不同任务可指定不同环境运行。

## 环境要求

| 依赖 | 要求 |
|---|---|
| Python | >= 3.8 |
| PyQt5 | >= 5.15 |
| psutil | >= 5.8 |
| NVIDIA GPU | GPU 监控功能依赖 `nvidia-smi` |

## 使用方法

### 添加任务

1. 输入训练脚本路径（如 `train.py`）
2. 选择工作目录（脚本所在目录）
3. 选择 Conda 环境（可选）
4. 设置所需 GPU 数量
5. 可选设置定时启动时间
6. 点击 **添加**

调度器会自动选择使用率最低的 GPU，按队列顺序启动任务。

### GPU 监控

顶部 GPU 面板显示所有检测到的 NVIDIA GPU 及其实时状态。点击 GPU 卡片上的 🔒 按钮可锁定该卡——调度器在自动分配时会跳过已锁定的 GPU。

### 任务操作

| 操作 | 方式 |
|---|---|
| 删除 | 选中 + `Delete` 键，或右键 → 删除 |
| 克隆 | 选中 + `Ctrl+D`，或右键 → 克隆 |
| 重试 | 选中失败/已停止任务 + `Ctrl+R`，或右键 → 重试 |
| 排序 | 在任务表格中拖拽行 |
| 详情 | 单击任意任务行 |
| 查看日志 | 选中任务后查看下方日志面板 |

### 导入 / 导出

使用工具栏按钮将当前任务队列导出为 JSON 文件，或导入之前保存的任务组。方便与同事分享训练配置。

## 快捷键

| 快捷键 | 功能 |
|---|---|
| `Delete` | 删除选中任务 |
| `Ctrl+D` | 克隆选中任务 |
| `Ctrl+R` | 重试选中任务（失败/已停止） |

## 架构说明

主窗口采用 **Mixin 模式**，拆分为 5 个职责单一的混入类，组合到 `MainWindow`：

| 混入类 | 职责 |
|---|---|
| `TaskMixin` | 任务增删查、表格渲染、统计 |
| `TaskOpsMixin` | 调度器控制、启停、拖拽排序、右键菜单、快捷键 |
| `GPUMixin` | GPU 监控刷新、Conda 环境异步加载 |
| `LogCfgMixin` | 日志筛选/高亮、配置持久化、文件对话框、导入导出 |

核心层与 UI 层完全解耦。`TaskScheduler` 和 `TaskThread` 均为独立的 `QThread` 子类，通过 Qt 信号与主窗口通信。

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
