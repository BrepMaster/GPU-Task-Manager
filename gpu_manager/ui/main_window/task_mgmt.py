"""
MainWindow 的任务队列管理：添加/删除/清空任务、表格渲染、统计更新。
"""
import os
from datetime import datetime

from PyQt5.QtWidgets import QTableWidgetItem, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from ...core.config import Colors, STATUS_NAMES
from ...core.gpu_manager import GPUManager
from ...core.models import Task, TaskConfig, ProgressInfo, TaskStatus
from ..ops_widget import make_ops_widget, make_progress_widget, update_progress_bar_style
from .base import _duration_text


class TaskMixin:
    """任务队列相关方法"""

    def add_task(self):
        try:
            # ── 输入校验 ──
            script = self.script_path_edit.text().strip()
            if not script:
                QMessageBox.warning(self, "提示", "请选择 Python 脚本路径。")
                self.script_path_edit.setFocus()
                return
            if not os.path.isfile(script):
                QMessageBox.warning(
                    self, "提示",
                    f"脚本文件不存在：\n{script}")
                self.script_path_edit.setFocus()
                return
            work_dir = self.work_dir_edit.text().strip()
            if work_dir and not os.path.isdir(work_dir):
                QMessageBox.warning(
                    self, "提示",
                    f"工作目录不存在：\n{work_dir}")
                self.work_dir_edit.setFocus()
                return
            env_text = self.conda_env_combo.currentText()
            if env_text.startswith("⏳"):
                QMessageBox.warning(
                    self, "提示",
                    "Conda 环境正在扫描中，请稍后再试。")
                return

            gpu_index = self.gpu_combo.currentData()
            if gpu_index is None:
                gpu_index = -1
            # gpu_index == -1 表示"自动选择"，延迟到调度时刻再分配
            total_wait = (self.wait_hours_spin.value() * 3600
                          + self.wait_minutes_spin.value() * 60
                          + self.wait_seconds_spin.value())
            task = Task(
                id=self.task_id_counter,
                config=TaskConfig(
                    env_name=self.conda_env_combo.currentText(),
                    script_path=self.script_path_edit.text(),
                    work_dir=self.work_dir_edit.text(),
                    dataset=self.dataset_edit.text(),
                    dataset_path=self.dataset_path_edit.text(),
                    max_epochs=self.epochs_spin.value(),
                    batch_size=self.batch_size_spin.value(),
                    experiment_name=self.experiment_edit.text(),
                ),
                gpu_id=gpu_index,
                wait_seconds=total_wait,
                status=TaskStatus.PENDING,
                progress_info=ProgressInfo(
                    total_epochs=self.epochs_spin.value(),
                    status_text="等待调度",
                ),
                add_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            self.tasks.append(task)
            row = self.task_table.rowCount()
            self.task_table.insertRow(row)
            self._populate_table_row(row, task)
            self.task_id_counter += 1
            self._quick_update_stats()
            # 保存字段历史（用于自动补全）
            self._save_field_history()
            gpu_display = (f"GPU {gpu_index}" if gpu_index >= 0
                           else "自动")
            self.add_to_log(
                "任务",
                f"任务 {task.id} 已添加到队列 ({gpu_display})")
        except Exception as e:
            QMessageBox.warning(self, "警告", f"添加任务失败: {str(e)}")

    def _populate_table_row(self, row, task):
        dur = _duration_text(task.start_time, task.end_time)
        gpu_text = (f"GPU {task.gpu_id}" if task.gpu_id >= 0
                    else "自动")
        items = [
            QTableWidgetItem(str(task.id)),
            QTableWidgetItem(task.config.experiment_name),
            QTableWidgetItem(str(task.config.max_epochs)),
            QTableWidgetItem(str(task.config.batch_size)),
            QTableWidgetItem(gpu_text),
            QTableWidgetItem(task.add_time),
            QTableWidgetItem(dur),
            QTableWidgetItem(self._status_name(task.status)),
        ]
        for col, item in enumerate(items):
            item.setTextAlignment(Qt.AlignCenter)
            self.task_table.setItem(row, col, item)
        self._set_row_status_color(row, task.status)

        pw = make_progress_widget(task)
        self.task_table.setCellWidget(row, 8, pw)

        ow = make_ops_widget(task.id, task.status, self._ops_handlers)
        self.task_table.setCellWidget(row, 9, ow)

        self.task_table.setRowHeight(row, 42)

    @staticmethod
    def _status_name(status):
        if isinstance(status, TaskStatus):
            status = status.value
        return STATUS_NAMES.get(status, status)

    def _set_row_status_color(self, row, status):
        si = self.task_table.item(row, 7)
        if not si:
            return
        key = status.value if isinstance(status, TaskStatus) else status
        color_map = {
            'pending': QColor(Colors.ORANGE),
            'running': QColor(Colors.BLUE),
            'completed': QColor(Colors.GREEN),
            'failed': QColor(Colors.RED),
            'stopped': QColor(Colors.TEXT_MUTED),
        }
        si.setForeground(
            color_map.get(key, QColor(Colors.TEXT_PRIMARY)))

    def _quick_update_stats(self):
        total = len(self.tasks)
        waiting = running = completed = failed = stopped = 0
        for t in self.tasks:
            s = t.status
            if s == TaskStatus.PENDING:
                waiting += 1
            elif s == TaskStatus.RUNNING:
                running += 1
            elif s == TaskStatus.COMPLETED:
                completed += 1
            elif s == TaskStatus.FAILED:
                failed += 1
            elif s == TaskStatus.STOPPED:
                stopped += 1
        self._stat_labels["总任务"].setText(str(total))
        self._stat_labels["等待中"].setText(str(waiting))
        self._stat_labels["运行中"].setText(str(running))
        self._stat_labels["已完成"].setText(str(completed))
        self._stat_labels["已失败"].setText(str(failed))
        self._stat_labels["已停止"].setText(str(stopped))
        self.queue_count_label.setText(
            f"共 {total} 个任务 | 等待 {waiting} | 运行 {running} "
            f"| 完成 {completed} | 失败 {failed} | 停止 {stopped}")

    def update_stats(self):
        self._quick_update_stats()

    def _refresh_running_durations(self):
        """每秒刷新运行中任务的训练时长显示"""
        for row, task in enumerate(self.tasks):
            if task.status != TaskStatus.RUNNING or not task.start_time:
                continue
            dur = _duration_text(task.start_time)
            item = self.task_table.item(row, 6)
            if item and item.text() != dur:
                item.setText(dur)

    def delete_task(self, task_id):
        task = next((t for t in self.tasks if t.id == task_id), None)
        if not task:
            return
        # 确认弹窗：运行中任务需先停止
        if task.status == TaskStatus.RUNNING:
            msg = f"任务 #{task_id} 正在运行中。\n确定停止并删除该任务？"
        else:
            msg = f"确定删除任务 #{task_id}？"
        reply = QMessageBox.question(
            self, "确认删除", msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                if (task.status == TaskStatus.RUNNING
                        and task_id in self.task_threads):
                    try:
                        self.task_threads[task_id].stop()
                    except Exception:
                        pass
                    self.task_threads.pop(task_id, None)
                self.tasks.pop(i)
                for row in range(self.task_table.rowCount()):
                    it = self.task_table.item(row, 0)
                    if it and it.text() == str(task_id):
                        self.task_table.removeRow(row)
                        break
                self.add_to_log("任务", f"任务 {task_id} 已删除")
                self._quick_update_stats()
                break

    def render_tasks(self):
        """增量更新任务表格：复用已有行，仅插入/移除差异行。"""
        table = self.task_table
        current_row_count = table.rowCount()
        target_count = len(self.tasks)

        # 删除多余的行（从末尾开始删）
        while table.rowCount() > target_count:
            table.removeRow(table.rowCount() - 1)

        # 补齐缺少的行
        while table.rowCount() < target_count:
            table.insertRow(table.rowCount())

        # 逐行更新内容
        for row, task in enumerate(self.tasks):
            self._update_table_row(row, task)

    def _update_table_row(self, row, task):
        """更新单行内容（增量），避免重建 widget。"""
        table = self.task_table
        # 检查是否需要更新基础字段
        id_item = table.item(row, 0)
        if id_item is None or id_item.text() != str(task.id):
            # ID 不同说明是换了一个任务，需要整行重建
            dur = _duration_text(task.start_time, task.end_time)
            gpu_text = (f"GPU {task.gpu_id}" if task.gpu_id >= 0
                        else "自动")
            items = [
                QTableWidgetItem(str(task.id)),
                QTableWidgetItem(task.config.experiment_name),
                QTableWidgetItem(str(task.config.max_epochs)),
                QTableWidgetItem(str(task.config.batch_size)),
                QTableWidgetItem(gpu_text),
                QTableWidgetItem(task.add_time),
                QTableWidgetItem(dur),
                QTableWidgetItem(self._status_name(task.status)),
            ]
            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row, col, item)
            self._set_row_status_color(row, task.status)
            pw = make_progress_widget(task)
            table.setCellWidget(row, 8, pw)
            ow = make_ops_widget(task.id, task.status, self._ops_handlers)
            table.setCellWidget(row, 9, ow)
            table.setRowHeight(row, 42)
        else:
            # 同一任务，只更新变化的字段
            exp_item = table.item(row, 1)
            if exp_item and exp_item.text() != task.config.experiment_name:
                exp_item.setText(task.config.experiment_name)
            epoch_item = table.item(row, 2)
            if epoch_item and epoch_item.text() != str(task.config.max_epochs):
                epoch_item.setText(str(task.config.max_epochs))
            batch_item = table.item(row, 3)
            if batch_item and batch_item.text() != str(task.config.batch_size):
                batch_item.setText(str(task.config.batch_size))
            gpu_item = table.item(row, 4)
            gpu_text = (f"GPU {task.gpu_id}" if task.gpu_id >= 0
                        else "自动")
            if gpu_item and gpu_item.text() != gpu_text:
                gpu_item.setText(gpu_text)
            time_item = table.item(row, 5)
            if time_item and time_item.text() != task.add_time:
                time_item.setText(task.add_time)
            # 训练时长
            dur = _duration_text(task.start_time, task.end_time)
            dur_item = table.item(row, 6)
            if dur_item and dur_item.text() != dur:
                dur_item.setText(dur)
            status_item = table.item(row, 7)
            new_status = self._status_name(task.status)
            if status_item and status_item.text() != new_status:
                status_item.setText(new_status)
                self._set_row_status_color(row, task.status)
                ow = make_ops_widget(task.id, task.status, self._ops_handlers)
                table.setCellWidget(row, 9, ow)
            # 更新进度
            pw = table.cellWidget(row, 8)
            if pw and hasattr(pw, '_progress_bar'):
                pct = task.progress_info.progress_percent
                pw._progress_bar.setValue(int(pct))
                update_progress_bar_style(pw._progress_bar, pct)
                pw._epoch_label.setText(
                    f"{task.progress_info.epoch}/{task.progress_info.total_epochs}")

    def clear_queue(self):
        if not self.tasks:
            return
        # 检查是否有运行中任务，提示不同
        running_count = sum(
            1 for t in self.tasks if t.status == TaskStatus.RUNNING)
        if running_count > 0:
            msg = (f"队列中有 {len(self.tasks)} 个任务"
                   f"（其中 {running_count} 个正在运行）。\n"
                   f"确定全部停止并清空？此操作不可撤销。")
        else:
            msg = f"确定清空全部 {len(self.tasks)} 个任务？此操作不可撤销。"
        reply = QMessageBox.question(
            self, "确认清空", msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        # 停止所有运行中的线程
        for tid, thread in list(self.task_threads.items()):
            try:
                thread.stop()
            except Exception:
                pass
        self.task_threads.clear()
        if self.scheduler:
            self.scheduler.stop()
            self.scheduler = None
        self.tasks.clear()
        self.task_table.setRowCount(0)
        self._quick_update_stats()
        self.add_to_log("警告", "队列已清空")

    def clone_task(self, task_id: int):
        """克隆指定任务：复制配置，生成新 ID，状态置为 PENDING"""
        src = next((t for t in self.tasks if t.id == task_id), None)
        if not src:
            return
        from copy import deepcopy
        new_task = Task(
            id=self.task_id_counter,
            config=deepcopy(src.config),
            gpu_id=src.gpu_id,
            wait_seconds=src.wait_seconds,
            status=TaskStatus.PENDING,
            progress_info=ProgressInfo(total_epochs=src.config.max_epochs,
                                       status_text="等待调度"),
            add_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self.tasks.append(new_task)
        row = self.task_table.rowCount()
        self.task_table.insertRow(row)
        self._populate_table_row(row, new_task)
        self.task_id_counter += 1
        self._quick_update_stats()
        self.add_to_log("任务", f"任务 {task_id} 已克隆为新任务 {new_task.id}")

    def retry_task(self, task_id: int):
        """将已停止/失败的任务重置为 PENDING，可重新调度"""
        task = next((t for t in self.tasks if t.id == task_id), None)
        if not task:
            return
        if task.status not in (TaskStatus.FAILED, TaskStatus.STOPPED,
                               TaskStatus.COMPLETED):
            self.add_to_log("警告", "只有已完成/已停止/失败的任务可以重试")
            return
        task.status = TaskStatus.PENDING
        task.start_time = None
        task.end_time = None
        task.progress_info = ProgressInfo(
            total_epochs=task.config.max_epochs, status_text="等待调度")
        self.render_tasks()
        self._quick_update_stats()
        self.add_to_log("任务", f"任务 {task_id} 已重置为等待状态，可重新调度")
