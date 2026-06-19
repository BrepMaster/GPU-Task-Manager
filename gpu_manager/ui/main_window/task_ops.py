"""
MainWindow 的任务执行相关方法：调度器、任务启动/停止、进度/输出回调、拖拽排序。
"""
from datetime import datetime

from ...core.scheduler import TaskScheduler
from ...core.task_thread import TaskThread
from ...core.models import TaskStatus
from ..ops_widget import make_ops_widget, update_progress_bar_style
from ..dialogs import TaskEditDialog, TaskDetailDialog
from ...core.logger import get_logger

logger = get_logger('task_ops')


class TaskOpsMixin:
    """任务执行、调度、编辑、排序相关方法"""

    def start_scheduler(self):
        if self.scheduler and self.scheduler.isRunning():
            self.add_to_log("警告", "调度器已在运行中")
            return
        pending = [t for t in self.tasks if t.status == TaskStatus.PENDING]
        if not pending:
            self.add_to_log("警告", "没有等待中的任务")
            return
        # 清理旧的 scheduler
        if self.scheduler:
            try:
                self.scheduler.task_ready.disconnect(self.on_task_ready)
                self.scheduler.quit()
                self.scheduler.wait(2000)
            except (RuntimeError, AttributeError):
                pass
            self.scheduler.deleteLater()
        self.scheduler = TaskScheduler()
        self.scheduler.task_ready.connect(self.on_task_ready)
        self.scheduler.start()
        for task in pending:
            self.scheduler.add_task(task.id, task.config, task.gpu_id)
        self.add_to_log("调度器", "调度器已启动")

    def on_task_ready(self, task_id, gpu_id):
        task = next((t for t in self.tasks if t.id == task_id), None)
        if not task:
            return
        task.status = TaskStatus.RUNNING
        task.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 更新 gpu_id（自动选择的任务在此刻获得实际 GPU）
        task.gpu_id = gpu_id
        for row in range(self.task_table.rowCount()):
            if self.task_table.item(row, 0).text() == str(task_id):
                si = self.task_table.item(row, 7)
                si.setText(self._status_name(TaskStatus.RUNNING))
                self._set_row_status_color(row, TaskStatus.RUNNING)
                ow = make_ops_widget(
                    task_id, TaskStatus.RUNNING, self._ops_handlers)
                self.task_table.setCellWidget(row, 9, ow)
                # 更新 GPU 列
                gpu_item = self.task_table.item(row, 4)
                if gpu_item:
                    gpu_item.setText(f"GPU {gpu_id}")
                break
        worker = TaskThread(task_id, task.config, gpu_id)
        worker.task_output.connect(self.on_task_output)
        worker.task_finished.connect(self.on_task_finished)
        worker.task_progress.connect(self.on_task_progress)
        worker.start()
        self.task_threads[task_id] = worker
        self._quick_update_stats()
        self.add_to_log(
            "调度器", f"任务 {task_id} 开始在 GPU {gpu_id} 上执行")

    def on_task_output(self, task_id, output):
        self.add_to_log(f"任务{task_id}", output)

    def on_task_finished(self, task_id, status, message):
        try:
            status_enum = TaskStatus(status)
        except ValueError:
            status_enum = TaskStatus.FAILED
        task = next((t for t in self.tasks if t.id == task_id), None)
        if task:
            task.status = status_enum
            task.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for row in range(self.task_table.rowCount()):
                if self.task_table.item(row, 0).text() == str(task_id):
                    si = self.task_table.item(row, 7)
                    si.setText(self._status_name(status_enum))
                    self._set_row_status_color(row, status_enum)
                    ow = make_ops_widget(
                        task_id, status_enum, self._ops_handlers)
                    self.task_table.setCellWidget(row, 9, ow)
                    if status_enum == TaskStatus.COMPLETED:
                        pw = self.task_table.cellWidget(row, 8)
                        if pw and hasattr(pw, '_progress_bar'):
                            pw._progress_bar.setValue(100)
                            total = task.progress_info.total_epochs
                            pw._epoch_label.setText(f"{total}/{total}")
                    break
        if task_id in self.task_threads:
            worker = self.task_threads.pop(task_id)
            worker.deleteLater()
        self._quick_update_stats()
        # 实时更新详情窗口
        self._update_detail_if_open(task_id)
        # 桌面通知（窗口不在前台时）
        if status_enum == TaskStatus.COMPLETED:
            self._show_notification(
                "GPU 任务管理器",
                f"任务 #{task_id} 已完成 ✓")
        elif status_enum == TaskStatus.FAILED:
            self._show_notification(
                "GPU 任务管理器",
                f"任务 #{task_id} 失败 ✗")
        self.add_to_log(
            "调度器",
            f"任务 {task_id} "
            f"{'完成' if status_enum == TaskStatus.COMPLETED else '失败'}")

    def on_task_progress(self, task_id, progress_info):
        task = next((t for t in self.tasks if t.id == task_id), None)
        if task:
            task.progress_info = progress_info
            for row in range(self.task_table.rowCount()):
                if self.task_table.item(row, 0).text() == str(task_id):
                    pw = self.task_table.cellWidget(row, 8)
                    if pw and hasattr(pw, '_progress_bar'):
                        pct = progress_info.progress_percent
                        pw._progress_bar.setValue(int(pct))
                        update_progress_bar_style(pw._progress_bar, pct)
                        epoch = progress_info.epoch
                        total = progress_info.total_epochs
                        pw._epoch_label.setText(f"{epoch}/{total}")
                        pw._progress_bar.setToolTip(
                            f"Epoch {epoch}/{total} ({pct:.1f}%)")
                    break
        # 实时更新详情窗口
        self._update_detail_if_open(task_id)

    def stop_task(self, task_id):
        task = next((t for t in self.tasks if t.id == task_id), None)
        if not task:
            return
        if task.status == TaskStatus.RUNNING and task_id in self.task_threads:
            try:
                self.task_threads[task_id].stop()
            except Exception as e:
                logger.warning("stop_task thread error: %s", e)
            self.task_threads.pop(task_id, None)
        if self.scheduler:
            self.scheduler.release_task_gpu(task_id)
        if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
            task.status = TaskStatus.STOPPED
            task.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for row in range(self.task_table.rowCount()):
            it = self.task_table.item(row, 0)
            if it and it.text() == str(task_id):
                si = self.task_table.item(row, 7)
                if si:
                    si.setText(self._status_name(TaskStatus.STOPPED))
                self._set_row_status_color(row, TaskStatus.STOPPED)
                ow = make_ops_widget(
                    task_id, TaskStatus.STOPPED, self._ops_handlers)
                self.task_table.setCellWidget(row, 9, ow)
                break
        self._quick_update_stats()
        self.add_to_log("警告", f"任务 {task_id} 已停止")

    def stop_all(self):
        if self.scheduler:
            self.scheduler.stop()
        for tid, thread in list(self.task_threads.items()):
            thread.stop()
        for task in self.tasks:
            if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                task.status = TaskStatus.STOPPED
        self._quick_update_stats()
        self.render_tasks()
        self.add_to_log("警告", "所有任务已停止")

    def _on_task_row_clicked(self, row):
        """_TaskTable.rowClicked 回调：单击行弹出任务详情"""
        if row < 0 or row >= len(self.tasks):
            return
        task = self.tasks[row]
        self._show_task_detail(task)

    def on_row_moved(self, logical_index, old_visual_index, new_visual_index):
        if old_visual_index == new_visual_index:
            return
        try:
            vh = self.task_table.verticalHeader()
            old_logical = vh.logicalIndex(old_visual_index)
            new_logical = vh.logicalIndex(new_visual_index)
            if old_logical < 0 or new_logical < 0:
                return
            if (old_logical >= len(self.tasks)
                    or new_logical >= len(self.tasks)):
                return
            task = self.tasks.pop(old_logical)
            self.tasks.insert(new_logical, task)
            self.render_tasks()
            self.add_to_log("系统", f"任务 {task.id} 顺序已调整")
        except (IndexError, ValueError) as e:
            logger.warning("Row reorder error: %s", e)

    def move_task_up(self, task_id):
        for i, task in enumerate(self.tasks):
            if task.id == task_id and i > 0:
                self.tasks[i], self.tasks[i - 1] = (
                    self.tasks[i - 1], self.tasks[i])
                self.render_tasks()
                self.add_to_log("系统", f"任务 {task_id} 已上移")
                return

    def move_task_down(self, task_id):
        for i, task in enumerate(self.tasks):
            if task.id == task_id and i < len(self.tasks) - 1:
                self.tasks[i], self.tasks[i + 1] = (
                    self.tasks[i + 1], self.tasks[i])
                self.render_tasks()
                self.add_to_log("系统", f"任务 {task_id} 已下移")
                return

    # ── 右键菜单 ──────────────────────────────────────────────────────────

    def on_task_context_menu(self, pos):
        from PyQt5.QtWidgets import QMenu
        from ...core.config import Colors
        row = self.task_table.rowAt(pos.y())
        if row < 0 or row >= len(self.tasks):
            return
        task = self.tasks[row]
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Colors.CARD_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
                color: {Colors.TEXT_PRIMARY};
            }}
            QMenu::item:selected {{
                background-color: {Colors.GRADIENT_TOP};
            }}
            QMenu::separator {{
                height: 1px;
                background: {Colors.BORDER};
                margin: 4px 10px;
            }}
        """)
        if task.status == TaskStatus.RUNNING:
            act_stop = menu.addAction("■ 停止")
            act_stop.triggered.connect(
                lambda: self.stop_task(task.id))
        if task.status in (TaskStatus.FAILED, TaskStatus.STOPPED,
                           TaskStatus.COMPLETED):
            act_retry = menu.addAction("🔄 重试")
            act_retry.triggered.connect(
                lambda: self.retry_task(task.id))
        act_clone = menu.addAction("📋 克隆")
        act_clone.triggered.connect(
            lambda: self.clone_task(task.id))
        if task.status != TaskStatus.RUNNING:
            act_edit = menu.addAction("✏️ 编辑")
            act_edit.triggered.connect(
                lambda: self._edit_task(task))
        menu.addSeparator()
        act_detail = menu.addAction("🔍 详情")
        act_detail.triggered.connect(
            lambda: self._show_task_detail(task))
        menu.addSeparator()
        act_del = menu.addAction("✕ 删除")
        act_del.triggered.connect(
            lambda: self.delete_task(task.id))
        menu.exec_(self.task_table.viewport().mapToGlobal(pos))

    def _show_task_detail(self, task):
        # 如果已有该任务的详情窗口，激活它而不是新建
        if not hasattr(self, '_detail_dialogs'):
            self._detail_dialogs = {}
        existing = self._detail_dialogs.get(task.id)
        if existing and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        from ..dialogs import TaskDetailDialog
        dlg = TaskDetailDialog(task, self)
        dlg.show()
        self._detail_dialogs[task.id] = dlg
        dlg.destroyed.connect(
            lambda: self._detail_dialogs.pop(task.id, None))

    def _update_detail_if_open(self, task_id):
        """如果指定任务有打开的详情窗口，刷新其内容"""
        if not hasattr(self, '_detail_dialogs'):
            return
        dlg = self._detail_dialogs.get(task_id)
        if dlg and dlg.isVisible():
            task = next((t for t in self.tasks if t.id == task_id), None)
            if task:
                dlg.update_from_task(task)

    def _edit_task(self, task):
        """右键菜单 → 编辑任务参数"""
        from PyQt5.QtWidgets import QDialog
        from ..dialogs import TaskEditDialog
        dialog = TaskEditDialog(task, self)
        if dialog.exec_() == QDialog.Accepted:
            task.config = dialog.get_config()
            task.gpu_id = dialog.get_gpu_id()
            task.wait_seconds = dialog.get_wait_seconds()
            task.progress_info.total_epochs = task.config.max_epochs
            self.render_tasks()
            self.add_to_log("任务", f"任务 {task.id} 参数已更新")

    # ── 键盘快捷键 ────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent, Qt
        if obj is self.task_table and event.type() == QEvent.KeyPress:
            row = self.task_table.currentRow()
            if 0 <= row < len(self.tasks):
                task = self.tasks[row]
                if event.key() == Qt.Key_Delete:
                    self.delete_task(task.id)
                    return True
                if (event.modifiers() == Qt.ControlModifier
                        and event.key() == Qt.Key_D):
                    self.clone_task(task.id)
                    return True
                if (event.modifiers() == Qt.ControlModifier
                        and event.key() == Qt.Key_R):
                    self.retry_task(task.id)
                    return True
        return super().eventFilter(obj, event)
