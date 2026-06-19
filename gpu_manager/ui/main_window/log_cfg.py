"""
MainWindow 的日志、配置持久化、文件浏览对话框。
"""
import os
import re
import json
from datetime import datetime

from PyQt5.QtWidgets import (
    QFileDialog, QMessageBox,
)
from PyQt5.QtCore import QTimer

from ...core.config import Colors
from ...core.logger import get_logger
from ...core.models import Task, TaskStatus

logger = get_logger('log_cfg')

CONFIG_VERSION = 1


class LogCfgMixin:
    """日志、配置存储、文件浏览"""

    def add_to_log(self, source, message):
        ts = datetime.now().strftime("%H:%M:%S")
        for sub in str(message).splitlines() or [""]:
            self._log_entries.append((source, ts, sub))
        # 更新筛选下拉框（如果有新 source）
        self._ensure_log_source_option(source)
        # 节流 flush
        if self._log_flush_timer is None:
            self._log_flush_timer = QTimer.singleShot(
                150, self._flush_log_buffer)

    def _ensure_log_source_option(self, source):
        """确保筛选下拉框包含该 source 选项（O(1) 查找）。"""
        if not hasattr(self, '_log_source_set'):
            self._log_source_set = set()
        if source in self._log_source_set:
            return
        self._log_source_set.add(source)
        self._log_filter_combo.addItem(source, source)

    def _flush_log_buffer(self):
        try:
            self._log_flush_timer = None
            # 只在"全部"且无关键字时增量追加
            current_filter = self._log_filter_combo.currentData()
            keyword = self._log_keyword_edit.text().strip()
            if current_filter == "all" and not keyword:
                # 增量模式：只渲染最新条目
                new_entries = self._log_entries[self._log_flushed_count:]
                if not new_entries:
                    return
                self._log_flushed_count = len(self._log_entries)
                html_parts = []
                for source, ts, text in new_entries:
                    html_parts.append(self._format_log_entry(source, ts, text, ""))
                self.log_text.appendHtml("<br>".join(html_parts))
            else:
                # 有筛选时，完全重渲染
                self._render_filtered_logs()

            # 裁剪条目数量
            max_entries = self._log_max_blocks * 2
            if len(self._log_entries) > max_entries:
                cut = len(self._log_entries) - max_entries
                self._log_entries = self._log_entries[cut:]
                self._log_flushed_count = max(0, self._log_flushed_count - cut)

            # 自动滚动
            if self._auto_scroll:
                sb = self.log_text.verticalScrollBar()
                sb.setValue(sb.maximum())
        except Exception as e:
            logger.warning("Log flush error: %s", e)

    def _format_log_entry(self, source, ts, text, keyword):
        """格式化单条日志为 HTML，支持关键字高亮。"""
        colors = {
            "系统": Colors.ACCENT3,
            "任务": Colors.ACCENT2,
            "调度器": Colors.GREEN,
            "警告": Colors.ORANGE,
            "错误": Colors.RED,
        }
        c = colors.get(source, Colors.TEXT_PRIMARY)
        # HTML 转义
        safe_text = (text.replace("&", "&amp;")
                         .replace("<", "&lt;")
                         .replace(">", "&gt;"))
        # 关键字高亮
        if keyword:
            kw_escaped = re.escape(keyword)
            safe_text = re.sub(
                f'({kw_escaped})',
                r'<span style="background-color:{0};font-weight:bold">\1</span>'.format(Colors.ACCENT5),
                safe_text, flags=re.IGNORECASE)
        return f'<span style="color:{c}">[{ts}] [{source}] {safe_text}</span>'

    def _render_filtered_logs(self):
        """完全重渲染日志（筛选模式）。"""
        current_filter = self._log_filter_combo.currentData()
        keyword = self._log_keyword_edit.text().strip()
        html_parts = []
        max_display = self._log_max_blocks
        entries = self._log_entries
        # 从后往前取最新的
        start = max(0, len(entries) - max_display)
        for source, ts, text in entries[start:]:
            if current_filter != "all" and source != current_filter:
                continue
            html_parts.append(
                self._format_log_entry(source, ts, text, keyword))
        self.log_text.clear()
        if html_parts:
            self.log_text.appendHtml("<br>".join(html_parts))
        if self._auto_scroll:
            sb = self.log_text.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _apply_log_filter(self):
        """筛选条件变化时触发完整重渲染。"""
        self._render_filtered_logs()

    def _on_auto_scroll_toggled(self, checked):
        self._auto_scroll = checked

    def clear_logs(self):
        self.log_text.clear()
        self._log_entries.clear()
        self._log_flushed_count = 0
        # 重置筛选下拉框：清空所有 source 选项，只保留"全部"
        if hasattr(self, '_log_source_set'):
            self._log_source_set.clear()
        self._log_filter_combo.blockSignals(True)
        self._log_filter_combo.clear()
        self._log_filter_combo.addItem("全部", "all")
        self._log_filter_combo.blockSignals(False)
        self.add_to_log("系统", "日志已清空")

    def export_logs(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", "task_log.txt",
            "Text Files (*.txt);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                self.add_to_log(
                    "系统", f"日志已导出到: {file_path}")
            except Exception as e:
                QMessageBox.warning(
                    self, "错误", f"导出日志失败: {str(e)}")

    def save_config_to_file(self):
        try:
            data = {
                'version': CONFIG_VERSION,
                'task_id_counter': self.task_id_counter,
                'tasks': [
                    task.to_dict()
                    for task in self.tasks
                    if task.status == TaskStatus.PENDING
                ],
            }
            # 保存前备份
            if os.path.exists(self.config_file):
                backup = self.config_file + '.bak'
                try:
                    import shutil
                    shutil.copy2(self.config_file, backup)
                except OSError:
                    pass  # 备份失败不影响主流程
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.add_to_log(
                "系统",
                f"配置已保存 (共 {len(data['tasks'])} 个待执行任务)")
        except Exception as e:
            QMessageBox.warning(
                self, "错误", f"保存配置失败: {str(e)}")

    def _save_task_history(self):
        """将已完成/失败/停止的任务归档到 history 文件"""
        history_file = self.config_file.replace(
            'task_config.json', 'task_history.json')
        try:
            existing = []
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            # 收集非 PENDING 的任务
            new_entries = [
                task.to_dict()
                for task in self.tasks
                if task.status != TaskStatus.PENDING
            ]
            existing.extend(new_entries)
            # 保留最近 200 条
            max_history = 200
            if len(existing) > max_history:
                existing = existing[-max_history:]
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'version': CONFIG_VERSION,
                    'history': existing,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Failed to save task history: %s", e)

    def export_task_group(self):
        """导出当前所有任务为 JSON（可分享给他人）"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出任务组", "task_group.json",
            "JSON Files (*.json);;All Files (*)")
        if not file_path:
            return
        try:
            data = {
                'version': CONFIG_VERSION,
                'exported_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'tasks': [t.to_dict() for t in self.tasks],
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.add_to_log(
                "系统", f"已导出 {len(data['tasks'])} 个任务到 {file_path}")
        except Exception as e:
            QMessageBox.warning(
                self, "错误", f"导出任务组失败: {str(e)}")

    def import_task_group(self):
        """从 JSON 文件导入任务组"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入任务组", "",
            "JSON Files (*.json);;All Files (*)")
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            tasks_data = data.get('tasks', [])
            if not tasks_data:
                self.add_to_log("警告", "导入文件中没有任务")
                return
            imported = 0
            for td in tasks_data:
                task = Task.from_dict(td)
                task.id = self.task_id_counter
                self.task_id_counter += 1
                task.status = TaskStatus.PENDING
                self.tasks.append(task)
                imported += 1
            self.render_tasks()
            self._quick_update_stats()
            self.add_to_log("系统", f"已导入 {imported} 个任务")
        except Exception as e:
            QMessageBox.warning(
                self, "错误", f"导入任务组失败: {str(e)}")

    def load_config_from_file(self):
        if not os.path.exists(self.config_file):
            return
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            file_version = data.get('version', 0)
            if file_version < CONFIG_VERSION:
                logger.info(
                    "Config v%d loaded, current version v%d — "
                    "auto-migrating", file_version, CONFIG_VERSION)
            loaded = data.get('tasks', [])
            if not loaded:
                return
            reply = QMessageBox.question(
                self, "加载配置",
                f"发现保存的配置，共 {len(loaded)} 个任务。\n是否加载？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply != QMessageBox.Yes:
                return
            self.task_id_counter = data.get(
                'task_id_counter', self.task_id_counter)
            for td in loaded:
                task = Task.from_dict(td)
                # 确保加载的任务处于 PENDING 状态
                task.status = TaskStatus.PENDING
                self.tasks.append(task)
            self.render_tasks()
            self._quick_update_stats()
            self.add_to_log("系统", f"已加载 {len(loaded)} 个任务")
        except Exception as e:
            QMessageBox.warning(
                self, "错误", f"加载配置失败: {str(e)}")

    def browse_script(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "选择Python脚本", "", "Python Files (*.py)")
        if fp:
            self.script_path_edit.setText(fp)

    def browse_workdir(self):
        dp = QFileDialog.getExistingDirectory(
            self, "选择工作目录")
        if dp:
            self.work_dir_edit.setText(dp)

    def browse_dataset(self):
        dp = QFileDialog.getExistingDirectory(
            self, "选择数据集目录")
        if dp:
            self.dataset_path_edit.setText(dp)

    def show_task_history(self):
        """弹出任务历史查看对话框"""
        from PyQt5.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel,
            QTableWidget, QTableWidgetItem, QPushButton,
        )
        from PyQt5.QtCore import Qt
        from ...core.config import Colors, STATUS_NAMES
        from .base import _duration_text

        history_file = self.config_file.replace(
            'task_config.json', 'task_history.json')
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                history = data.get('history', [])
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load history: %s", e)

        dlg = QDialog(self)
        dlg.setWindowTitle("📜 任务历史")
        dlg.setMinimumSize(800, 500)
        dlg.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.CARD_BG};
            }}
            QTableWidget {{
                background-color: {Colors.CARD_BG};
                alternate-background-color: {Colors.ROW_ALT};
                color: {Colors.TEXT_PRIMARY};
                gridline-color: transparent;
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                font-size: 12px;
                selection-background-color: {Colors.GRADIENT_TOP};
                selection-color: {Colors.TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background-color: {Colors.GRADIENT_TOP};
                color: {Colors.TEXT_SECONDARY};
                padding: 8px 6px;
                border: none;
                border-bottom: 1.5px solid {Colors.BORDER};
                font-weight: bold;
                font-size: 11px;
            }}
        """)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel(f"📜 任务历史 ({len(history)} 条记录)")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: bold; "
            f"color: {Colors.ACCENT2}; background: transparent; border: none;")
        layout.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels([
            "ID", "实验名称", "数据集", "状态",
            "开始时间", "结束时间", "时长",
        ])
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        table.setRowCount(len(history))

        for row, entry in enumerate(history):
            cfg = entry.get('config', {})
            status_str = entry.get('status', 'unknown')
            status_name = STATUS_NAMES.get(status_str, status_str)
            start = entry.get('start_time', '')
            end = entry.get('end_time', '')
            dur = _duration_text(start, end)
            items = [
                str(entry.get('id', '')),
                cfg.get('experiment_name', ''),
                cfg.get('dataset', ''),
                status_name,
                start or '-',
                end or '-',
                dur,
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row, col, item)

        table.setRowHeight(0, 36) if history else None
        for row in range(table.rowCount()):
            table.setRowHeight(row, 36)
        layout.addWidget(table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setMinimumWidth(100)
        close_btn.setMinimumHeight(36)
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
        close_btn.clicked.connect(dlg.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        dlg.exec_()
