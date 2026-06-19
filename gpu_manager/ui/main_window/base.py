"""
MainWindow 的基础部分：构造、UI 骨架、样式表、标题栏、左右面板、状态栏。
其他 mixin 通过 `self` 访问在这里定义的属性。
"""
import os
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGridLayout, QLabel, QLineEdit, QComboBox, QSpinBox,
    QPushButton, QFrame, QScrollArea, QTableWidget,
    QHeaderView, QAbstractItemView, QCheckBox, QPlainTextEdit,
    QApplication, QSystemTrayIcon,
)
from PyQt5.QtCore import Qt, QTimer, QSettings, pyqtSignal
from PyQt5.QtGui import QFont, QIcon

from ...core.config import APP_TITLE, Colors
from ..gpu_card import GPUCardsPanel


class _TaskTable(QTableWidget):
    """自定义表格：拖拽排序模式下仍能正确响应单击事件"""
    rowClicked = pyqtSignal(int)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            press_pos = self._press_pos if hasattr(self, '_press_pos') else None
            if press_pos is not None:
                dist = (event.pos() - press_pos).manhattanLength()
                threshold = QApplication.startDragDistance() or 10
                if dist <= threshold:
                    idx = self.indexAt(event.pos())
                    if idx.isValid():
                        self.rowClicked.emit(idx.row())
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        self._press_pos = event.pos()
        super().mousePressEvent(event)


def _duration_text(start_time, end_time=None):
    """根据 start_time / end_time 计算训练时长文本，如 '01:23:45'"""
    if not start_time:
        return "-"
    fmt = "%Y-%m-%d %H:%M:%S"
    try:
        st = datetime.strptime(start_time, fmt)
        et = datetime.strptime(end_time, fmt) if end_time else datetime.now()
        delta = et - st
        secs = int(delta.total_seconds())
        if secs < 0:
            return "-"
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    except (ValueError, TypeError):
        return "-"


