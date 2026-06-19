"""
全局配置：应用名、配色方案、主题管理。
"""

APP_TITLE = "🌸 GPU 任务管理器"
APP_VERSION = "v2.1.0"

# ==================== 主题色彩定义 ====================
_THEMES = {
    'light': {
        # ── 基础色 ──
        'BG':            "#F8F6F3",   # 奶油白背景
        'CARD_BG':       "#FFFFFF",   # 纯白卡片
        'TEXT_PRIMARY':  "#3D3539",   # 深棕主文字
        'TEXT_SECONDARY': "#9A919A",  # 柔和灰紫次要
        'TEXT_MUTED':    "#C4BCC4",   # 淡灰紫弱化文字
        'BORDER':        "#EDEBE8",   # 极柔和边框
        # ── 粉彩点缀色 ──
        'ACCENT':        "#E8A0BF",   # 樱花粉
        'ACCENT2':       "#B8A9D4",   # 薰衣草紫
        'ACCENT3':       "#9DC5B5",   # 薄荷绿
        'ACCENT4':       "#F0B6A4",   # 蜜桃色
        'ACCENT5':       "#F2D4A8",   # 暖金色
        # ── 语义色 ──
        'GREEN':         "#7BC8A4",   # 翠绿
        'RED':           "#F2868B",   # 珊瑚红
        'BLUE':          "#82B1D4",   # 天空蓝
        'ORANGE':        "#F5C177",   # 金橙
        # ── 表面/渐变 ──
        'SHADOW':        "rgba(0,0,0,0.03)",
        'SHADOW_CARD':   "rgba(200,180,190,0.12)",  # 卡片柔和阴影
        'GRADIENT_TOP':  "#FDF2F8",   # 淡粉底色/表头
        'CARD_HOVER':    "#FFF8FC",   # 卡片悬停淡粉
        'ROW_ALT':       "#FFF9FC",   # 表格交替行（淡粉）
        # ── 按钮辅助 ──
        'BTN_HOVER':     "#F5EEF5",   # 通用按钮悬停
    },
    'dark': {
        # ── 基础色 ──
        'BG':            "#1A1B2E",   # 深蓝黑背景
        'CARD_BG':       "#252640",   # 深灰蓝卡片
        'TEXT_PRIMARY':  "#E8E6F0",   # 浅色文字
        'TEXT_SECONDARY': "#9694AE",  # 次要文字
        'TEXT_MUTED':    "#605E78",   # 淡灰文字
        'BORDER':        "#3A3854",   # 深边框
        # ── 粉彩点缀色（暗色下更饱和） ──
        'ACCENT':        "#E8A0BF",   # 樱花粉
        'ACCENT2':       "#B8A9D4",   # 薰衣草紫
        'ACCENT3':       "#9DC5B5",   # 薄荷绿
        'ACCENT4':       "#F0B6A4",   # 蜜桃色
        'ACCENT5':       "#F2D4A8",   # 暖金色
        # ── 语义色 ──
        'GREEN':         "#7BC8A4",
        'RED':           "#F2868B",
        'BLUE':          "#82B1D4",
        'ORANGE':        "#F5C177",
        # ── 表面/渐变 ──
        'SHADOW':        "rgba(0,0,0,0.20)",
        'SHADOW_CARD':   "rgba(0,0,0,0.30)",
        'GRADIENT_TOP':  "#302E48",
        'CARD_HOVER':    "#2E2C46",
        'ROW_ALT':       "#2A2842",
        'BTN_HOVER':     "#3A3854",
    },
}


class Colors:
    """主题色彩类：支持 light/dark 切换，保持类属性向后兼容。"""
    _current_theme = 'light'

    @classmethod
    def set_theme(cls, theme_name):
        if theme_name not in _THEMES:
            return
        cls._current_theme = theme_name
        theme = _THEMES[theme_name]
        for key, value in theme.items():
            setattr(cls, key, value)

    @classmethod
    def get_theme(cls):
        return cls._current_theme

    @classmethod
    def available_themes(cls):
        return list(_THEMES.keys())


# 初始化默认主题
Colors.set_theme('light')


# ==================== 状态文本/颜色 ====================
STATUS_NAMES = {
    'pending': '⏳ 等待中',
    'running': '▶ 运行中',
    'completed': '✅ 已完成',
    'failed': '❌ 失败',
    'stopped': '⏹ 已停止',
}
