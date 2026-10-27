"""
ui/controller.py - Refined Compact Control Panel for Miss Minutes.

Follows the reference design from the 'Miss Minutes - Expressions & States' specification:
- Mini character avatar badge with real-time status indicator.
- Prominent Manual ON/OFF power button.
- Clean activity & state status card.
- Comprehensive 10-state visual simulator grid for interactive QA.
- Reduced-motion toggle and clean close actions.
- Position persistence support.
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.expressions import get_visual_config
from ui.state_machine import AppStateMachine, AssistantState
from ui.theme import Theme


class MiniAvatarWidget(QWidget):
    """Small procedural Miss Minutes avatar icon for the control panel header."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._is_online = False

    def set_online(self, online: bool) -> None:
        if self._is_online != online:
            self._is_online = online
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        bezel_col = QColor("#d97706" if self._is_online else "#54473b")
        face_col = QColor("#fefbf3" if self._is_online else "#d4cbba")
        eye_col = QColor("#451a03" if self._is_online else "#4a3f35")

        # Casing
        painter.setBrush(QBrush(bezel_col))
        painter.setPen(QPen(bezel_col.darker(130), 1.2))
        painter.drawEllipse(QRectF(2, 2, 24, 24))

        # Face
        painter.setBrush(QBrush(face_col))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(4.5, 4.5, 19, 19))

        # Eyes
        painter.setBrush(QBrush(eye_col))
        if self._is_online:
            painter.drawEllipse(QRectF(9, 10, 3, 4))
            painter.drawEllipse(QRectF(16, 10, 3, 4))
            # Smile
            painter.setPen(QPen(eye_col, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawArc(QRectF(10, 14, 8, 5), -30 * 16, -120 * 16)
        else:
            # Sleeping slits
            painter.setPen(QPen(eye_col, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(8, 12, 12, 12)
            painter.drawLine(16, 12, 20, 12)
            painter.drawLine(11, 16, 17, 16)


class MissMinutesController(QWidget):
    """
    Compact desktop control panel for Miss Minutes.
    """

    exit_requested = Signal()
    position_changed = Signal(QPoint)
    reduced_motion_toggled = Signal(bool)
    delegation_demo_requested = Signal()
    capability_demo_requested = Signal()
    voice_session_requested = Signal()
    command_submitted = Signal(str)

    def __init__(
        self,
        state_machine: AppStateMachine,
        parent: Optional[QWidget] = None,
        reduced_motion: bool = False,
    ) -> None:
        super().__init__(parent)
        self._state_machine = state_machine
        self._reduced_motion = reduced_motion
        self._drag_start_pos: Optional[QPoint] = None
        self._sim_buttons: Dict[AssistantState, QPushButton] = {}

        self.setObjectName("ControllerWindow")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # Compact size
        self.setFixedSize(315, 415)
        self.setStyleSheet(Theme.controller_stylesheet())

        self._build_ui()
        self._connect_signals()
        self._update_state_display(self._state_machine.current_state, self._state_machine.current_state)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(8)

        # 1. Header Bar: Avatar + Title + Status Dot + Close
        header = QHBoxLayout()
        header.setSpacing(8)

        self._avatar = MiniAvatarWidget()
        header.addWidget(self._avatar)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self._title_label = QLabel("Miss Minutes")
        self._title_label.setObjectName("HeaderTitle")

        self._status_dot = QLabel("● Assistant is OFF")
        self._status_dot.setObjectName("HeaderStatusDot")
        self._status_dot.setStyleSheet("color: #ef4444;")

        title_box.addWidget(self._title_label)
        title_box.addWidget(self._status_dot)
        header.addLayout(title_box, 1)

        self._close_btn = QPushButton("✕")
        self._close_btn.setObjectName("CloseButton")
        self._close_btn.setToolTip("Close Miss Minutes")
        self._close_btn.clicked.connect(self._on_close_clicked)
        header.addWidget(self._close_btn)

        main_layout.addLayout(header)

        # 2. Prominent Manual ON/OFF Power Button
        self._power_btn = QPushButton("TURN ON ASSISTANT")
        self._power_btn.setObjectName("PowerButton")
        self._power_btn.setProperty("online", "false")
        self._power_btn.clicked.connect(self._on_power_clicked)
        main_layout.addWidget(self._power_btn)

        # 3. Status Card (Current State Badge + Human-readable Activity)
        status_card = QFrame()
        status_card.setObjectName("StatusCard")
        card_layout = QVBoxLayout(status_card)
        card_layout.setContentsMargins(10, 6, 10, 6)
        card_layout.setSpacing(2)

        badge_row = QHBoxLayout()
        state_caption = QLabel("CURRENT STATE:")
        state_caption.setStyleSheet("font-size: 9px; color: #a89a88; font-weight: 700; letter-spacing: 0.5px;")
        badge_row.addWidget(state_caption)

        self._state_badge = QLabel("OFFLINE")
        self._state_badge.setObjectName("StateBadge")
        badge_row.addWidget(self._state_badge)
        badge_row.addStretch(1)
        card_layout.addLayout(badge_row)

        self._msg_label = QLabel("Assistant is OFF. Not listening, not working.")
        self._msg_label.setStyleSheet("font-size: 11px; color: #fdf8f0;")
        self._msg_label.setWordWrap(True)
        card_layout.addWidget(self._msg_label)

        main_layout.addWidget(status_card)

        # 3b. Interactive Command & Search Bar
        cmd_layout = QHBoxLayout()
        cmd_layout.setSpacing(4)
        self._cmd_input = QLineEdit()
        self._cmd_input.setObjectName("CmdInput")
        self._cmd_input.setPlaceholderText("Type command (Chrome, WhatsApp, Screen)...")
        self._cmd_input.setStyleSheet("background-color: #1a1512; color: #fdf8f0; border: 1px solid #b45309; border-radius: 4px; padding: 4px 6px; font-size: 11px;")
        self._send_btn = QPushButton("Send")
        self._send_btn.setObjectName("SendBtn")
        self._send_btn.setStyleSheet("background-color: #f59e0b; color: #1a1512; font-weight: bold; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        self._send_btn.clicked.connect(self._on_send_command)
        self._cmd_input.returnPressed.connect(self._on_send_command)
        cmd_layout.addWidget(self._cmd_input, 1)
        cmd_layout.addWidget(self._send_btn)
        main_layout.addLayout(cmd_layout)

        # 4. Interactive State Simulator Section
        sim_header = QLabel("VISUAL STATE SIMULATOR (12 STATES)")
        sim_header.setStyleSheet("font-size: 9px; color: #8c7f70; font-weight: 700; letter-spacing: 0.4px;")
        main_layout.addWidget(sim_header)

        grid = QGridLayout()
        grid.setSpacing(4)

        # Map simulation buttons to corresponding states
        sim_states = [
            ("Wake", AssistantState.WAKE_DETECTED),
            ("Listen", AssistantState.LISTENING),
            ("Transcribe", AssistantState.TRANSCRIBING),
            ("Think", AssistantState.THINKING),
            ("Validate", AssistantState.VALIDATING),
            ("Work", AssistantState.WORKING),
            ("Speak", AssistantState.SPEAKING),
            ("Success", AssistantState.SUCCESS),
            ("Error", AssistantState.ERROR),
            ("Blocked", AssistantState.BLOCKED),
        ]

        for idx, (label, target_state) in enumerate(sim_states):
            row = idx // 5
            col = idx % 5
            btn = QPushButton(label)
            btn.setObjectName("StateGridBtn")
            btn.setToolTip(f"Simulate state: {target_state.value}")
            # Bind closure cleanly
            btn.clicked.connect(lambda checked=False, s=target_state: self._on_sim_state_clicked(s))
            self._sim_buttons[target_state] = btn
            grid.addWidget(btn, row, col)

        main_layout.addLayout(grid)

        # 5. Demos Bar: Dual-Agent Delegation & Phase 4 Telugu-English Capability Pipeline
        demos_bar = QHBoxLayout()
        demos_bar.setSpacing(6)

        self._delegation_btn = QPushButton("⚡ Jarvis Demo")
        self._delegation_btn.setObjectName("BottomToolBtn")
        self._delegation_btn.setStyleSheet("background-color: #2b2016; color: #fbbf24; border: 1px solid #d97706; font-weight: 700; font-size: 10px; padding: 4px;")
        self._delegation_btn.setToolTip("Demonstrates autonomous delegation from Miss Minutes to Jarvis")
        self._delegation_btn.clicked.connect(self._on_delegation_clicked)
        demos_bar.addWidget(self._delegation_btn, 1)

        self._cap_demo_btn = QPushButton("🎵 Capability")
        self._cap_demo_btn.setObjectName("BottomToolBtn")
        self._cap_demo_btn.setStyleSheet("background-color: #1f2937; color: #60a5fa; border: 1px solid #3b82f6; font-weight: 700; font-size: 10px; padding: 4px;")
        self._cap_demo_btn.setToolTip("Demonstrates mock pipeline: 'YouTube open chesi AR Rahman songs play cheyyi'")
        self._cap_demo_btn.clicked.connect(self._on_cap_demo_clicked)
        demos_bar.addWidget(self._cap_demo_btn, 1)

        self._voice_btn = QPushButton("🎤 Voice")
        self._voice_btn.setObjectName("BottomToolBtn")
        self._voice_btn.setStyleSheet("background-color: #064e3b; color: #34d399; border: 1px solid #10b981; font-weight: 700; font-size: 10px; padding: 4px;")
        self._voice_btn.setToolTip("Start real voice interaction (Hey Minutes / Microphone)")
        self._voice_btn.clicked.connect(self._on_voice_clicked)
        demos_bar.addWidget(self._voice_btn, 1)

        main_layout.addLayout(demos_bar)

        # 6. Bottom Controls (Motion Toggle + Close)
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self._motion_btn = QPushButton("Motion: Normal")
        self._motion_btn.setObjectName("BottomToolBtn")
        self._motion_btn.setToolTip("Toggle reduced motion / animations")
        self._motion_btn.clicked.connect(self._on_motion_clicked)
        bottom_bar.addWidget(self._motion_btn, 1)

        self._exit_btn = QPushButton("Close App")
        self._exit_btn.setObjectName("BottomToolBtn")
        self._exit_btn.clicked.connect(self._on_close_clicked)
        bottom_bar.addWidget(self._exit_btn, 1)

        main_layout.addLayout(bottom_bar)

    def _connect_signals(self) -> None:
        self._state_machine.state_changed.connect(self._update_state_display)
        self._state_machine.status_message_changed.connect(self._update_message)

    def _update_state_display(self, new_state: AssistantState, old_state: AssistantState) -> None:
        online = self._state_machine.is_online
        cfg = get_visual_config(new_state)

        # Update Avatar
        self._avatar.set_online(online)

        # Update Status Dot
        if online:
            self._status_dot.setText("● Assistant is ON")
            self._status_dot.setStyleSheet("color: #10b981;")
            self._power_btn.setText("TURN OFF ASSISTANT")
            self._power_btn.setProperty("online", "true")
        else:
            self._status_dot.setText("● Assistant is OFF")
            self._status_dot.setStyleSheet("color: #ef4444;")
            self._power_btn.setText("TURN ON ASSISTANT")
            self._power_btn.setProperty("online", "false")

        # Update State Badge
        self._state_badge.setText(new_state.value)
        badge_style = (
            f"background-color: {cfg.badge_bg.name()}; "
            f"color: #ffffff; "
            f"border: 1px solid {cfg.bezel_color.name()};"
        )
        self._state_badge.setStyleSheet(badge_style)

        # Enable/Disable simulation grid buttons based on online status
        for btn in self._sim_buttons.values():
            btn.setEnabled(online)
        self._delegation_btn.setEnabled(online)
        self._cap_demo_btn.setEnabled(online)
        self._voice_btn.setEnabled(online)

        # Force stylesheet re-polish on power button
        self._power_btn.style().unpolish(self._power_btn)
        self._power_btn.style().polish(self._power_btn)

    def _update_message(self, message: str) -> None:
        self._msg_label.setText(message)

    def _on_power_clicked(self) -> None:
        self._state_machine.toggle_power()

    def _on_send_command(self) -> None:
        text = self._cmd_input.text().strip()
        if text and self._state_machine.is_online:
            self._cmd_input.clear()
            self.command_submitted.emit(text)

    def _on_delegation_clicked(self) -> None:
        if self._state_machine.is_online:
            self.delegation_demo_requested.emit()

    def _on_cap_demo_clicked(self) -> None:
        if self._state_machine.is_online:
            self.capability_demo_requested.emit()

    def _on_voice_clicked(self) -> None:
        if self._state_machine.is_online:
            self.voice_session_requested.emit()

    def _on_sim_state_clicked(self, target_state: AssistantState) -> None:
        if self._state_machine.is_online:
            cfg = get_visual_config(target_state)
            self._state_machine.transition_to(target_state, cfg.description)

    def _on_motion_clicked(self) -> None:
        self._reduced_motion = not self._reduced_motion
        self._motion_btn.setText("Motion: Reduced" if self._reduced_motion else "Motion: Normal")
        self.reduced_motion_toggled.emit(self._reduced_motion)

    def _on_close_clicked(self) -> None:
        self.exit_requested.emit()

    # --- Mouse Dragging Support ---

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_start_pos
            self.move(new_pos)
            self.position_changed.emit(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = None
            self.position_changed.emit(self.pos())
            event.accept()
