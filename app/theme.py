LIGHT_QSS = """
* { font-family: "LXGW ZhenKai", "LXGW WenKai Screen", "Noto Sans CJK SC", "Noto Sans SC", sans-serif; font-size: 13px; }
QMainWindow, QWidget { background-color: #1e1e2e; color: #1a1a1a; }
QToolBar { background: #f5f5f5; border-bottom: 1px solid #313244; spacing: 4px; padding: 4px; }
QToolBar QToolButton {
    background: transparent; border: none; padding: 6px 10px; border-radius: 6px;
    color: #cdd6f4; min-width: 50px;
}
QToolBar QToolButton:hover { background: #e6e9ef; }
QToolBar QToolButton:pressed { background: #45475a; }
QToolBar QToolButton:checked { background: #cba6f7; color: white; }

#Sidebar {
    background: #f5f5f5; border-right: 1px solid #313244;
}
#Sidebar QListWidget {
    background: transparent; border: none; padding: 8px; outline: none;
}
#Sidebar QListWidget::item {
    padding: 10px 14px; border-radius: 8px; margin: 2px 4px; color: #45475a;
}
#Sidebar QListWidget::item:hover { background: #313244; }
#Sidebar QListWidget::item:selected { background: #cba6f7; color: white; }

#StatusBar {
    background: #f5f5f5; border-top: 1px solid #313244; color: #a6adc8;
}

QTabWidget::pane { border: 1px solid #313244; border-radius: 6px; background: #fff; top: -1px; }
QTabBar::tab {
    background: transparent; padding: 8px 16px; margin-right: 2px;
    border-bottom: 2px solid transparent; color: #a6adc8;
}
QTabBar::tab:selected { color: #cba6f7; border-bottom-color: #cba6f7; background: #fff; }
QTabBar::tab:hover { color: #cdd6f4; }

QPushButton {
    background: #cba6f7; color: white; border: none; padding: 8px 16px;
    border-radius: 6px; font-weight: 500;
}
QPushButton:hover { background: #b4befe; }
QPushButton:pressed { background: #a78bfa; }
QPushButton:disabled { background: #585b70; color: #7f849c; }
QPushButton#secondary { background: #313244; color: #45475a; }
QPushButton#secondary:hover { background: #585b70; }
QPushButton#danger { background: #ef4444; }
QPushButton#danger:hover { background: #dc2626; }

QSlider::groove:horizontal {
    height: 6px; background: #313244; border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #cba6f7; width: 16px; height: 16px; margin: -6px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover { background: #b4befe; }
QSlider::sub-page:horizontal { background: #cba6f7; border-radius: 3px; }

QLabel#section { font-size: 14px; font-weight: 600; color: #45475a; padding: 8px 2px; }
QLabel#hint { color: #7f849c; font-size: 12px; }

QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {
    padding: 6px 10px; border: 1px solid #585b70; border-radius: 6px;
    background: #fff; color: #cdd6f4; min-height: 20px;
}
QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus {
    border-color: #cba6f7;
}

QGroupBox {
    border: 1px solid #313244; border-radius: 8px; margin-top: 14px;
    padding-top: 10px; font-weight: 600; color: #45475a;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 0 6px; background: #f5f5f5;
}

QCheckBox { padding: 4px; spacing: 6px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #585b70; }
QCheckBox::indicator:checked { background: #cba6f7; border-color: #cba6f7; image: none; }

QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #585b70; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #7f849c; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QSplitter::handle { background: #313244; width: 2px; }
"""

DARK_QSS = """
* { font-family: "LXGW ZhenKai", "LXGW WenKai Screen", "Noto Sans CJK SC", "Noto Sans SC", sans-serif; font-size: 13px; }
QMainWindow, QWidget { background-color: #1e1e2e; color: #cdd6f4; }
QToolBar { background: #181825; border-bottom: 1px solid #313244; spacing: 6px; padding: 7px 10px; }
QToolBar QToolButton {
    background: transparent; border: none; padding: 7px 11px; border-radius: 8px;
    color: #cdd6f4; min-width: 50px;
}
QToolBar QToolButton:hover { background: #313244; }
QToolBar QToolButton:pressed { background: #45475a; }
QToolBar QToolButton:checked { background: #cba6f7; color: white; }

#Sidebar { background: #181825; border-right: 1px solid #313244; }
#Sidebar QListWidget { background: transparent; border: none; padding: 8px; outline: none; }
#Sidebar QListWidget::item { padding: 11px 14px; border-radius: 10px; margin: 2px 3px; color: #a6adc8; }
#Sidebar QListWidget::item:hover { background: #313244; }
#Sidebar QListWidget::item:selected { background: #cba6f7; color: white; }

#StatusBar { background: #11111b; border-top: 1px solid #313244; color: #a6adc8; }

QTabWidget::pane { border: 1px solid #313244; border-radius: 6px; background: #11111b; top: -1px; }
QTabBar::tab { background: transparent; padding: 8px 16px; margin-right: 2px; border-bottom: 2px solid transparent; color: #a6adc8; }
QTabBar::tab:selected { color: #cba6f7; border-bottom-color: #cba6f7; }
QTabBar::tab:hover { color: #313244; }

QPushButton { background: #cba6f7; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: 500; }
QPushButton:hover { background: #b4befe; }
QPushButton:disabled { background: #45475a; color: #7f849c; }
QPushButton#secondary { background: #45475a; color: #313244; }
QPushButton#secondary:hover { background: #585b70; }
QPushButton#danger { background: #dc2626; }

QSlider::groove:horizontal { height: 6px; background: #45475a; border-radius: 3px; }
QSlider::handle:horizontal { background: #cba6f7; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }
QSlider::sub-page:horizontal { background: #cba6f7; border-radius: 3px; }

QLabel#section { font-size: 14px; font-weight: 700; color: #cdd6f4; padding: 8px 2px; }
QLabel#hint { color: #a6adc8; font-size: 12px; }

QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {
    padding: 8px 11px; border: 1px solid #45475a; border-radius: 9px;
    background: #181825; color: #cdd6f4; min-height: 20px;
}
QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus { border-color: #cba6f7; }

QGroupBox { border: 1px solid #45475a; border-radius: 12px; margin-top: 14px; padding: 12px 10px 10px; font-weight: 700; color: #cdd6f4; background: #181825; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 7px; background: #181825; color: #cba6f7; }

QCheckBox { padding: 4px; spacing: 6px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #585b70; background: #313244; }
QCheckBox::indicator:checked { background: #cba6f7; border-color: #cba6f7; }

QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #585b70; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #7f849c; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QSplitter::handle { background: #45475a; width: 2px; }
QLabel#appTitle { font-size: 18px; font-weight: 800; letter-spacing: 1px; padding: 8px 6px 4px; color: #cba6f7; }
QLineEdit#toolSearch { padding: 9px 12px; border-radius: 11px; border: 1px solid #45475a; background: #11111b; color: #cdd6f4; selection-background-color: #cba6f7; }
QListWidget#SidebarList { border: none; outline: none; background: transparent; }
"""
