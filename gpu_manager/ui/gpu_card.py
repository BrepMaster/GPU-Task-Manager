"""
GPU 卡片组件：显示每个 GPU 的使用率、显存、温度、功耗。
"""
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton
from PyQt5.QtCore import Qt

from ..core.config import Colors


class GPUCardsPanel:
    """管理 GPU 卡片列表：首次重建，之后增量更新。"""

    def __init__(self, layout, on_lock_toggle=None):
        self._layout = layout
        self._card_widgets = {}  # gpu_index -> card widget
        self._locked_gpus = set()  # 被锁定的 GPU 索引
        self._on_lock_toggle = on_lock_toggle  # 回调: (gpu_id, locked) -> None

    def clear(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._card_widgets.clear()

    @property
    def locked_gpus(self):
        return self._locked_gpus

    def _toggle_lock(self, gpu_id):
        if gpu_id in self._locked_gpus:
            self._locked_gpus.discard(gpu_id)
        else:
            self._locked_gpus.add(gpu_id)
        # 更新按钮状态
        w = self._card_widgets.get(gpu_id)
        if w and hasattr(w, '_lock_btn'):
            locked = gpu_id in self._locked_gpus
            w._lock_btn.setText("🔒" if locked else "🔓")
            w._lock_btn.setToolTip(
                "已锁定 - 调度器不会使用此GPU（点击解锁）" if locked
                else "未锁定（点击锁定，调度器将跳过此GPU）")
            w._lock_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.RED if locked else Colors.GRADIENT_TOP};
                    color: {Colors.CARD_BG if locked else Colors.TEXT_SECONDARY};
                    border: 1px solid {Colors.RED if locked else Colors.BORDER};
                    border-radius: 8px;
                    font-size: 14px; padding: 4px;
                }}
                QPushButton:hover {{ opacity: 0.8; }}
            """)
        if self._on_lock_toggle:
            self._on_lock_toggle(gpu_id, gpu_id in self._locked_gpus)

    def update(self, gpu_count, usages, memories, temps, powers, names):
        """根据 GPU 数量决定重建还是增量更新"""
        if len(self._card_widgets) != gpu_count:
            self._rebuild(gpu_count, usages, memories, temps, powers, names)
            return
        for i in range(gpu_count):
            w = self._card_widgets.get(i)
            if not w:
                continue
            usage = usages[i] if i < len(usages) else 0
            mem_used, mem_total = (
                memories[i] if i < len(memories) else (0, 0))
            temp = temps[i] if i < len(temps) else 0
            power_draw, power_limit = (
                powers[i] if i < len(powers) else (0.0, 0.0))

            if hasattr(w, '_usage_bar'):
                w._usage_bar.setValue(usage)
                w._usage_bar.setFormat(f"{usage}%")
                w._usage_bar.setStyleSheet(self._bar_style(usage))

            if hasattr(w, '_mem_bar'):
                mem_pct = (
                    int(mem_used / mem_total * 100) if mem_total > 0 else 0)
                w._mem_bar.setValue(mem_pct)
                w._mem_bar.setFormat(f"{mem_used}/{mem_total}MB")
                w._mem_bar.setStyleSheet(
                    self._bar_style(mem_pct, is_memory=True))

            if hasattr(w, '_temp_label'):
                tc = (Colors.GREEN if temp < 70
                      else (Colors.ORANGE if temp < 85 else Colors.RED))
                w._temp_label.setText(f"🌡 {temp}°C")
                w._temp_label.setStyleSheet(
                    f"color: {tc}; font-size: 11px; "
                    f"background: transparent; border: none;")

            if hasattr(w, '_power_label'):
                txt = f"⚡ {power_draw:.0f}W"
                if power_limit > 0:
                    txt += f"/{power_limit:.0f}W"
                w._power_label.setText(txt)

    def _rebuild(self, gpu_count, usages, memories, temps, powers, names):
        self.clear()
        for i in range(gpu_count):
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {Colors.CARD_BG};
                    border-radius: 14px;
                    border: 1px solid {Colors.BORDER};
                }}
            """)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 10, 14, 10)
            cl.setSpacing(5)

            usage = usages[i] if i < len(usages) else 0
            mem_used, mem_total = (
                memories[i] if i < len(memories) else (0, 0))
            temp = temps[i] if i < len(temps) else 0
            power_draw, power_limit = (
                powers[i] if i < len(powers) else (0.0, 0.0))
            name = names[i] if i < len(names) else f"GPU {i}"

            # 标题行 + 锁定按钮
            hdr = QHBoxLayout()
            nl = QLabel(f"🖥 GPU {i} — {name}")
            nl.setStyleSheet(
                f"color: {Colors.TEXT_PRIMARY}; font-weight: bold; "
                f"font-size: 12px; background: transparent; border: none;")
            hdr.addWidget(nl)
            hdr.addStretch()
            locked = i in self._locked_gpus
            lock_btn = QPushButton("🔒" if locked else "🔓")
            lock_btn.setFixedSize(28, 28)
            lock_btn.setCursor(Qt.PointingHandCursor)
            lock_btn.setToolTip(
                "已锁定 - 调度器不会使用此GPU（点击解锁）" if locked
                else "未锁定（点击锁定，调度器将跳过此GPU）")
            lock_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.RED if locked else Colors.GRADIENT_TOP};
                    color: {Colors.CARD_BG if locked else Colors.TEXT_SECONDARY};
                    border: 1px solid {Colors.RED if locked else Colors.BORDER};
                    border-radius: 8px;
                    font-size: 14px; padding: 4px;
                }}
                QPushButton:hover {{ opacity: 0.8; }}
            """)
            lock_btn.clicked.connect(
                lambda checked, gid=i: self._toggle_lock(gid))
            hdr.addWidget(lock_btn)
            cl.addLayout(hdr)

            # 使用率
            ul = QHBoxLayout()
            ul.setSpacing(6)
            ul.addWidget(QLabel("使用率:"))
            ub = QProgressBar()
            ub.setMaximum(100)
            ub.setValue(usage)
            ub.setTextVisible(True)
            ub.setFormat(f"{usage}%")
            ub.setFixedHeight(12)
            ub.setStyleSheet(self._bar_style(usage))
            ul.addWidget(ub)
            cl.addLayout(ul)

            # 显存
            ml = QHBoxLayout()
            ml.setSpacing(6)
            ml.addWidget(QLabel("显存:"))
            mp = int(mem_used / mem_total * 100) if mem_total > 0 else 0
            mb = QProgressBar()
            mb.setMaximum(100)
            mb.setValue(mp)
            mb.setTextVisible(True)
            mb.setFormat(f"{mem_used}/{mem_total}MB")
            mb.setFixedHeight(12)
            mb.setStyleSheet(self._bar_style(mp, is_memory=True))
            ml.addWidget(mb)
            cl.addLayout(ml)

            # 温度/功耗
            il = QHBoxLayout()
            il.setSpacing(12)
            tc = (Colors.GREEN if temp < 70
                  else (Colors.ORANGE if temp < 85 else Colors.RED))
            tlb = QLabel(f"🌡 {temp}°C")
            tlb.setStyleSheet(
                f"color: {tc}; font-size: 11px; "
                f"background: transparent; border: none;")
            il.addWidget(tlb)
            ptxt = f"⚡ {power_draw:.0f}W"
            if power_limit > 0:
                ptxt += f"/{power_limit:.0f}W"
            plb = QLabel(ptxt)
            plb.setStyleSheet(
                f"color: {Colors.ACCENT5}; font-size: 11px; "
                f"background: transparent; border: none;")
            il.addWidget(plb)
            il.addStretch()
            cl.addLayout(il)

            card._usage_bar = ub
            card._mem_bar = mb
            card._temp_label = tlb
            card._power_label = plb
            card._lock_btn = lock_btn

            self._layout.addWidget(card)
            self._card_widgets[i] = card

    @staticmethod
    def _bar_style(value, is_memory=False):
        if is_memory:
            cs, ce = Colors.ACCENT2, Colors.ACCENT
        else:
            if value < 50:
                cs, ce = Colors.ACCENT3, Colors.GREEN
            elif value < 80:
                cs, ce = Colors.ORANGE, Colors.ACCENT5
            else:
                cs, ce = Colors.RED, Colors.ACCENT4
        return f"""
            QProgressBar {{
                background-color: {Colors.GRADIENT_TOP};
                border: none;
                border-radius: 6px;
                font-size: 9px;
                color: {Colors.TEXT_PRIMARY};
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {cs}, stop:1 {ce});
                border-radius: 5px;
            }}
        """