class _MainWindowBase(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setGeometry(100, 100, 1500, 950)

        self.tasks = []
        self.task_id_counter = 1
        self.task_threads = {}
        self.scheduler = None

        # 日志条目存储（用于筛选重显）
        self._log_entries = []  # [(source, ts, raw_text), ...]
        self._auto_scroll = True

        self.config_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "..", "task_config.json")
        self.config_file = os.path.normpath(self.config_file)

        # 日志节流
        self._log_flushed_count = 0
        self._log_flush_timer = None
        self._log_max_blocks = 2000

        # 操作列 handlers，给 ops_widget 用
        self._ops_handlers = {
            'stop_task': self.stop_task,
            'delete_task': self.delete_task,
            'move_task_up': self.move_task_up,
            'move_task_down': self.move_task_down,
            'clone_task': self.clone_task,
            'retry_task': self.retry_task,
        }

        # 恢复主题
        self._restore_theme()

        self.init_ui()

        # 恢复窗口位置和大小
        self._restore_window_geometry()

        # 恢复表单字段值
        self._restore_form_fields()

        # 恢复主题按钮文本
        self._update_theme_button()

        # 在 init_ui 之后才能拿到 gpu_cards_layout
        self._gpu_cards_panel = GPUCardsPanel(
            self.gpu_cards_layout,
            on_lock_toggle=self._on_gpu_lock_toggle)

        self.load_gpu_info()
        self.load_conda_envs()
        self.load_config_from_file()

        self.gpu_timer = QTimer()
        self.gpu_timer.timeout.connect(self.refresh_gpu_info)
        self.gpu_timer.start(5000)

        # 训练时长刷新定时器（每秒更新运行中任务的时长显示）
        self._duration_timer = QTimer()
        self._duration_timer.timeout.connect(self._refresh_running_durations)
        self._duration_timer.start(1000)

        # 系统托盘图标（用于任务完成通知）
        self._tray_icon = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon = QSystemTrayIcon(self)
            self._tray_icon.setIcon(self.windowIcon() or QIcon())
            self._tray_icon.setToolTip("GPU 任务管理器")

    # ---------- UI 骨架 ----------
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 16, 20, 16)

        main_layout.addWidget(self._create_title_bar())

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self._create_left_panel(), 3)
        content.addWidget(self._create_right_panel(), 7)
        main_layout.addLayout(content)

        main_layout.addWidget(self._create_status_bar())
        self.apply_stylesheet()

    def _create_title_bar(self):
        w = QWidget()
        w.setObjectName("titleBar")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(24, 14, 24, 14)

        left = QHBoxLayout()
        icon = QLabel("🌸")
        icon.setStyleSheet(
            "font-size: 26px; background: transparent; border: none;")
        left.addWidget(icon)

        title = QLabel("GPU 任务管理器")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: bold; "
            f"color: {Colors.TEXT_PRIMARY}; "
            f"background: transparent; border: none;")
        left.addWidget(title)
        left.addStretch()
        layout.addLayout(left)

        self.save_config_btn = QPushButton("💾 保存")
        self.save_config_btn.setObjectName("titleBtn")
        self.save_config_btn.clicked.connect(self.save_config_to_file)
        layout.addWidget(self.save_config_btn)

        self.load_config_btn = QPushButton("📂 加载")
        self.load_config_btn.setObjectName("titleBtn")
        self.load_config_btn.clicked.connect(self.load_config_from_file)
        layout.addWidget(self.load_config_btn)

        self.theme_toggle_btn = QPushButton("🌙 主题")
        self.theme_toggle_btn.setObjectName("titleBtn")
        self.theme_toggle_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_toggle_btn)

        self.export_tasks_btn = QPushButton("📤 导出")
        self.export_tasks_btn.setObjectName("titleBtn")
        self.export_tasks_btn.clicked.connect(self.export_task_group)
        layout.addWidget(self.export_tasks_btn)

        self.import_tasks_btn = QPushButton("📥 导入")
        self.import_tasks_btn.setObjectName("titleBtn")
        self.import_tasks_btn.clicked.connect(self.import_task_group)
        layout.addWidget(self.import_tasks_btn)
        return w

    # ---------- 左面板 ----------
    def _create_left_panel(self):
        panel = QWidget()
        panel.setObjectName("leftPanel")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("leftScroll")
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # 卡片1：任务配置
        c1 = self._make_card("⚙️ 任务配置", Colors.ACCENT)
        cf = QFormLayout()
        cf.setSpacing(10)
        cf.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        el = QHBoxLayout()
        self.conda_env_combo = QComboBox()
        self.conda_env_combo.setMinimumHeight(34)
        reb = QPushButton("🔄")
        reb.setObjectName("iconBtn")
        reb.setFixedSize(34, 34)
        reb.clicked.connect(self.load_conda_envs)
        el.addWidget(self.conda_env_combo)
        el.addWidget(reb)
        cf.addRow("Conda环境:", el)

        sl = QHBoxLayout()
        self.script_path_edit = QLineEdit()
        self.script_path_edit.setPlaceholderText("选择脚本路径...")
        self.script_path_edit.setMinimumHeight(34)
        sbb = QPushButton("📂")
        sbb.setObjectName("iconBtn")
        sbb.setFixedSize(34, 34)
        sbb.clicked.connect(self.browse_script)
        sl.addWidget(self.script_path_edit)
        sl.addWidget(sbb)
        cf.addRow("Python脚本:", sl)

        self.gpu_combo = QComboBox()
        self.gpu_combo.addItem("自动选择（最低使用率）", -1)
        self.gpu_combo.setMinimumHeight(34)
        cf.addRow("GPU选择:", self.gpu_combo)

        wdl = QHBoxLayout()
        self.work_dir_edit = QLineEdit()
        self.work_dir_edit.setPlaceholderText("选择工作目录...")
        self.work_dir_edit.setMinimumHeight(34)
        wb = QPushButton("📂")
        wb.setObjectName("iconBtn")
        wb.setFixedSize(34, 34)
        wb.clicked.connect(self.browse_workdir)
        wdl.addWidget(self.work_dir_edit)
        wdl.addWidget(wb)
        cf.addRow("工作目录:", wdl)

        self.dataset_edit = QLineEdit("cad38")
        self.dataset_edit.setMinimumHeight(34)
        cf.addRow("数据集:", self.dataset_edit)

        self.experiment_edit = QLineEdit("classification")
        self.experiment_edit.setMinimumHeight(34)
        cf.addRow("实验名称:", self.experiment_edit)

        dpl = QHBoxLayout()
        self.dataset_path_edit = QLineEdit()
        self.dataset_path_edit.setPlaceholderText("选择数据集路径...")
        self.dataset_path_edit.setMinimumHeight(34)
        db = QPushButton("📂")
        db.setObjectName("iconBtn")
        db.setFixedSize(34, 34)
        db.clicked.connect(self.browse_dataset)
        dpl.addWidget(self.dataset_path_edit)
        dpl.addWidget(db)
        cf.addRow("数据集路径:", dpl)

        ebl = QHBoxLayout()
        ebl.setSpacing(8)
        ebl.addWidget(QLabel("轮次:"))
        self.epochs_spin = QSpinBox()
        self.epochs_spin.setValue(200)
        self.epochs_spin.setMinimum(1)
        self.epochs_spin.setMaximum(100000)
        self.epochs_spin.setMinimumHeight(34)
        ebl.addWidget(self.epochs_spin)
        ebl.addWidget(QLabel("批大小:"))
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setValue(64)
        self.batch_size_spin.setMinimum(1)
        self.batch_size_spin.setMaximum(8192)
        self.batch_size_spin.setMinimumHeight(34)
        ebl.addWidget(self.batch_size_spin)
        cf.addRow(ebl)

        wl = QHBoxLayout()
        wl.setSpacing(4)
        self.wait_hours_spin = QSpinBox()
        self.wait_hours_spin.setRange(0, 23)
        self.wait_hours_spin.setSuffix("时")
        self.wait_hours_spin.setMinimumHeight(34)
        wl.addWidget(self.wait_hours_spin)
        self.wait_minutes_spin = QSpinBox()
        self.wait_minutes_spin.setRange(0, 59)
        self.wait_minutes_spin.setSuffix("分")
        self.wait_minutes_spin.setMinimumHeight(34)
        wl.addWidget(self.wait_minutes_spin)
        self.wait_seconds_spin = QSpinBox()
        self.wait_seconds_spin.setRange(0, 59)
        self.wait_seconds_spin.setSuffix("秒")
        self.wait_seconds_spin.setMinimumHeight(34)
        wl.addWidget(self.wait_seconds_spin)
        cf.addRow("前置等待:", wl)

        self._set_card_content(c1, cf)
        layout.addWidget(c1)

        # 卡片2：操作控制
        c2 = self._make_card("🎮 操作控制", Colors.ACCENT2)
        ctrl = QGridLayout()
        ctrl.setSpacing(8)
        self.add_task_btn = QPushButton("➕ 添加任务")
        self.add_task_btn.setObjectName("primaryBtn")
        self.add_task_btn.setMinimumHeight(42)
        self.add_task_btn.clicked.connect(self.add_task)
        ctrl.addWidget(self.add_task_btn, 0, 0)
        self.start_scheduler_btn = QPushButton("▶️ 开始调度")
        self.start_scheduler_btn.setObjectName("successBtn")
        self.start_scheduler_btn.setMinimumHeight(42)
        self.start_scheduler_btn.clicked.connect(self.start_scheduler)
        ctrl.addWidget(self.start_scheduler_btn, 0, 1)
        self.stop_all_btn = QPushButton("⏹ 停止全部")
        self.stop_all_btn.setObjectName("dangerBtn")
        self.stop_all_btn.setMinimumHeight(42)
        self.stop_all_btn.clicked.connect(self.stop_all)
        ctrl.addWidget(self.stop_all_btn, 1, 0)
        self.clear_queue_btn = QPushButton("🗑 清空队列")
        self.clear_queue_btn.setObjectName("warningBtn")
        self.clear_queue_btn.setMinimumHeight(42)
        self.clear_queue_btn.clicked.connect(self.clear_queue)
        ctrl.addWidget(self.clear_queue_btn, 1, 1)
        self._set_card_content(c2, ctrl)
        layout.addWidget(c2)

        # 卡片3：统计
        c3 = self._make_card("📊 队列统计", Colors.ACCENT3)
        sg = QGridLayout()
        sg.setSpacing(8)
        items = [
            ("总任务", Colors.TEXT_PRIMARY), ("等待中", Colors.ORANGE),
            ("运行中", Colors.BLUE), ("已完成", Colors.GREEN),
            ("已失败", Colors.RED), ("已停止", Colors.TEXT_MUTED),
        ]
        self._stat_labels = {}
        for idx, (name, color) in enumerate(items):
            ctn = QWidget()
            ctn.setStyleSheet(
                f"background-color: {Colors.GRADIENT_TOP}; "
                f"border-radius: 14px; padding: 4px;")
            inner = QVBoxLayout(ctn)
            inner.setSpacing(2)
            inner.setContentsMargins(10, 6, 10, 6)
            nl = QLabel(name)
            nl.setStyleSheet(
                f"font-size: 11px; color: {Colors.TEXT_SECONDARY}; "
                f"background: transparent; border: none;")
            nl.setAlignment(Qt.AlignCenter)
            vl = QLabel("0")
            vl.setStyleSheet(
                f"font-size: 24px; font-weight: bold; color: {color}; "
                f"background: transparent; border: none;")
            vl.setAlignment(Qt.AlignCenter)
            inner.addWidget(nl)
            inner.addWidget(vl)
            sg.addWidget(ctn, idx // 3, idx % 3)
            self._stat_labels[name] = vl
        self._set_card_content(c3, sg)
        layout.addWidget(c3)

        # 卡片4：GPU 监控
        c4 = self._make_card("🖥 GPU 资源监控", Colors.ACCENT4)
        gl = QVBoxLayout()
        gl.setSpacing(6)
        self.gpu_info_label = QLabel("正在检测GPU...")
        self.gpu_info_label.setWordWrap(True)
        self.gpu_info_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-weight: bold; font-size: 13px;
                padding: 10px; border-radius: 12px;
                background-color: {Colors.GRADIENT_TOP}; border: none;
            }}
        """)
        gl.addWidget(self.gpu_info_label)
        self.gpu_cards_layout = QVBoxLayout()
        self.gpu_cards_layout.setSpacing(6)
        gl.addLayout(self.gpu_cards_layout)
        self._set_card_content(c4, gl)
        layout.addWidget(c4)

        layout.addStretch()
        scroll.setWidget(content)
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.addWidget(scroll)
        return panel

    # ---------- 右面板 ----------
    def _create_right_panel(self):
        panel = QWidget()
        panel.setObjectName("rightPanel")
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        qc = self._make_card("📋 任务队列", Colors.ACCENT)
        ql = QVBoxLayout()
        ql.setSpacing(4)
        tb = QHBoxLayout()
        tb.setSpacing(6)
        self.queue_count_label = QLabel("共 0 个任务")
        self.queue_count_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; "
            f"background: transparent; border: none;")
        tb.addWidget(self.queue_count_label)
        tb.addStretch()
        self.history_btn = QPushButton("📜 历史")
        self.history_btn.setObjectName("smallBtn")
        self.history_btn.clicked.connect(self.show_task_history)
        tb.addWidget(self.history_btn)
        ql.addLayout(tb)

        self.task_table = _TaskTable()
        self.task_table.setAlternatingRowColors(True)
        self.task_table.setColumnCount(10)
        self.task_table.setHorizontalHeaderLabels([
            "ID", "实验名称", "轮次", "批量", "GPU",
            "添加时间", "训练时长", "状态", "进度", "操作",
        ])
        self.task_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.task_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self.task_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers)
        # 双击打开详情（单击只做行选中，由 QTableWidget 原生处理）
        self.task_table.cellDoubleClicked.connect(
            lambda row, col: self._on_task_row_clicked(row))
        self.task_table.setDragDropMode(
            QAbstractItemView.InternalMove)
        self.task_table.setDragEnabled(True)
        self.task_table.setAcceptDrops(True)
        self.task_table.setDropIndicatorShown(True)
        self.task_table.verticalHeader().setSectionsMovable(True)
        self.task_table.verticalHeader().setDragEnabled(True)
        self.task_table.verticalHeader().setDragDropMode(
            QAbstractItemView.InternalMove)
        self.task_table.verticalHeader().sectionMoved.connect(
            self.on_row_moved)
        self.task_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.task_table.customContextMenuRequested.connect(
            self.on_task_context_menu)
        self.task_table.installEventFilter(self)
        hdr = self.task_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.resizeSection(0, 40)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        hdr.resizeSection(2, 50)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        hdr.resizeSection(3, 50)
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)
        hdr.resizeSection(4, 65)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)
        hdr.resizeSection(5, 125)
        hdr.setSectionResizeMode(6, QHeaderView.Fixed)
        hdr.resizeSection(6, 80)
        hdr.setSectionResizeMode(7, QHeaderView.Fixed)
        hdr.resizeSection(7, 85)
        hdr.setSectionResizeMode(8, QHeaderView.Stretch)
        hdr.setSectionResizeMode(9, QHeaderView.Fixed)
        hdr.resizeSection(9, 145)
        ql.addWidget(self.task_table)
        self._set_card_content(qc, ql)
        layout.addWidget(qc)

        lc = self._make_card("📝 运行日志", Colors.ACCENT3)
        ll = QVBoxLayout()
        ll.setSpacing(6)

        # 日志筛选工具栏
        ft = QHBoxLayout()
        ft.setSpacing(6)
        ft.addWidget(QLabel("筛选:"))
        self._log_filter_combo = QComboBox()
        self._log_filter_combo.addItem("全部", "all")
        self._log_filter_combo.setMinimumWidth(100)
        self._log_filter_combo.setMaximumWidth(160)
        self._log_filter_combo.currentIndexChanged.connect(
            self._apply_log_filter)
        ft.addWidget(self._log_filter_combo)
        self._log_keyword_edit = QLineEdit()
        self._log_keyword_edit.setPlaceholderText("关键字高亮...")
        self._log_keyword_edit.setMaximumWidth(140)
        self._log_keyword_edit.textChanged.connect(self._apply_log_filter)
        ft.addWidget(self._log_keyword_edit)
        self._auto_scroll_cb = QCheckBox("自动滚动")
        self._auto_scroll_cb.setChecked(True)
        self._auto_scroll_cb.toggled.connect(self._on_auto_scroll_toggled)
        ft.addWidget(self._auto_scroll_cb)
        ft.addStretch()
        cl = QPushButton("🗑 清空日志")
        cl.setObjectName("smallBtn")
        cl.clicked.connect(self.clear_logs)
        ft.addWidget(cl)
        ll.addLayout(ft)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(3000)
        self.log_text.setFont(QFont("Consolas", 9))
        ll.addWidget(self.log_text)

        lt = QHBoxLayout()
        lt.setSpacing(6)
        self.export_log_btn = QPushButton("📥 导出日志")
        self.export_log_btn.setObjectName("smallBtn")
        self.export_log_btn.clicked.connect(self.export_logs)
        lt.addWidget(self.export_log_btn)
        lt.addStretch()
        ll.addLayout(lt)
        self._set_card_content(lc, ll)
        layout.addWidget(lc)
        return panel

    # ---------- 状态栏 ----------
    def _create_status_bar(self):
        w = QWidget()
        w.setObjectName("statusBar")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(20, 6, 20, 6)
        layout.setSpacing(20)
        self.status_scheduler_label = QLabel("调度器: ⏸ 未启动")
        self.status_scheduler_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; "
            f"background: transparent; border: none;")
        layout.addWidget(self.status_scheduler_label)
        self.status_gpu_label = QLabel("GPU: 检测中...")
        self.status_gpu_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; "
            f"background: transparent; border: none;")
        layout.addWidget(self.status_gpu_label)
        layout.addStretch()
        self.status_time_label = QLabel("")
        self.status_time_label.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 12px; "
            f"background: transparent; border: none;")
        layout.addWidget(self.status_time_label)
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status_time)
        self.status_timer.start(1000)
        return w

    def _update_status_time(self):
        self.status_time_label.setText(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        running = bool(self.scheduler and self.scheduler.isRunning())
        prev = getattr(self, '_sched_running', None)
        if running != prev:
            self._sched_running = running
            if running:
                self.status_scheduler_label.setText("调度器: ▶ 运行中")
                self.status_scheduler_label.setStyleSheet(
                    f"color: {Colors.GREEN}; font-size: 12px; "
                    f"background: transparent; border: none;")
            else:
                self.status_scheduler_label.setText("调度器: ⏸ 未启动")
                self.status_scheduler_label.setStyleSheet(
                    f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; "
                    f"background: transparent; border: none;")

    # ---------- 卡片工具 ----------
    def _make_card(self, title, accent):
        card = QFrame()
        card.setObjectName("card")
        ml = QVBoxLayout(card)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        # ── 顶部细色条（6px 渐变色带） ──
        strip = QWidget()
        strip.setFixedHeight(6)
        strip.setStyleSheet(
            f"background: qlineargradient("
            f"x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {accent}, stop:1 {self._lighter(accent)}); "
            f"border-top-left-radius: 16px; "
            f"border-top-right-radius: 16px;")
        ml.addWidget(strip)

        # ── 内容区 ──
        body = QWidget()
        body.setObjectName("cardBody")
        bw = QVBoxLayout(body)
        bw.setContentsMargins(18, 12, 18, 18)
        bw.setSpacing(10)

        # 标题文字
        tl = QLabel(title)
        tl.setStyleSheet(
            f"color: {accent}; font-weight: bold; font-size: 14px; "
            f"background: transparent; border: none; "
            f"padding-bottom: 4px;")
        bw.addWidget(tl)

        ml.addWidget(body)
        card._body = body
        card._body_layout = bw
        return card

    def _set_card_content(self, card, layout):
        old = card._body.layout()
        while old.count():
            old.takeAt(0)
        old.addLayout(layout)

    @staticmethod
    def _lighter(hx):
        hx = hx.lstrip('#')
        r = int(hx[0:2], 16)
        g = int(hx[2:4], 16)
        b = int(hx[4:6], 16)
        r = min(255, r + 40)
        g = min(255, g + 40)
        b = min(255, b + 40)
        return f"#{r:02x}{g:02x}{b:02x}"

    # ---------- 样式表 ----------
    def apply_stylesheet(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {Colors.BG};
            }}
            QWidget {{
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
            }}

            /* ── 标题栏 ── */
            QWidget#titleBar {{
                background-color: {Colors.CARD_BG};
                border-radius: 18px;
                border: 1px solid {Colors.BORDER};
            }}
            QPushButton#titleBtn {{
                padding: 8px 18px;
                border: 1.5px solid {Colors.ACCENT};
                border-radius: 12px;
                background-color: {Colors.CARD_BG};
                color: {Colors.ACCENT};
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton#titleBtn:hover {{
                background-color: {Colors.GRADIENT_TOP};
                color: {Colors.ACCENT2};
                border-color: {Colors.ACCENT2};
            }}

            /* ── 卡片（阴影用双层 border 模拟） ── */
            QFrame#card {{
                background-color: {Colors.CARD_BG};
                border-radius: 16px;
                border: 1px solid {Colors.BORDER};
            }}
            QWidget#cardBody {{ background: transparent; }}

            /* ── 滚动区域 ── */
            QScrollArea#leftScroll {{
                background: transparent; border: none;
            }}
            QScrollArea#leftScroll > QWidget > QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent; width: 4px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.BORDER};
                border-radius: 2px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {Colors.TEXT_MUTED};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}

            /* ── 输入控件 ── */
            QLineEdit, QComboBox, QSpinBox {{
                padding: 8px 12px;
                border: 1.5px solid {Colors.BORDER};
                border-radius: 12px;
                background-color: {Colors.CARD_BG};
                color: {Colors.TEXT_PRIMARY};
                font-size: 12px;
                selection-background-color: {Colors.ACCENT};
                selection-color: white;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border: 2px solid {Colors.ACCENT};
                background-color: {Colors.CARD_BG};
            }}
            QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{
                border-color: {Colors.ACCENT2};
            }}
            QComboBox::drop-down {{ border: none; width: 22px; }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {Colors.ACCENT};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Colors.CARD_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 12px;
                padding: 6px;
                selection-background-color: {Colors.GRADIENT_TOP};
                selection-color: {Colors.TEXT_PRIMARY};
                outline: none;
                font-size: 12px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 7px 12px; border-radius: 8px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                border: none; width: 18px;
            }}

            /* ── 按钮 ── */
            QPushButton {{
                padding: 9px 16px;
                border: none;
                border-radius: 12px;
                color: white;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton#primaryBtn {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0.6,
                    stop:0 {Colors.ACCENT}, stop:1 {Colors.ACCENT2});
            }}
            QPushButton#primaryBtn:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0.6,
                    stop:0 {Colors.ACCENT2}, stop:1 {Colors.ACCENT});
            }}
            QPushButton#successBtn {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0.6,
                    stop:0 {Colors.ACCENT3}, stop:1 {Colors.GREEN});
            }}
            QPushButton#successBtn:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0.6,
                    stop:0 {Colors.GREEN}, stop:1 {Colors.ACCENT3});
            }}
            QPushButton#dangerBtn {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0.6,
                    stop:0 {Colors.RED}, stop:1 {Colors.ACCENT4});
            }}
            QPushButton#dangerBtn:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0.6,
                    stop:0 {Colors.ACCENT4}, stop:1 {Colors.RED});
            }}
            QPushButton#warningBtn {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0.6,
                    stop:0 {Colors.ORANGE}, stop:1 {Colors.ACCENT5});
            }}
            QPushButton#warningBtn:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0.6,
                    stop:0 {Colors.ACCENT5}, stop:1 {Colors.ORANGE});
            }}
            QPushButton#iconBtn {{
                padding: 4px;
                background-color: {Colors.GRADIENT_TOP};
                border: 1.5px solid {Colors.ACCENT};
                border-radius: 10px;
                font-size: 14px;
            }}
            QPushButton#iconBtn:hover {{
                background-color: {Colors.ACCENT};
                color: white;
            }}
            QPushButton#smallBtn {{
                padding: 6px 12px;
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
                font-weight: normal;
            }}
            QPushButton#smallBtn:hover {{
                background-color: {Colors.GRADIENT_TOP};
                border-color: {Colors.ACCENT};
                color: {Colors.ACCENT};
            }}

            /* ── 表格 ── */
            QTableWidget {{
                background-color: {Colors.CARD_BG};
                alternate-background-color: {Colors.ROW_ALT};
                color: {Colors.TEXT_PRIMARY};
                gridline-color: transparent;
                border: 1px solid {Colors.BORDER};
                border-radius: 14px;
                font-size: 12px;
                selection-background-color: {Colors.GRADIENT_TOP};
                selection-color: {Colors.TEXT_PRIMARY};
            }}
            QTableWidget::item {{
                padding: 8px 6px;
            }}
            QTableWidget::item:selected {{
                background-color: {Colors.GRADIENT_TOP};
                color: {Colors.TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background-color: {Colors.GRADIENT_TOP};
                color: {Colors.TEXT_SECONDARY};
                padding: 10px 6px;
                border: none;
                border-bottom: 1.5px solid {Colors.BORDER};
                font-weight: bold;
                font-size: 11px;
            }}

            /* ── 文本框 ── */
            QPlainTextEdit {{
                background-color: {Colors.CARD_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 12px;
                padding: 12px;
                font-size: 12px;
                selection-background-color: {Colors.ACCENT3};
            }}

            /* ── 通用标签 ── */
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 12px;
                background: transparent;
                border: none;
            }}

            /* ── 状态栏 ── */
            QWidget#statusBar {{
                background-color: {Colors.CARD_BG};
                border-radius: 14px;
                border: 1px solid {Colors.BORDER};
            }}
            QWidget#leftPanel, QWidget#rightPanel {{
                background: transparent;
            }}

            /* ── 进度条 ── */
            QProgressBar {{
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 9px;
                font-size: 10px;
                color: {Colors.TEXT_PRIMARY};
                text-align: center;
            }}
        """)

    # ---------- 主题切换 ----------
    def _toggle_theme(self):
        current = Colors.get_theme()
        new_theme = 'dark' if current == 'light' else 'light'
        Colors.set_theme(new_theme)
        self.apply_stylesheet()
        # 更新按钮文本
        self.theme_toggle_btn.setText(
            "☀️ 主题" if new_theme == 'dark' else "🌙 主题")
        # 持久化主题选择
        settings = QSettings("GPUManager", "GPUManager")
        settings.setValue("theme", new_theme)
        # 刷新 GPU 卡片样式
        self._gpu_cards_panel.clear()
        # 立即异步重建 GPU 卡片，不等 5 秒定时器
        self.refresh_gpu_info()
        # 强制全量刷新表格 cell widgets（ops/progress 使用创建时颜色）
        self.task_table.setRowCount(0)
        if self.tasks:
            for row_idx, task in enumerate(self.tasks):
                self.task_table.insertRow(row_idx)
                self._populate_table_row(row_idx, task)
        # 刷新队列统计标签颜色
        self.queue_count_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; "
            f"background: transparent; border: none;")
        self._quick_update_stats()

    def _restore_theme(self):
        settings = QSettings("GPUManager", "GPUManager")
        theme = settings.value("theme", "light")
        if theme in Colors.available_themes():
            Colors.set_theme(theme)

    def _update_theme_button(self):
        """在 init_ui 之后调用，更新主题按钮文本"""
        theme = Colors.get_theme()
        self.theme_toggle_btn.setText(
            "☀️ 主题" if theme == 'dark' else "🌙 主题")

    def _show_notification(self, title, message):
        """通过系统托盘弹出桌面通知（仅在窗口不在前台时）"""
        if self._tray_icon and not self.isActiveWindow():
            self._tray_icon.showMessage(
                title, message,
                QSystemTrayIcon.Information, 5000)

    # ---------- 窗口位置记忆 ----------
    def _restore_window_geometry(self):
        settings = QSettings("GPUManager", "GPUManager")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def _save_window_geometry(self):
        settings = QSettings("GPUManager", "GPUManager")
        settings.setValue("geometry", self.saveGeometry())

    def _save_form_fields(self):
        """持久化表单字段值，下次启动自动恢复"""
        settings = QSettings("GPUManager", "GPUManager")
        settings.setValue("form/script_path",
                          self.script_path_edit.text())
        settings.setValue("form/work_dir",
                          self.work_dir_edit.text())
        settings.setValue("form/dataset",
                          self.dataset_edit.text())
        settings.setValue("form/dataset_path",
                          self.dataset_path_edit.text())
        settings.setValue("form/experiment_name",
                          self.experiment_edit.text())
        settings.setValue("form/epochs",
                          self.epochs_spin.value())
        settings.setValue("form/batch_size",
                          self.batch_size_spin.value())

    def _restore_form_fields(self):
        """从 QSettings 恢复上次使用的表单字段值"""
        settings = QSettings("GPUManager", "GPUManager")
        script = settings.value("form/script_path", "")
        if script:
            self.script_path_edit.setText(script)
        work_dir = settings.value("form/work_dir", "")
        if work_dir:
            self.work_dir_edit.setText(work_dir)
        dataset = settings.value("form/dataset", "")
        if dataset:
            self.dataset_edit.setText(dataset)
        ds_path = settings.value("form/dataset_path", "")
        if ds_path:
            self.dataset_path_edit.setText(ds_path)
        exp = settings.value("form/experiment_name", "")
        if exp:
            self.experiment_edit.setText(exp)
        epochs = settings.value("form/epochs", None)
        if epochs is not None:
            try:
                self.epochs_spin.setValue(int(epochs))
            except (ValueError, TypeError):
                pass
        batch = settings.value("form/batch_size", None)
        if batch is not None:
            try:
                self.batch_size_spin.setValue(int(batch))
            except (ValueError, TypeError):
                pass
        # 设置字段历史自动补全
        self._setup_field_completers()

    def _setup_field_completers(self):
        """为数据集和实验名称字段设置历史自动补全"""
        from PyQt5.QtCore import QStringListModel
        from PyQt5.QtWidgets import QCompleter
        settings = QSettings("GPUManager", "GPUManager")
        for edit, key in [
            (self.dataset_edit, "history/datasets"),
            (self.experiment_edit, "history/experiments"),
        ]:
            history = settings.value(key, [])
            if not isinstance(history, list):
                history = []
            if history:
                model = QStringListModel(history)
                completer = QCompleter(model, edit)
                completer.setCaseSensitivity(Qt.CaseInsensitive)
                completer.setFilterMode(Qt.MatchContains)
                edit.setCompleter(completer)

    def _save_field_history(self):
        """将当前字段值追加到历史记录"""
        settings = QSettings("GPUManager", "GPUManager")
        for edit, key in [
            (self.dataset_edit, "history/datasets"),
            (self.experiment_edit, "history/experiments"),
        ]:
            value = edit.text().strip()
            if not value:
                continue
            history = settings.value(key, [])
            if not isinstance(history, list):
                history = []
            # 去重并放到最前面
            if value in history:
                history.remove(value)
            history.insert(0, value)
            # 最多保留 20 条
            history = history[:20]
            settings.setValue(key, history)

    # ---------- 关闭事件 ----------
    def closeEvent(self, event):
        self._save_window_geometry()
        self._save_form_fields()
        if self.scheduler:
            self.scheduler.stop()
        for thread in self.task_threads.values():
            thread.stop()
        if hasattr(self, 'status_timer'):
            self.status_timer.stop()
        if hasattr(self, '_duration_timer'):
            self._duration_timer.stop()
        self._save_task_history()
        self.save_config_to_file()
        event.accept()
