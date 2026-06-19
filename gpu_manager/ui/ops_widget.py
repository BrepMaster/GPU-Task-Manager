"""
操作列按钮组件 + 进度列组件。
根据任务状态展示不同的按钮组合（停止/上移/下移/删除）。
"""
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QProgressBar, QLabel,
)
from PyQt5.QtCore import Qt

from ..core.config import Colors
from ..core.models import TaskStatus


def _lerp_color(c1, c2, t):
    """线性插值两个十六进制颜色，t 在 [0, 1]"""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _progress_colors(pct):
    """
    根据进度百分比返回 (渐变色起点, 渐变色终点)。
    0% → 珊瑚红，50% → 清新浅绿，100% → 深邃墨绿。
    """
    pct = max(0.0, min(100.0, pct))
    if pct <= 50:
        t = pct / 50.0
        cs = _lerp_color("#F2868B", "#B5E8C3", t)  # 珊瑚红 → 浅绿
        ce = _lerp_color("#E8636B", "#8DD4A8", t)  # 深红   → 柔绿
    else:
        t = (pct - 50) / 50.0
        cs = _lerp_color("#B5E8C3", "#4CAF6E", t)  # 浅绿 → 翠绿
        ce = _lerp_color("#8DD4A8", "#2E8B57", t)  # 柔绿 → 墨绿
    return cs, ce


def update_progress_bar_style(pb, pct):
    """更新 QProgressBar 的 chunk 渐变色（红→浅绿→深绿），相同值跳过"""
    # 缓存：进度值没变就跳过昂贵的 setStyleSheet
    last = getattr(pb, '_last_color_pct', None)
    rounded = int(pct)
    if last == rounded:
        return
    pb._last_color_pct = rounded
    cs, ce = _progress_colors(pct)
    pb.setStyleSheet(f"""
        QProgressBar {{
            background-color: {Colors.GRADIENT_TOP};
            border: none;
            border-radius: 7px;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 {cs}, stop:1 {ce});
            border-radius: 6px;
        }}
    """)


def make_ops_widget(task_id, status, handlers):
    """
    构造操作列 widget。

    handlers: dict，需要提供以下回调：
      - stop_task(task_id)     : 停止任务
      - delete_task(task_id)   : 删除任务
      - move_task_up(task_id)  : 上移任务
      - move_task_down(task_id): 下移任务
      - clone_task(task_id)    : 克隆任务
      - retry_task(task_id)    : 重试任务
    """
    status_key = status.value if isinstance(status, TaskStatus) else status
    w = QWidget()
    w.setStyleSheet(f"background-color: {Colors.CARD_BG};")
    l = QHBoxLayout(w)
    l.setContentsMargins(3, 3, 3, 3)
    l.setSpacing(3)
    l.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    def make_btn(text, color, hover_color, tooltip, callback, fixed_w=38):
        """描边风格按钮：彩色边框+文字，hover 填充底色"""
        b = QPushButton(text)
        b.setFixedHeight(26)
        b.setFixedWidth(fixed_w)
        b.setToolTip(tooltip)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {color};
                border: 1.5px solid {color};
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: white;
            }}
            QPushButton:pressed {{
                background-color: {hover_color};
                border-color: {hover_color};
                color: white;
            }}
        """)
        b.clicked.connect(lambda checked, cb=callback: cb())
        return b

    if status_key == 'running':
        stop_b = make_btn(
            "停止", Colors.BLUE, Colors.ACCENT2,
            f"停止任务 {task_id}",
            lambda tid=task_id: handlers['stop_task'](tid),
            fixed_w=40)
        l.addWidget(stop_b)
        del_b = make_btn(
            "×", Colors.TEXT_MUTED, Colors.RED,
            f"删除任务 {task_id}",
            lambda tid=task_id: handlers['delete_task'](tid),
            fixed_w=26)
        l.addWidget(del_b)
    elif status_key == 'pending':
        clone_b = make_btn(
            "克隆", Colors.ACCENT5, Colors.ORANGE,
            "克隆任务",
            lambda tid=task_id: handlers['clone_task'](tid))
        l.addWidget(clone_b)
        up_b = make_btn(
            "↑", Colors.ACCENT3, Colors.GREEN,
            "上移",
            lambda tid=task_id: handlers['move_task_up'](tid),
            fixed_w=26)
        l.addWidget(up_b)
        dwb = make_btn(
            "↓", Colors.ACCENT3, Colors.GREEN,
            "下移",
            lambda tid=task_id: handlers['move_task_down'](tid),
            fixed_w=26)
        l.addWidget(dwb)
        del_b = make_btn(
            "×", Colors.RED, Colors.ACCENT4,
            "删除任务",
            lambda tid=task_id: handlers['delete_task'](tid),
            fixed_w=26)
        l.addWidget(del_b)
    else:
        retry_b = make_btn(
            "重试", Colors.BLUE, Colors.ACCENT2,
            "重试任务",
            lambda tid=task_id: handlers['retry_task'](tid))
        l.addWidget(retry_b)
        clone_b = make_btn(
            "克隆", Colors.ACCENT5, Colors.ORANGE,
            "克隆任务",
            lambda tid=task_id: handlers['clone_task'](tid))
        l.addWidget(clone_b)
        del_b = make_btn(
            "×", Colors.RED, Colors.ACCENT4,
            "删除任务",
            lambda tid=task_id: handlers['delete_task'](tid),
            fixed_w=26)
        l.addWidget(del_b)

    return w


def make_progress_widget(task):
    """进度列 widget：进度条 + epoch 标签（如 0/200）"""
    w = QWidget()
    w.setStyleSheet(f"background-color: {Colors.CARD_BG};")
    l = QHBoxLayout(w)
    l.setContentsMargins(6, 2, 6, 2)
    l.setSpacing(4)

    pi = task.progress_info
    pp = pi.progress_percent
    pb = QProgressBar()
    pb.setMinimum(0)
    pb.setMaximum(100)
    pb.setValue(int(pp))
    pb.setTextVisible(False)
    pb.setFixedHeight(14)
    update_progress_bar_style(pb, pp)
    l.addWidget(pb)

    # epoch 标签：如 "50/200"
    el = QLabel(f"{pi.epoch}/{pi.total_epochs}")
    el.setStyleSheet(
        f"color: {Colors.ACCENT}; font-size: 11px; font-weight: bold; "
        f"background: transparent; border: none;")
    el.setFixedWidth(56)
    el.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    l.addWidget(el)

    w._progress_bar = pb
    w._epoch_label = el
    return w
