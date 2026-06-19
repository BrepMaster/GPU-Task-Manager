"""
任务编辑 / 详情对话框。
"""
from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox,
    QPushButton, QFrame, QProgressBar,
)
from PyQt5.QtCore import Qt

from ..core.config import Colors
from ..core.models import TaskConfig, TaskStatus
from .ops_widget import _progress_colors


class TaskEditDialog(QDialog):
    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.setWindowTitle(f"编辑任务 {task.id}")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.CARD_BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 18px;
            }}
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 13px;
                background: transparent;
            }}
            QLineEdit, QComboBox, QSpinBox {{
                padding: 8px 12px;
                border: 1.5px solid {Colors.BORDER};
                border-radius: 12px;
                background-color: {Colors.BG};
                color: {Colors.TEXT_PRIMARY};
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border-color: {Colors.ACCENT};
                background-color: {Colors.CARD_BG};
            }}
            QPushButton {{
                padding: 9px 18px;
                border: none;
                border-radius: 12px;
                color: white;
                font-weight: bold;
                font-size: 13px;
            }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel(f"✏️ 编辑任务 #{self.task.id}")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: bold; "
            f"color: {Colors.ACCENT2}; background: transparent;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        cfg = self.task.config

        self.env_combo = QComboBox()
        self.env_combo.setMinimumHeight(36)
        if self.parent() and hasattr(self.parent(), 'conda_env_combo'):
            for i in range(self.parent().conda_env_combo.count()):
                self.env_combo.addItem(self.parent().conda_env_combo.itemText(i))
        else:
            self.env_combo.addItem(cfg.env_name)
        self.env_combo.setCurrentText(cfg.env_name)
        form.addRow("Conda环境:", self.env_combo)

        self.script_edit = QLineEdit(cfg.script_path)
        self.script_edit.setMinimumHeight(36)
        form.addRow("脚本路径:", self.script_edit)

        self.workdir_edit = QLineEdit(cfg.work_dir)
        self.workdir_edit.setMinimumHeight(36)
        form.addRow("工作目录:", self.workdir_edit)

        self.dataset_edit = QLineEdit(cfg.dataset)
        self.dataset_edit.setMinimumHeight(36)
        form.addRow("数据集:", self.dataset_edit)

        self.dataset_path_edit = QLineEdit(cfg.dataset_path)
        self.dataset_path_edit.setMinimumHeight(36)
        form.addRow("数据集路径:", self.dataset_path_edit)

        self.experiment_edit = QLineEdit(cfg.experiment_name)
        self.experiment_edit.setMinimumHeight(36)
        form.addRow("实验名称:", self.experiment_edit)

        self.epochs_spin = QSpinBox()
        self.epochs_spin.setMinimum(1)
        self.epochs_spin.setMaximum(100000)
        self.epochs_spin.setValue(cfg.max_epochs)
        self.epochs_spin.setMinimumHeight(36)
        form.addRow("训练轮次:", self.epochs_spin)

        self.batch_spin = QSpinBox()
        self.batch_spin.setMinimum(1)
        self.batch_spin.setMaximum(8192)
        self.batch_spin.setValue(cfg.batch_size)
        self.batch_spin.setMinimumHeight(36)
        form.addRow("批大小:", self.batch_spin)

        self.gpu_spin = QSpinBox()
        self.gpu_spin.setMinimum(-1)
        self.gpu_spin.setMaximum(7)
        self.gpu_spin.setValue(self.task.gpu_id)
        self.gpu_spin.setSpecialValueText("自动选择")
        self.gpu_spin.setMinimumHeight(36)
        form.addRow("GPU:", self.gpu_spin)

        # 前置等待
        ws = self.task.wait_seconds
        wh = QHBoxLayout()
        wh.setSpacing(4)
        self.wait_hours_spin = QSpinBox()
        self.wait_hours_spin.setRange(0, 23)
        self.wait_hours_spin.setSuffix("时")
        self.wait_hours_spin.setValue(ws // 3600)
        self.wait_hours_spin.setMinimumHeight(36)
        wh.addWidget(self.wait_hours_spin)
        self.wait_minutes_spin = QSpinBox()
        self.wait_minutes_spin.setRange(0, 59)
        self.wait_minutes_spin.setSuffix("分")
        self.wait_minutes_spin.setValue((ws % 3600) // 60)
        self.wait_minutes_spin.setMinimumHeight(36)
        wh.addWidget(self.wait_minutes_spin)
        self.wait_seconds_spin = QSpinBox()
        self.wait_seconds_spin.setRange(0, 59)
        self.wait_seconds_spin.setSuffix("秒")
        self.wait_seconds_spin.setValue(ws % 60)
        self.wait_seconds_spin.setMinimumHeight(36)
        wh.addWidget(self.wait_seconds_spin)
        form.addRow("前置等待:", wh)

        layout.addLayout(form)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {Colors.TEXT_MUTED}; color: white; }}
            QPushButton:hover {{ background-color: {Colors.TEXT_SECONDARY}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("💾 保存")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Colors.ACCENT}, stop:1 {Colors.ACCENT2});
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Colors.ACCENT2}, stop:1 {Colors.ACCENT});
            }}
        """)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def get_config(self) -> TaskConfig:
        return TaskConfig(
            env_name=self.env_combo.currentText(),
            script_path=self.script_edit.text(),
            work_dir=self.workdir_edit.text(),
            dataset=self.dataset_edit.text(),
            dataset_path=self.dataset_path_edit.text(),
            max_epochs=self.epochs_spin.value(),
            batch_size=self.batch_spin.value(),
            experiment_name=self.experiment_edit.text(),
        )

    def get_gpu_id(self):
        return self.gpu_spin.value()

    def get_wait_seconds(self):
        return (self.wait_hours_spin.value() * 3600
                + self.wait_minutes_spin.value() * 60
                + self.wait_seconds_spin.value())


class TaskDetailDialog(QWidget):
    """点击任务弹出的详情面板 — 非模态，支持实时更新"""
    _STATUS_MAP = {
        'pending': '⏳ 等待中',
        'running': '▶️ 运行中',
        'completed': '✅ 已完成',
        'failed': '❌ 失败',
        'stopped': '⏹ 已停止',
    }
    _STATUS_COLORS = {
        'pending': None,    # 用 Colors.ACCENT
        'running': None,    # 用 Colors.BLUE
        'completed': None,  # 用 Colors.GREEN
        'failed': None,     # 用 Colors.RED
        'stopped': None,    # 用 Colors.TEXT_MUTED
    }

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.setWindowTitle(f"任务 #{task.id} 详情")
        self.setMinimumWidth(520)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.CARD_BG};
            }}
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(28, 28, 28, 28)

        t = self.task
        cfg = t.config
        status_str = (t.status.value if isinstance(t.status, TaskStatus)
                      else t.status)
        status_text = self._STATUS_MAP.get(status_str, status_str)

        # ── 标题行 ──
        header = QHBoxLayout()
        tid_lbl = QLabel(f"任务 #{t.id}")
        tid_lbl.setStyleSheet(
            f"font-size: 20px; font-weight: bold; "
            f"color: {Colors.ACCENT2}; background: transparent; border: none;")
        header.addWidget(tid_lbl)
        header.addStretch()
        # 保存引用以便实时更新
        self._status_badge = QLabel(status_text)
        self._status_badge.setStyleSheet(self._badge_style(status_str))
        header.addWidget(self._status_badge)
        layout.addLayout(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(
            f"color: {Colors.BORDER}; background-color: {Colors.BORDER}; "
            f"max-height: 1px;")
        layout.addWidget(sep)

        # ── 静态信息卡片（不会变化） ──
        info_card = self._info_card("📋 基础信息", [
            ("实验名称", cfg.experiment_name),
            ("脚本路径", cfg.script_path or '-'),
            ("工作目录", cfg.work_dir or '-'),
            ("数据集", cfg.dataset),
            ("数据集路径", cfg.dataset_path or '-'),
            ("Conda环境", cfg.env_name),
        ])
        layout.addWidget(info_card)

        train_card = self._info_card("⚙️ 训练参数", [
            ("训练轮次", str(cfg.max_epochs)),
            ("批大小", str(cfg.batch_size)),
            ("指定GPU",
             f"GPU {t.gpu_id}" if t.gpu_id >= 0 else "自动选择"),
        ])
        layout.addWidget(train_card)

        # ── 动态信息卡片（运行时变化） ──
        pi = t.progress_info
        progress_rows, self._dyn_labels = self._dynamic_info_rows(t)
        progress_card = self._info_card("📈 运行状态", progress_rows)
        layout.addWidget(progress_card)

        # ── 进度条 ──
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        pct = pi.progress_percent
        self._progress_bar.setValue(int(pct))
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat(f"{pct:.1f}%")
        self._progress_bar.setFixedHeight(22)
        self._update_progress_bar_style(pct)
        layout.addWidget(self._progress_bar)

        layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setMinimumWidth(100)
        close_btn.setMinimumHeight(38)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Colors.ACCENT2}, stop:1 {Colors.ACCENT});
                color: white; font-weight: bold; font-size: 13px;
                border: none; border-radius: 12px;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Colors.ACCENT}, stop:1 {Colors.ACCENT2});
            }}
        """)
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _dynamic_info_rows(self, task):
        """构建运行状态卡片的行列表，同时返回需要动态更新的 QLabel 引用"""
        t = task
        pi = t.progress_info
        epoch = pi.epoch
        total_epochs = pi.total_epochs
        pct = pi.progress_percent
        status_text = pi.status_text

        progress_text = (
            f"Epoch {epoch}/{total_epochs} ({pct:.1f}%)"
            if total_epochs > 0 else f"{pct:.1f}%")

        gpu_text = (f"GPU {t.gpu_id}" if t.gpu_id >= 0
                    else "自动选择")

        labels = {}
        rows = [
            ("当前状态", status_text, "status_text"),
            ("进度", progress_text, "progress"),
            ("GPU", gpu_text, "gpu"),
            ("添加时间", t.add_time or '-', "add_time"),
            ("开始时间", t.start_time or '-', "start_time"),
            ("结束时间", t.end_time or '-', "end_time"),
            ("前置等待", f"{t.wait_seconds} 秒", "wait"),
        ]
        display_rows = []
        for row in rows:
            label, value, key = row
            vl = QLabel(str(value))
            vl.setWordWrap(True)
            vl.setStyleSheet(
                f"font-size: 12px; color: {Colors.TEXT_PRIMARY}; "
                f"background: transparent; border: none;")
            labels[key] = vl
            display_rows.append((label, vl))
        return display_rows, labels

    def update_from_task(self, task):
        """外部调用：根据 task 最新状态刷新所有动态字段"""
        self.task = task
        status_str = (task.status.value if isinstance(task.status, TaskStatus)
                      else task.status)
        status_text = self._STATUS_MAP.get(status_str, status_str)
        self._status_badge.setText(status_text)
        self._status_badge.setStyleSheet(self._badge_style(status_str))

        pi = task.progress_info
        pct = pi.progress_percent
        epoch = pi.epoch
        total = pi.total_epochs
        progress_text = (
            f"Epoch {epoch}/{total} ({pct:.1f}%)"
            if total > 0 else f"{pct:.1f}%")

        lbls = self._dyn_labels
        lbls["status_text"].setText(pi.status_text)
        lbls["progress"].setText(progress_text)
        lbls["gpu"].setText(
            f"GPU {task.gpu_id}" if task.gpu_id >= 0 else "自动选择")
        lbls["start_time"].setText(task.start_time or '-')
        lbls["end_time"].setText(task.end_time or '-')

        # 更新进度条
        self._progress_bar.setValue(int(pct))
        self._progress_bar.setFormat(f"{pct:.1f}%")
        self._update_progress_bar_style(pct)

    def _badge_style(self, status_str):
        color_map = {
            'pending': Colors.ACCENT,
            'running': Colors.BLUE,
            'completed': Colors.GREEN,
            'failed': Colors.RED,
            'stopped': Colors.TEXT_MUTED,
        }
        bg = color_map.get(status_str, Colors.ACCENT)
        return (
            f"font-size: 13px; font-weight: bold; color: {Colors.CARD_BG}; "
            f"background-color: {bg}; "
            f"padding: 4px 14px; border-radius: 12px;")

    def _update_progress_bar_style(self, pct):
        cs, ce = _progress_colors(pct)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {Colors.GRADIENT_TOP};
                border: none;
                border-radius: 11px;
                font-size: 12px;
                font-weight: bold;
                color: {Colors.TEXT_PRIMARY};
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {cs}, stop:1 {ce});
                border-radius: 10px;
            }}
        """)

    def _info_card(self, title, rows):
        """构建信息卡片。rows 中的 value 可以是字符串或 QLabel。"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.GRADIENT_TOP};
                border: none;
                border-radius: 14px;
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setSpacing(6)
        cl.setContentsMargins(16, 12, 16, 12)

        tl = QLabel(title)
        tl.setStyleSheet(
            f"font-size: 13px; font-weight: bold; "
            f"color: {Colors.ACCENT2}; background: transparent; border: none;")
        cl.addWidget(tl)

        for label, value in rows:
            row_w = QHBoxLayout()
            row_w.setSpacing(8)
            kl = QLabel(label)
            kl.setStyleSheet(
                f"font-size: 12px; color: {Colors.TEXT_MUTED}; "
                f"background: transparent; border: none; min-width: 70px;")
            row_w.addWidget(kl)
            if isinstance(value, QLabel):
                # 已创建的 QLabel，直接添加
                row_w.addWidget(value)
            else:
                vl = QLabel(str(value))
                vl.setWordWrap(True)
                vl.setStyleSheet(
                    f"font-size: 12px; color: {Colors.TEXT_PRIMARY}; "
                    f"background: transparent; border: none;")
                row_w.addWidget(vl)
            row_w.addStretch()
            cl.addLayout(row_w)

        return card
