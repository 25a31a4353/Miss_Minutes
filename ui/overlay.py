"""
ui/overlay.py - Expressive Miss Minutes Desktop Character Overlay & Speech Bubble.

Implements the authentic floating desktop companion matching the visual specifications
in the reference desktop screenshot and Expressions & States sheet:
- Small, transparent, frameless, floating, always-on-top, draggable desktop companion.
- Procedural vector clock character with radiating TVA sunburst rays, gloved hands, cartoon shoes.
- All 12 FSM states with distinct facial expressions, poses, props, and animations.
- Dynamic floating/bobbing motion with smooth sine-wave vertical travel.
- Visually and behaviorally distinct LISTENING vs THINKING, WORKING, SPEAKING, SUCCESS, ERROR vs BLOCKED.
- True 32-bit ARGB per-pixel transparency with zero opaque rectangular backgrounds.
- WM_NCHITTEST click-through for empty transparent corner areas on Windows.
- Floating status pill directly underneath: '● Miss Minutes • Idle' with interactive mic button.
- Companion speech bubble floating beside character displaying contextual dialogue.
- Reduced-motion accessibility mode.
- Desktop position persistence and multi-monitor boundary clamping.
"""

from __future__ import annotations

import math
import sys
from typing import Optional

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QMenu, QWidget

from ui.expressions import (
    ArmPose,
    EyebrowType,
    EyeShape,
    LegPose,
    MouthShape,
    StateProp,
    StateVisualConfig,
    get_visual_config,
)
from ui.state_machine import AppStateMachine, AssistantState


class SpeechBubbleWidget(QWidget):
    """
    Transparent companion speech bubble floating beside Miss Minutes.
    Shows contextual dialogue (e.g. 'Yes? I'm listening...', 'Working on it...')
    matching the reference desktop screenshot.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(175, 75)

        self._user_prompt: str = ""
        self._dialogue: str = ""

    def update_dialogue(self, dialogue: str, user_prompt: str = "") -> None:
        self._dialogue = dialogue
        self._user_prompt = user_prompt
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._dialogue and not self._user_prompt:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        font = painter.font()
        font.setFamily("Segoe UI")

        y_offset = 4.0

        # 1. User Prompt Bubble (e.g. '👤 Hey Minutes')
        if self._user_prompt:
            u_rect = QRectF(6, y_offset, self.width() - 12, 24)
            painter.setBrush(QBrush(QColor(26, 20, 16, 230)))
            painter.setPen(QPen(QColor(180, 83, 9, 140), 1.0))
            painter.drawRoundedRect(u_rect, 12, 12)

            font.setPointSize(8)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QPen(QColor("#d4cbba")))
            painter.drawText(u_rect, Qt.AlignmentFlag.AlignCenter, f"👤 {self._user_prompt}")
            y_offset += 28.0

        # 2. Assistant Dialogue Bubble (e.g. 'Yes? I'm listening...')
        if self._dialogue:
            card_h = 36.0 if len(self._dialogue) < 28 else 44.0
            r_rect = QRectF(6, y_offset, self.width() - 12, card_h)

            painter.setBrush(QBrush(QColor(22, 17, 13, 235)))
            painter.setPen(QPen(QColor("#f59e0b"), 1.2))
            painter.drawRoundedRect(r_rect, 12, 12)

            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QPen(QColor("#fdf8f0")))
            inner = QRectF(14, y_offset + 3, self.width() - 28, card_h - 6)
            painter.drawText(
                inner,
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                self._dialogue,
            )


class MissMinutesOverlay(QWidget):
    """
    Transparent floating character overlay with expressive animated states,
    floating status pill, and companion speech bubble.
    """

    controller_toggle_requested = Signal()
    position_changed = Signal(QPoint)
    voice_session_requested = Signal()

    def __init__(
        self,
        state_machine: AppStateMachine,
        parent: Optional[QWidget] = None,
        always_on_top: bool = True,
        reduced_motion: bool = False,
    ) -> None:
        super().__init__(parent)
        self._state_machine = state_machine
        self._reduced_motion = reduced_motion
        self._drag_start_pos: Optional[QPoint] = None
        self._mic_hovered = False

        # True top-level tool window: enables hardware-accelerated 32-bit ARGB DWM transparency
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)

        # 150x170 design footprint accommodating 140px character and status pill
        self.setFixedSize(150, 170)

        # Companion floating speech bubble
        self._bubble = SpeechBubbleWidget()

        # Connect state machine signals
        self._state_machine.state_changed.connect(self._on_state_changed)
        self._state_machine.status_message_changed.connect(self._on_status_message_changed)

        # Animation state
        self._anim_phase = 0.0
        self._blink_counter = 0
        self._is_blinking = False

        # Dialogue timeout timer: hides dialogue after inactivity in IDLE state
        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.setInterval(7000)
        self._bubble_timer.timeout.connect(self._on_bubble_timeout)

        # High-smoothness lightweight animation loop (~32 FPS, 31ms interval)
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(31)
        self._anim_timer.timeout.connect(self._on_anim_tick)

        if not self._reduced_motion:
            self._anim_timer.start()

        self._update_tooltip()

        # Initial dialogue setup
        cfg = get_visual_config(self._state_machine.current_state)
        self._bubble.update_dialogue(cfg.dialogue)

    @property
    def reduced_motion(self) -> bool:
        return self._reduced_motion

    @reduced_motion.setter
    def reduced_motion(self, value: bool) -> None:
        self._reduced_motion = bool(value)
        if self._reduced_motion:
            self._anim_timer.stop()
        else:
            self._anim_timer.start()
        self.update()

    # --- Windows Native Hit-Testing (Click-through for transparent corners) ---

    def nativeEvent(self, eventType, message):
        """
        On Windows, intercepts WM_NCHITTEST to return HTTRANSPARENT (-1) for clicks
        on transparent corner pixels, allowing desktop icons and wallpaper behind
        Miss Minutes to be clicked directly without using setMask() which destroys alpha.
        Uses QCursor.pos() so High-DPI screen scaling (e.g. 150%) maps correctly to logical points.
        """
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                from PySide6.QtGui import QCursor
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == 0x0084:  # WM_NCHITTEST
                    local_pos = self.mapFromGlobal(QCursor.pos())
                    # Check if inside character body/rays, status pill, or mic button
                    char_hit = (local_pos.x() - 75.0) ** 2 + (local_pos.y() - 66.0) ** 2 <= (56.0 ** 2)
                    pill_hit = self._get_status_pill_rect().adjusted(-2, -6, 2, 6).contains(local_pos)
                    mic_hit = self._get_mic_btn_rect().contains(local_pos)
                    if not (char_hit or pill_hit or mic_hit):
                        return True, -1  # HTTRANSPARENT: let Windows pass click through!
            except Exception:
                pass
        return super().nativeEvent(eventType, message)

    # --- Geometry Helpers ---

    def _get_status_pill_rect(self) -> QRect:
        """Returns the bounding rectangle of the floating status pill."""
        return QRect(6, 136, 138, 28)

    def _get_mic_btn_rect(self) -> QRect:
        """Returns the generous hit-box of the microphone button on the status pill."""
        return QRect(102, 130, 44, 38)

    def _sync_bubble_position(self) -> None:
        """Keeps the companion speech bubble aligned beside Miss Minutes."""
        if self._bubble.isVisible():
            self._bubble.move(self.x() + self.width() + 6, self.y() + 12)

    # --- State & Message Handlers ---

    def _on_state_changed(self, new_state: AssistantState, old_state: AssistantState) -> None:
        cfg = get_visual_config(new_state)
        self._update_tooltip()
        self._anim_phase = 0.0
        self._is_blinking = False

        user_prompt = ""
        dialogue = cfg.dialogue

        if new_state == AssistantState.WAKE_DETECTED:
            user_prompt = "Hey Minutes"
            dialogue = "Yes? I'm listening..."
            self._bubble_timer.stop()
        elif new_state == AssistantState.IDLE:
            dialogue = cfg.dialogue or "Ready and waiting for your command!"
            self._bubble_timer.start()
        elif new_state == AssistantState.OFFLINE:
            dialogue = cfg.dialogue
            self._bubble_timer.start()
        else:
            self._bubble_timer.stop()

        self._bubble.update_dialogue(dialogue, user_prompt)
        if self.isVisible():
            self._bubble.show()
            self._sync_bubble_position()

        self.update()

    def _on_status_message_changed(self, message: str) -> None:
        if message:
            self._bubble.update_dialogue(message)
            if self._state_machine.current_state == AssistantState.IDLE:
                self._bubble_timer.start()
            if self.isVisible():
                self._bubble.show()
                self._sync_bubble_position()
            self.update()

    def _on_bubble_timeout(self) -> None:
        if self._state_machine.current_state in (AssistantState.IDLE, AssistantState.OFFLINE):
            self._bubble.hide()

    def _update_tooltip(self) -> None:
        cfg = get_visual_config(self._state_machine.current_state)
        self.setToolTip(
            f"Miss Minutes — [{cfg.title}]\n"
            f"{cfg.description}\n\n"
            f"• Left-click + drag: move character\n"
            f"• Double-click: toggle Control Panel\n"
            f"• Right-click: context options\n"
            f"• Click mic icon: voice interaction"
        )

    def _on_anim_tick(self) -> None:
        if self._reduced_motion:
            return

        state = self._state_machine.current_state
        if state == AssistantState.OFFLINE:
            self._anim_phase = (self._anim_phase + 0.02) % (2.0 * math.pi)
        else:
            self._anim_phase = (self._anim_phase + 0.075) % (2.0 * math.pi)

            # Natural blinking logic every ~90-100 frames (~3.5 seconds)
            self._blink_counter += 1
            if self._blink_counter > 95:
                self._is_blinking = True
                if self._blink_counter > 99:
                    self._is_blinking = False
                    self._blink_counter = 0

        self.update()

    # --- Mouse & Interaction Handling ---

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            # Check if clicked on the status pill or mic button
            pill_area = self._get_status_pill_rect().adjusted(-2, -6, 2, 6)
            if pill_area.contains(pos) or self._get_mic_btn_rect().contains(pos):
                if not self._state_machine.is_online:
                    self._state_machine.turn_on()
                else:
                    self.voice_session_requested.emit()
                event.accept()
                return

            self._drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        pill_area = self._get_status_pill_rect().adjusted(-2, -6, 2, 6)
        is_hover = pill_area.contains(pos) or self._get_mic_btn_rect().contains(pos)
        if is_hover != self._mic_hovered:
            self._mic_hovered = is_hover
            if self._mic_hovered:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()

        if self._drag_start_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_start_pos
            self.move(new_pos)
            self._sync_bubble_position()
            self.position_changed.emit(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = None
            self.position_changed.emit(self.pos())
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.controller_toggle_requested.emit()
            event.accept()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._sync_bubble_position()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._state_machine.is_online or self._state_machine.current_state == AssistantState.IDLE:
            self._bubble.show()
            self._sync_bubble_position()
            self._bubble_timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._bubble.hide()

    def closeEvent(self, event) -> None:
        self._bubble.close()
        super().closeEvent(event)

    def _show_context_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #221c17;
                color: #f7f1e6;
                border: 1px solid #544436;
                border-radius: 8px;
                padding: 6px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #f59e0b;
                color: #1a1309;
                font-weight: 600;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3d3226;
                margin: 4px 6px;
            }
        """)

        online = self._state_machine.is_online
        power_action = menu.addAction("Turn OFF Assistant" if online else "Turn ON Assistant")
        panel_action = menu.addAction("Open Control Panel")
        menu.addSeparator()

        motion_text = "Enable Animations" if self._reduced_motion else "Reduce Motion"
        motion_action = menu.addAction(motion_text)
        menu.addSeparator()

        exit_action = menu.addAction("Exit Miss Minutes")

        action = menu.exec(global_pos)
        if action == power_action:
            self._state_machine.toggle_power()
        elif action == panel_action:
            self.controller_toggle_requested.emit()
        elif action == motion_action:
            self.reduced_motion = not self._reduced_motion
        elif action == exit_action:
            self.window().close()

    # --- Procedural Vector Character Rendering ---

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        state = self._state_machine.current_state
        cfg = get_visual_config(state)

        # Character Center and Radii
        cx = 75.0
        cy = 64.0
        body_radius = 35.0

        # Substantial, clearly observable floating/bobbing sine wave (~10px travel)
        pulse = 0.0 if self._reduced_motion else math.sin(self._anim_phase)
        bob_y = 0.0 if (self._reduced_motion or state == AssistantState.OFFLINE) else (5.0 * pulse)

        # Celebratory victory hop during SUCCESS
        if state == AssistantState.SUCCESS and not self._reduced_motion:
            bob_y = -7.0 * abs(math.sin(self._anim_phase * 2.5))

        cy += bob_y

        active_r = body_radius + (0.8 * pulse if cfg.glow_intensity > 0 else 0.0)

        # 1. Outer Glow Aura
        if cfg.glow_intensity > 0.01:
            glow_r = active_r + 14.0 + (3.0 * pulse)
            rad_grad = QRadialGradient(cx, cy, glow_r)
            glow_color = QColor(cfg.accent_color)
            glow_color.setAlphaF(min(0.68, cfg.glow_intensity + (0.12 * pulse)))
            rad_grad.setColorAt(0.65, glow_color)
            rad_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(rad_grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))

        # 2. TVA Sunburst Rays (radiating halo around casing)
        if state != AssistantState.OFFLINE:
            self._draw_sunburst_rays(painter, cx, cy, active_r, cfg, pulse)

        # 3. Cartoon Legs & Shoes
        self._draw_legs_and_shoes(painter, cx, cy, active_r, cfg, pulse)

        # 4. Cartoon Gloved Arms
        self._draw_arms_and_hands(painter, cx, cy, active_r, cfg, pulse)

        # 5. Clock Outer Bezel (Retro Amber / Copper)
        bezel_pen = QPen(cfg.bezel_color.darker(135), 3.2)
        painter.setPen(bezel_pen)
        painter.setBrush(QBrush(cfg.bezel_color))
        painter.drawEllipse(QRectF(cx - active_r, cy - active_r, active_r * 2, active_r * 2))

        # 6. Clock Dial Face (Cream / Parchment)
        dial_r = active_r - 4.2
        painter.setPen(QPen(cfg.bezel_color.darker(160), 1.0))
        painter.setBrush(QBrush(cfg.face_color))
        painter.drawEllipse(QRectF(cx - dial_r, cy - dial_r, dial_r * 2, dial_r * 2))

        # 7. Dial Rim Tick Marks
        painter.save()
        painter.translate(cx, cy)
        tick_col = QColor(cfg.eye_color)
        tick_col.setAlphaF(0.45)
        painter.setPen(QPen(tick_col, 1.2))
        for i in range(12):
            length = 3.5 if i % 3 == 0 else 2.0
            painter.drawLine(0, -int(dial_r - 2), 0, -int(dial_r - 2 - length))
            painter.rotate(30)
        painter.restore()

        # 8. Rosy Cheeks
        if state != AssistantState.OFFLINE:
            blush_col = QColor(249, 115, 22, 40)
            painter.setBrush(QBrush(blush_col))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(cx - 21, cy + 2, 8, 5))
            painter.drawEllipse(QRectF(cx + 13, cy + 2, 8, 5))

        # 9. Clock Hands
        self._draw_clock_hands(painter, cx, cy, cfg, pulse)

        # 10. Cartoon Eyes & Eyelashes
        self._draw_eyes_and_brows(painter, cx, cy, cfg)

        # 11. Expressive Mouth
        self._draw_mouth(painter, cx, cy, cfg, pulse)

        # 12. State Prop (Soundwaves, Thought Cloud, Spinning Gears, Checkmark, etc.)
        self._draw_prop(painter, cx, cy, cfg, pulse)

        # 13. Floating Status Pill (Anchored underneath character)
        self._draw_status_pill(painter, cfg, state)

    # --- Sunburst Rays (TVA Clock Halo) ---

    def _draw_sunburst_rays(
        self,
        painter: QPainter,
        cx: float,
        cy: float,
        radius: float,
        cfg: StateVisualConfig,
        pulse: float,
    ) -> None:
        """Draws the signature radiating clock spikes around Miss Minutes' casing."""
        num_rays = 16
        ray_base_r = radius + 1.2
        ray_len = 10.0 + (1.5 * pulse)

        painter.save()
        painter.translate(cx, cy)

        # Visible orbital rotation during WORKING state
        if cfg.state == AssistantState.WORKING and not self._reduced_motion:
            painter.rotate(math.degrees(self._anim_phase * 1.5))

        ray_color = QColor(cfg.accent_color)
        ray_pen = QPen(ray_color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(ray_pen)

        for i in range(num_rays):
            is_major = (i % 2 == 0)
            curr_len = ray_len if is_major else (ray_len * 0.65)
            painter.drawLine(0, -int(ray_base_r), 0, -int(ray_base_r + curr_len))
            painter.rotate(360.0 / num_rays)

        painter.restore()

    # --- Cartoon Legs and Shoes ---

    def _draw_legs_and_shoes(
        self,
        painter: QPainter,
        cx: float,
        cy: float,
        body_r: float,
        cfg: StateVisualConfig,
        pulse: float,
    ) -> None:
        leg_color = QColor("#ea580c" if cfg.state != AssistantState.OFFLINE else "#78716c")
        shoe_color = QColor("#c2410c" if cfg.state != AssistantState.OFFLINE else "#57534e")
        sole_color = QColor("#fef3c7" if cfg.state != AssistantState.OFFLINE else "#a8a29e")

        leg_pen = QPen(leg_color, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(leg_pen)

        if cfg.leg_pose == LegPose.SITTING:
            # Relaxed sitting legs (OFFLINE)
            painter.drawLine(int(cx - 15), int(cy + body_r - 4), int(cx - 18), int(cy + body_r + 13))
            painter.drawLine(int(cx + 15), int(cy + body_r - 4), int(cx + 18), int(cy + body_r + 13))
            painter.setBrush(QBrush(shoe_color))
            painter.setPen(QPen(shoe_color.darker(130), 1.2))
            painter.drawEllipse(QRectF(cx - 26, cy + body_r + 9, 15, 8))
            painter.drawEllipse(QRectF(cx + 11, cy + body_r + 9, 15, 8))

        elif cfg.leg_pose == LegPose.STRIDE:
            # Energetic running stride (WORKING)
            swing = 6.0 * math.sin(self._anim_phase * 3) if not self._reduced_motion else 3.0
            painter.drawLine(int(cx - 13), int(cy + body_r - 4), int(cx - 20 - swing), int(cy + body_r + 14))
            painter.drawLine(int(cx + 13), int(cy + body_r - 4), int(cx + 20 + swing), int(cy + body_r + 14))
            painter.setBrush(QBrush(shoe_color))
            painter.setPen(QPen(shoe_color.darker(130), 1.2))
            painter.drawEllipse(QRectF(cx - 28 - swing, cy + body_r + 10, 15, 8))
            painter.drawEllipse(QRectF(cx + 15 + swing, cy + body_r + 10, 15, 8))

        elif cfg.leg_pose == LegPose.CELEBRATING:
            # Kicking up heels in joy (SUCCESS)
            kick = 2.0 * math.sin(self._anim_phase * 3) if not self._reduced_motion else 0.0
            painter.drawLine(int(cx - 13), int(cy + body_r - 4), int(cx - 21), int(cy + body_r + 11 + kick))
            painter.drawLine(int(cx + 13), int(cy + body_r - 4), int(cx + 21), int(cy + body_r + 11 - kick))
            painter.setBrush(QBrush(shoe_color))
            painter.setPen(QPen(shoe_color.darker(130), 1.2))
            painter.drawEllipse(QRectF(cx - 27, cy + body_r + 8 + kick, 15, 8))
            painter.drawEllipse(QRectF(cx + 12, cy + body_r + 8 - kick, 15, 8))

        else:
            # Standing cheerfully (IDLE, LISTENING, THINKING, etc.)
            painter.drawLine(int(cx - 13), int(cy + body_r - 3), int(cx - 14), int(cy + body_r + 14))
            painter.drawLine(int(cx + 13), int(cy + body_r - 3), int(cx + 14), int(cy + body_r + 14))

            painter.setBrush(QBrush(shoe_color))
            painter.setPen(QPen(shoe_color.darker(130), 1.2))
            painter.drawRoundedRect(QRectF(cx - 22, cy + body_r + 10, 15, 7), 3, 3)
            painter.drawRoundedRect(QRectF(cx + 7, cy + body_r + 10, 15, 7), 3, 3)

            painter.setBrush(QBrush(sole_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(cx - 18, cy + body_r + 9, 7, 2))
            painter.drawRect(QRectF(cx + 11, cy + body_r + 9, 7, 2))

    # --- Cartoon Arms and Gloved Hands ---

    def _draw_arms_and_hands(
        self,
        painter: QPainter,
        cx: float,
        cy: float,
        body_r: float,
        cfg: StateVisualConfig,
        pulse: float,
    ) -> None:
        arm_color = QColor("#ea580c" if cfg.state != AssistantState.OFFLINE else "#78716c")
        glove_color = QColor("#ffffff" if cfg.state != AssistantState.OFFLINE else "#e7e5e4")
        glove_border = QColor("#d97706" if cfg.state != AssistantState.OFFLINE else "#78716c")

        arm_pen = QPen(arm_color, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(arm_pen)

        if cfg.arm_pose == ArmPose.RESTING:
            painter.drawLine(int(cx - body_r + 4), int(cy + 10), int(cx - body_r - 9), int(cy + 20))
            painter.drawLine(int(cx + body_r - 4), int(cy + 10), int(cx + body_r + 9), int(cy + 20))
            self._draw_glove(painter, cx - body_r - 11, cy + 20, 6.5, glove_color, glove_border)
            self._draw_glove(painter, cx + body_r + 7, cy + 20, 6.5, glove_color, glove_border)

        elif cfg.arm_pose == ArmPose.WAVING_RIGHT:
            wave = 4.0 * math.sin(self._anim_phase * 2) if not self._reduced_motion else 0.0
            # Left arm bent to hip
            painter.drawLine(int(cx - body_r + 3), int(cy + 8), int(cx - body_r - 11), int(cy + 15))
            painter.drawLine(int(cx - body_r - 11), int(cy + 15), int(cx - body_r + 2), int(cy + 20))
            self._draw_glove(painter, cx - body_r - 2, cy + 18, 5.5, glove_color, glove_border)

            # Right arm raised waving high
            painter.drawLine(int(cx + body_r - 3), int(cy + 6), int(cx + body_r + 13), int(cy - 6 + wave))
            self._draw_glove(painter, cx + body_r + 13, cy - 8 + wave, 7.5, glove_color, glove_border)

        elif cfg.arm_pose == ArmPose.ALERT_EAR:
            painter.drawLine(int(cx - body_r + 3), int(cy + 8), int(cx - body_r - 9), int(cy + 16))
            self._draw_glove(painter, cx - body_r - 11, cy + 16, 6, glove_color, glove_border)

            painter.drawLine(int(cx + body_r - 3), int(cy + 6), int(cx + body_r + 11), int(cy - 10))
            self._draw_glove(painter, cx + body_r + 11, cy - 12, 7, glove_color, glove_border)

        elif cfg.arm_pose == ArmPose.CUPPED_EAR:
            # Cupped hand firmly right next to ear (LISTENING)
            painter.drawLine(int(cx - body_r + 3), int(cy + 10), int(cx - body_r - 7), int(cy + 18))
            self._draw_glove(painter, cx - body_r - 9, cy + 18, 6, glove_color, glove_border)

            painter.drawLine(int(cx + body_r - 3), int(cy + 8), int(cx + body_r + 6), int(cy - 6))
            self._draw_glove(painter, cx + body_r + 6, cy - 10, 8, glove_color, glove_border)

        elif cfg.arm_pose == ArmPose.HOLDING_TABLET:
            painter.drawLine(int(cx - body_r + 4), int(cy + 11), int(cx - 15), int(cy + 20))
            painter.drawLine(int(cx + body_r - 4), int(cy + 11), int(cx + 15), int(cy + 20))
            self._draw_glove(painter, cx - 17, cy + 18, 5.5, glove_color, glove_border)
            self._draw_glove(painter, cx + 11, cy + 18, 5.5, glove_color, glove_border)

        elif cfg.arm_pose == ArmPose.CHIN_THINKER:
            # Left on hip, right holding chin (THINKING)
            painter.drawLine(int(cx - body_r + 3), int(cy + 8), int(cx - body_r - 8), int(cy + 16))
            self._draw_glove(painter, cx - body_r - 9, cy + 16, 6, glove_color, glove_border)

            painter.drawLine(int(cx + body_r - 4), int(cy + 14), int(cx + 4), int(cy + 19))
            self._draw_glove(painter, cx + 2, cy + 15, 7.0, glove_color, glove_border)

        elif cfg.arm_pose == ArmPose.HOLDING_MAGNIFIER:
            painter.drawLine(int(cx - body_r + 3), int(cy + 8), int(cx - body_r - 9), int(cy + 16))
            self._draw_glove(painter, cx - body_r - 9, cy + 16, 6, glove_color, glove_border)

            painter.drawLine(int(cx + body_r - 3), int(cy + 9), int(cx + 18), int(cy - 2))
            self._draw_glove(painter, cx + 16, cy - 4, 6.5, glove_color, glove_border)

        elif cfg.arm_pose == ArmPose.STRIDE_RUN:
            # Active pumping arms in stride (WORKING)
            swing = 7.0 * math.sin(self._anim_phase * 3) if not self._reduced_motion else 3.0
            painter.drawLine(int(cx - body_r + 3), int(cy + 8), int(cx - body_r - 9 - swing), int(cy + 13))
            self._draw_glove(painter, cx - body_r - 11 - swing, cy + 13, 6.5, glove_color, glove_border)

            painter.drawLine(int(cx + body_r - 3), int(cy + 8), int(cx + body_r + 9 + swing), int(cy + 2))
            self._draw_glove(painter, cx + body_r + 9 + swing, cy + 2, 6.5, glove_color, glove_border)

        elif cfg.arm_pose == ArmPose.GESTURE_OUT:
            # Expressive talking gesturing arms (SPEAKING)
            gest = 3.0 * math.sin(self._anim_phase * 3) if not self._reduced_motion else 0.0
            painter.drawLine(int(cx - body_r + 3), int(cy + 8), int(cx - body_r - 13), int(cy + 2 + gest))
            self._draw_glove(painter, cx - body_r - 15, cy + 2 + gest, 7, glove_color, glove_border)

            painter.drawLine(int(cx + body_r - 3), int(cy + 8), int(cx + body_r + 13), int(cy + 2 - gest))
            self._draw_glove(painter, cx + body_r + 11, cy + 2 - gest, 7, glove_color, glove_border)

        elif cfg.arm_pose == ArmPose.DOUBLE_THUMBS_UP:
            # Triumphant double thumbs up (SUCCESS)
            painter.drawLine(int(cx - body_r + 4), int(cy + 8), int(cx - body_r - 12), int(cy - 6))
            painter.drawLine(int(cx + body_r - 4), int(cy + 8), int(cx + body_r + 12), int(cy - 6))
            self._draw_thumbs_up_glove(painter, cx - body_r - 14, cy - 10, is_left=True)
            self._draw_thumbs_up_glove(painter, cx + body_r + 10, cy - 10, is_left=False)

        elif cfg.arm_pose == ArmPose.DROOPING:
            # Sad drooping arms (ERROR)
            painter.drawLine(int(cx - body_r + 3), int(cy + 9), int(cx - body_r - 5), int(cy + 27))
            painter.drawLine(int(cx + body_r - 3), int(cy + 9), int(cx + body_r + 5), int(cy + 27))
            self._draw_glove(painter, cx - body_r - 7, cy + 27, 6, glove_color, glove_border)
            self._draw_glove(painter, cx + body_r + 3, cy + 27, 6, glove_color, glove_border)

        elif cfg.arm_pose == ArmPose.STOP_PALM:
            # Left on hip, bold prominent STOP palm (BLOCKED)
            painter.drawLine(int(cx - body_r + 3), int(cy + 9), int(cx - body_r - 9), int(cy + 18))
            painter.drawLine(int(cx - body_r - 9), int(cy + 18), int(cx - body_r + 2), int(cy + 22))
            self._draw_glove(painter, cx - body_r - 2, cy + 20, 5.5, glove_color, glove_border)

            # High raised forward stop arm
            painter.drawLine(int(cx + body_r - 4), int(cy + 8), int(cx + body_r + 14), int(cy - 5))
            self._draw_stop_palm(painter, cx + body_r + 14, cy - 9)

        else:
            self._draw_glove(painter, cx - body_r - 9, cy + 16, 6, glove_color, glove_border)
            self._draw_glove(painter, cx + body_r + 5, cy + 16, 6, glove_color, glove_border)

    def _draw_glove(
        self,
        painter: QPainter,
        x: float,
        y: float,
        size: float,
        color: QColor,
        border: QColor,
    ) -> None:
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(border, 1.2))
        painter.drawEllipse(QRectF(x, y, size * 1.8, size * 1.8))

    def _draw_thumbs_up_glove(self, painter: QPainter, x: float, y: float, is_left: bool) -> None:
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.setPen(QPen(QColor("#059669"), 1.3))
        painter.drawRoundedRect(QRectF(x, y + 4, 12, 10), 3, 3)
        thumb_x = x + (1 if is_left else 7)
        painter.drawRoundedRect(QRectF(thumb_x, y - 5, 5, 10), 2, 2)

    def _draw_stop_palm(self, painter: QPainter, x: float, y: float) -> None:
        # Bold prominent white glove in STOP palm gesture
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.setPen(QPen(QColor("#b91c1c"), 1.5))
        painter.drawRoundedRect(QRectF(x, y, 12, 15), 3, 3)
        painter.drawLine(int(x + 2), int(y), int(x + 2), int(y - 5))
        painter.drawLine(int(x + 5), int(y), int(x + 5), int(y - 6))
        painter.drawLine(int(x + 8), int(y), int(x + 8), int(y - 5))

    # --- Clock Hands ---

    def _draw_clock_hands(
        self,
        painter: QPainter,
        cx: float,
        cy: float,
        cfg: StateVisualConfig,
        pulse: float,
    ) -> None:
        painter.save()
        painter.translate(cx, cy)
        hand_pen = QPen(
            QColor("#78350f" if cfg.state != AssistantState.OFFLINE else "#78716c"),
            2.0,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
        )
        painter.setPen(hand_pen)

        if cfg.state == AssistantState.OFFLINE:
            # Sleeping drooped hands (6:30)
            painter.drawLine(0, 0, 0, 12)
            painter.drawLine(0, 0, 5, 7)
        elif cfg.state == AssistantState.WORKING:
            # Fast spinning clock hands in fast-forward!
            spin = (self._anim_phase * 6.0) if not self._reduced_motion else 1.0
            painter.save()
            painter.rotate(math.degrees(spin))
            painter.drawLine(0, 0, 0, -14)
            painter.restore()
            painter.save()
            painter.rotate(math.degrees(spin * 0.25))
            painter.drawLine(0, 0, 0, -10)
            painter.restore()
        elif cfg.state == AssistantState.SUCCESS:
            # Celebratory V victory hands
            painter.drawLine(0, 0, -11, -13)
            painter.drawLine(0, 0, 11, -13)
        else:
            # Classic friendly 10:10 hands
            painter.drawLine(0, 0, -10, -12)
            painter.drawLine(0, 0, 12, -10)

        # Center brass pin
        painter.setBrush(QBrush(cfg.bezel_color))
        painter.setPen(QPen(QColor("#78350f"), 1.0))
        painter.drawEllipse(QRectF(-2.2, -2.2, 4.4, 4.4))
        painter.restore()

    # --- Cartoon Eyes, Eyelashes, and Eyebrows ---

    def _draw_eyes_and_brows(
        self,
        painter: QPainter,
        cx: float,
        cy: float,
        cfg: StateVisualConfig,
    ) -> None:
        eye_y = cy - 6
        eye_spacing = 11.5
        left_eye_x = cx - eye_spacing
        right_eye_x = cx + eye_spacing

        painter.setBrush(QBrush(cfg.eye_color))
        painter.setPen(QPen(cfg.eye_color, 1.7))

        # Check for natural blink
        if self._is_blinking and cfg.state in (AssistantState.IDLE, AssistantState.WORKING):
            p_l = QPainterPath()
            p_l.moveTo(left_eye_x - 5, eye_y)
            p_l.quadTo(left_eye_x, eye_y - 3, left_eye_x + 5, eye_y)
            painter.drawPath(p_l)

            p_r = QPainterPath()
            p_r.moveTo(right_eye_x - 5, eye_y)
            p_r.quadTo(right_eye_x, eye_y - 3, right_eye_x + 5, eye_y)
            painter.drawPath(p_r)
            return

        # Signature 1950s Cartoon Eyelashes (3 per eye)
        if cfg.state != AssistantState.OFFLINE:
            lash_pen = QPen(cfg.eye_color, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(lash_pen)
            painter.drawLine(int(left_eye_x - 3), int(eye_y - 5), int(left_eye_x - 7), int(eye_y - 8))
            painter.drawLine(int(left_eye_x - 1), int(eye_y - 6), int(left_eye_x - 4), int(eye_y - 10))
            painter.drawLine(int(left_eye_x + 1), int(eye_y - 6), int(left_eye_x), int(eye_y - 11))

            painter.drawLine(int(right_eye_x - 1), int(eye_y - 6), int(right_eye_x), int(eye_y - 11))
            painter.drawLine(int(right_eye_x + 1), int(eye_y - 6), int(right_eye_x + 4), int(eye_y - 10))
            painter.drawLine(int(right_eye_x + 3), int(eye_y - 5), int(right_eye_x + 7), int(eye_y - 8))
            painter.setPen(QPen(cfg.eye_color, 1.7))

        if cfg.eye_shape in (EyeShape.SLEEPING, EyeShape.LISTENING_CLOSED):
            # Curved peaceful listening/sleeping eyes (⌒ ⌒)
            p_l = QPainterPath()
            p_l.moveTo(left_eye_x - 5, eye_y)
            p_l.quadTo(left_eye_x, eye_y - 5, left_eye_x + 5, eye_y)
            painter.drawPath(p_l)

            p_r = QPainterPath()
            p_r.moveTo(right_eye_x - 5, eye_y)
            p_r.quadTo(right_eye_x, eye_y - 5, right_eye_x + 5, eye_y)
            painter.drawPath(p_r)

        elif cfg.eye_shape == EyeShape.WINKING:
            p_l = QPainterPath()
            p_l.moveTo(left_eye_x - 5, eye_y)
            p_l.quadTo(left_eye_x, eye_y - 5, left_eye_x + 5, eye_y)
            painter.drawPath(p_l)

            painter.drawEllipse(QRectF(right_eye_x - 4, eye_y - 5, 8.5, 10.5))
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(right_eye_x - 2, eye_y - 3.5, 3, 3))

        elif cfg.eye_shape == EyeShape.THINKING_UP:
            # Eyes looking way up and right toward thought cloud (THINKING)
            painter.drawEllipse(QRectF(left_eye_x - 4, eye_y - 5, 8, 10))
            painter.drawEllipse(QRectF(right_eye_x - 4, eye_y - 5, 8, 10))
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(left_eye_x + 0.5, eye_y - 4.5, 3.0, 3.0))
            painter.drawEllipse(QRectF(right_eye_x + 0.5, eye_y - 4.5, 3.0, 3.0))

        elif cfg.eye_shape == EyeShape.FOCUSED_DOWN:
            painter.drawEllipse(QRectF(left_eye_x - 4, eye_y - 4, 8, 9))
            painter.drawEllipse(QRectF(right_eye_x - 4, eye_y - 4, 8, 9))
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(left_eye_x - 1.5, eye_y + 1, 2.6, 2.6))
            painter.drawEllipse(QRectF(right_eye_x - 1.5, eye_y + 1, 2.6, 2.6))

        elif cfg.eye_shape == EyeShape.SAD_DROOPY:
            # Drooping sad eyes (ERROR)
            painter.drawEllipse(QRectF(left_eye_x - 4, eye_y - 3.5, 8, 9))
            painter.drawEllipse(QRectF(right_eye_x - 4, eye_y - 3.5, 8, 9))
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(left_eye_x - 1.5, eye_y - 1.5, 2.3, 2.3))
            painter.drawEllipse(QRectF(right_eye_x - 1.5, eye_y - 1.5, 2.3, 2.3))

        elif cfg.eye_shape == EyeShape.STERN:
            # Stern determined sharp eyes (BLOCKED)
            painter.drawEllipse(QRectF(left_eye_x - 4, eye_y - 4.5, 8, 9))
            painter.drawEllipse(QRectF(right_eye_x - 4, eye_y - 4.5, 8, 9))
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(left_eye_x - 1, eye_y - 3, 2.5, 2.5))
            painter.drawEllipse(QRectF(right_eye_x - 2.5, eye_y - 3, 2.5, 2.5))

        else:
            painter.drawEllipse(QRectF(left_eye_x - 4, eye_y - 5, 8.5, 10.5))
            painter.drawEllipse(QRectF(right_eye_x - 4, eye_y - 5, 8.5, 10.5))
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(left_eye_x - 2, eye_y - 3.5, 3, 3))
            painter.drawEllipse(QRectF(right_eye_x - 2, eye_y - 3.5, 3, 3))
            painter.drawEllipse(QRectF(left_eye_x + 0.5, eye_y + 0.5, 1.4, 1.4))
            painter.drawEllipse(QRectF(right_eye_x + 0.5, eye_y + 0.5, 1.4, 1.4))

        self._draw_eyebrows(painter, left_eye_x, right_eye_x, eye_y, cfg)

    def _draw_eyebrows(
        self,
        painter: QPainter,
        lx: float,
        rx: float,
        ey: float,
        cfg: StateVisualConfig,
    ) -> None:
        brow_pen = QPen(cfg.eye_color, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(brow_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        by = ey - 9.0

        if cfg.eyebrow_type == EyebrowType.STERN_ANGLED:
            # Sharp V-angled stern eyebrows (BLOCKED)
            painter.drawLine(int(lx - 4), int(by - 3), int(lx + 4), int(by + 2))
            painter.drawLine(int(rx - 4), int(by + 2), int(rx + 4), int(by - 3))
        elif cfg.eyebrow_type == EyebrowType.SAD_SLANTED:
            # Slanted sad eyebrows (ERROR)
            painter.drawLine(int(lx - 4), int(by + 2), int(lx + 4), int(by - 2))
            painter.drawLine(int(rx - 4), int(by - 2), int(rx + 4), int(by + 2))
        elif cfg.eyebrow_type == EyebrowType.ONE_RAISED:
            # Left raised high, right arched (THINKING)
            painter.drawLine(int(lx - 4), int(by - 4), int(lx + 4), int(by - 4))
            painter.drawLine(int(rx - 4), int(by + 1), int(rx + 4), int(by))
        elif cfg.eyebrow_type == EyebrowType.RAISED:
            painter.drawLine(int(lx - 4), int(by - 3), int(lx + 4), int(by - 4))
            painter.drawLine(int(rx - 4), int(by - 4), int(rx + 4), int(by - 3))
        elif cfg.eyebrow_type != EyebrowType.RELAXED:
            painter.drawLine(int(lx - 3), int(by - 1), int(lx + 3), int(by - 1))
            painter.drawLine(int(rx - 3), int(by - 1), int(rx + 3), int(by - 1))

    # --- Expressive Mouth with Live Articulation ---

    def _draw_mouth(
        self,
        painter: QPainter,
        cx: float,
        cy: float,
        cfg: StateVisualConfig,
        pulse: float,
    ) -> None:
        mouth_y = cy + 12.0
        mouth_pen = QPen(cfg.eye_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(mouth_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        m_path = QPainterPath()

        if cfg.mouth_shape == MouthShape.RESTING:
            m_path.moveTo(cx - 4, mouth_y)
            m_path.lineTo(cx + 4, mouth_y)
        elif cfg.mouth_shape == MouthShape.ALERT_O:
            painter.setBrush(QBrush(cfg.eye_color))
            painter.drawEllipse(QRectF(cx - 3, mouth_y - 2, 6, 6))
            return
        elif cfg.mouth_shape == MouthShape.PUCKER:
            # Thoughtful pursed lips (THINKING)
            painter.setBrush(QBrush(cfg.eye_color))
            painter.drawEllipse(QRectF(cx - 2, mouth_y - 1, 4.5, 4.5))
            return
        elif cfg.mouth_shape == MouthShape.TALKING:
            # Live speech articulation: alternates phonemes at speech rhythm!
            talk_mod = math.sin(self._anim_phase * 4.5) if not self._reduced_motion else 0.5
            painter.setBrush(QBrush(QColor("#7f1d1d")))
            if talk_mod > 0.25:
                # Wide open speech mouth
                m_path.moveTo(cx - 6, mouth_y - 1)
                m_path.quadTo(cx, mouth_y + 8, cx + 6, mouth_y - 1)
                m_path.closeSubpath()
                painter.drawPath(m_path)
                painter.setBrush(QBrush(QColor("#ffffff")))
                painter.drawRect(QRectF(cx - 4, mouth_y, 8, 2))
                return
            elif talk_mod < -0.25:
                # Small 'O' phoneme
                painter.drawEllipse(QRectF(cx - 3, mouth_y - 1, 6, 5))
                return
            else:
                # Talking smile
                painter.drawEllipse(QRectF(cx - 4.5, mouth_y - 1, 9, 4))
                return
        elif cfg.mouth_shape == MouthShape.FROWN:
            # Wobbly sad downward frown (ERROR)
            m_path.moveTo(cx - 6, mouth_y + 3)
            m_path.quadTo(cx, mouth_y - 4, cx + 6, mouth_y + 3)
        elif cfg.mouth_shape == MouthShape.FIRM_LINE:
            # Resolute protective flat line (BLOCKED)
            m_path.moveTo(cx - 6, mouth_y)
            m_path.lineTo(cx + 6, mouth_y)
        elif cfg.mouth_shape == MouthShape.BEAMING:
            # Wide beaming celebratory smile with teeth (SUCCESS)
            painter.setBrush(QBrush(QColor("#7f1d1d")))
            m_path.moveTo(cx - 8, mouth_y - 2)
            m_path.quadTo(cx, mouth_y + 8, cx + 8, mouth_y - 2)
            m_path.closeSubpath()
            painter.drawPath(m_path)
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(cx - 5, mouth_y - 1.5, 10, 2.5), 1, 1)
            return
        else:
            m_path.moveTo(cx - 7, mouth_y)
            m_path.quadTo(cx, mouth_y + 5.5, cx + 7, mouth_y)

        painter.drawPath(m_path)

    # --- Props & Special Animated Effects ---

    def _draw_prop(
        self,
        painter: QPainter,
        cx: float,
        cy: float,
        cfg: StateVisualConfig,
        pulse: float,
    ) -> None:
        prop = cfg.prop

        if prop == StateProp.ZZZ_BUBBLES:
            bob = 1.8 * math.sin(self._anim_phase) if not self._reduced_motion else 0.0
            font = painter.font()
            font.setFamily("Consolas")
            font.setBold(True)

            painter.setPen(QPen(QColor("#a8a29e")))
            font.setPointSize(6)
            painter.setFont(font)
            painter.drawText(int(cx + 24), int(cy - 24 + bob), "z")

            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(int(cx + 30), int(cy - 31 + bob), "z")

            font.setPointSize(10)
            painter.setFont(font)
            painter.setPen(QPen(QColor("#e7e5e4")))
            painter.drawText(int(cx + 38), int(cy - 40 + bob), "Z")

        elif prop == StateProp.ALERT_BURST:
            painter.setPen(QPen(QColor("#fbbf24"), 2.0))
            painter.drawLine(int(cx + 32), int(cy - 30), int(cx + 42), int(cy - 40))
            painter.drawLine(int(cx + 39), int(cy - 23), int(cx + 51), int(cy - 27))
            painter.drawLine(int(cx + 27), int(cy - 39), int(cx + 32), int(cy - 50))

        elif prop == StateProp.SOUNDWAVES_BLUE:
            # Prominent expanding cyan listening soundwaves (LISTENING)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            wave_expand = (3.0 * math.sin(self._anim_phase * 2.5)) if not self._reduced_motion else 1.0
            for i in range(3):
                arc_r = 11.0 + (i * 7.0) + wave_expand
                wave_alpha = max(0.25, 0.95 - (i * 0.22))
                painter.setPen(QPen(QColor(56, 189, 248, int(wave_alpha * 255)), 2.2))
                painter.drawArc(QRectF(cx + 34 - arc_r, cy - 10 - arc_r, arc_r * 2, arc_r * 2), -40 * 16, 80 * 16)

        elif prop == StateProp.HOLOGRAM_TABLET:
            tab_rect = QRectF(cx - 20, cy + 10, 40, 24)
            painter.setBrush(QBrush(QColor(124, 58, 237, 170)))
            painter.setPen(QPen(QColor("#c084fc"), 1.4))
            painter.drawRoundedRect(tab_rect, 3, 3)

            painter.setPen(QPen(QColor("#e9d5ff"), 1.2))
            painter.drawLine(int(cx - 15), int(cy + 15), int(cx + 15), int(cy + 15))
            painter.drawLine(int(cx - 15), int(cy + 20), int(cx + 8), int(cy + 20))
            painter.drawLine(int(cx - 15), int(cy + 25), int(cx + 12), int(cy + 25))

        elif prop == StateProp.THOUGHT_CLOUD:
            # Prominent puffy thought cloud with drifting animation (THINKING)
            cloud_drift = 2.5 * math.sin(self._anim_phase * 1.5) if not self._reduced_motion else 0.0
            painter.setBrush(QBrush(QColor(254, 243, 199, 240)))
            painter.setPen(QPen(QColor("#d97706"), 1.4))

            # Connecting bubbles
            painter.drawEllipse(QRectF(cx + 18, cy - 18 + cloud_drift * 0.3, 4.5, 4.5))
            painter.drawEllipse(QRectF(cx + 24, cy - 26 + cloud_drift * 0.6, 6.5, 6.5))

            # Cloud body
            cloud_path = QPainterPath()
            cloud_path.addEllipse(QRectF(cx + 24, cy - 46 + cloud_drift, 24, 16))
            cloud_path.addEllipse(QRectF(cx + 17, cy - 42 + cloud_drift, 16, 13))
            cloud_path.addEllipse(QRectF(cx + 36, cy - 42 + cloud_drift, 16, 13))
            painter.drawPath(cloud_path)

        elif prop == StateProp.MAGNIFYING_GLASS:
            mg_x = cx + 18
            mg_y = cy - 7
            painter.setBrush(QBrush(QColor(2, 132, 199, 70)))
            painter.setPen(QPen(QColor("#38bdf8"), 2.2))
            painter.drawEllipse(QRectF(mg_x - 11, mg_y - 11, 22, 22))

            painter.setPen(QPen(QColor("#78350f"), 3.0))
            painter.drawLine(int(mg_x + 8), int(mg_y + 8), int(mg_x + 16), int(mg_y + 16))

        elif prop == StateProp.SPINNING_GEARS:
            # TWO prominent rotating golden mechanical gears (WORKING)
            spin = (self._anim_phase * 3.5) if not self._reduced_motion else 0.5
            # Master Gear 1
            self._draw_gear(painter, cx + 38, cy - 14, 13.0, spin)
            # Meshed Gear 2
            self._draw_gear(painter, cx + 40, cy + 10, 9.0, -spin * 1.4)

        elif prop == StateProp.SPEECH_WAVES:
            # Pulsing speech wave ripples radiating outward from mouth (SPEAKING)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for i in range(3):
                rip = ((self._anim_phase * 8.0 + i * 6.0) % 18.0) if not self._reduced_motion else (i * 6.0)
                wave_col = QColor(244, 114, 182, max(30, int(220 - rip * 9)))
                painter.setPen(QPen(wave_col, 2.0))
                arc_r = 10.0 + rip
                painter.drawArc(QRectF(cx + 20 - arc_r, cy + 12 - arc_r, arc_r * 2, arc_r * 2), -30 * 16, 60 * 16)

        elif prop == StateProp.SUCCESS_SPARKLES:
            # Sparkling golden stars scaling and twinkling (SUCCESS)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#fbbf24")))
            star_pulse = 2.5 * math.sin(self._anim_phase * 3) if not self._reduced_motion else 0.0
            self._draw_sparkle_star(painter, cx - 38, cy - 22, 7.0 + star_pulse)
            self._draw_sparkle_star(painter, cx + 38, cy - 22, 7.0 - star_pulse)
            self._draw_sparkle_star(painter, cx + 34, cy + 8, 5.0 + star_pulse)

            # Emerald checkmark badge
            painter.setBrush(QBrush(QColor("#059669")))
            painter.drawEllipse(QRectF(cx + 26, cy - 36, 16, 16))
            painter.setPen(QPen(QColor("#ffffff"), 2.0))
            painter.drawLine(int(cx + 29), int(cy - 28), int(cx + 33), int(cy - 24))
            painter.drawLine(int(cx + 33), int(cy - 24), int(cx + 39), int(cy - 31))

        elif prop == StateProp.ERROR_SCRIBBLE:
            # Red/purple dizzy confusion spiral scribble (ERROR)
            jitter = 2.0 * math.sin(self._anim_phase * 4) if not self._reduced_motion else 0.0
            painter.setPen(QPen(QColor("#ef4444"), 2.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            s_path = QPainterPath()
            s_path.moveTo(cx - 14 + jitter, cy - 38)
            s_path.quadTo(cx - 3 + jitter, cy - 48, cx + 6 + jitter, cy - 40)
            s_path.quadTo(cx + 16 + jitter, cy - 32, cx + 4 + jitter, cy - 43)
            s_path.quadTo(cx - 8 + jitter, cy - 50, cx + 12 + jitter, cy - 36)
            painter.drawPath(s_path)

        elif prop == StateProp.BLOCKED_SHIELD:
            # Red & white prohibition security shield icon (BLOCKED)
            sh_x = cx + 40
            sh_y = cy - 20
            sh_r = 11.5
            painter.setBrush(QBrush(QColor(185, 28, 28, 235)))
            painter.setPen(QPen(QColor("#ffffff"), 2.0))
            painter.drawEllipse(QRectF(sh_x - sh_r, sh_y - sh_r, sh_r * 2, sh_r * 2))
            painter.drawLine(int(sh_x - 7), int(sh_y + 7), int(sh_x + 7), int(sh_y - 7))

    def _draw_gear(self, painter: QPainter, x: float, y: float, radius: float, angle_rad: float) -> None:
        """Draws a bold, clearly defined mechanical cog with 6 teeth."""
        painter.save()
        painter.translate(x, y)
        painter.rotate(math.degrees(angle_rad))
        painter.setBrush(QBrush(QColor("#f59e0b")))
        painter.setPen(QPen(QColor("#b45309"), 1.3))
        painter.drawEllipse(QRectF(-radius, -radius, radius * 2, radius * 2))
        tooth_w = max(2.5, radius * 0.32)
        tooth_h = max(2.5, radius * 0.35)
        for _ in range(6):
            painter.drawRect(QRectF(-tooth_w / 2.0, -radius - tooth_h * 0.8, tooth_w, tooth_h))
            painter.rotate(60)
        # Center hole
        painter.setBrush(QBrush(QColor("#141210")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(-radius * 0.35, -radius * 0.35, radius * 0.7, radius * 0.7))
        painter.restore()

    def _draw_sparkle_star(self, painter: QPainter, x: float, y: float, size: float) -> None:
        path = QPainterPath()
        path.moveTo(x, y - size)
        path.quadTo(x, y, x + size, y)
        path.quadTo(x, y, x, y + size)
        path.quadTo(x, y, x - size, y)
        path.quadTo(x, y, x, y - size)
        painter.drawPath(path)

    # --- Floating Status Pill (Reference Image 1) ---

    def _draw_status_pill(self, painter: QPainter, cfg: StateVisualConfig, state: AssistantState) -> None:
        """
        Draws the sleek floating capsule pill directly underneath Miss Minutes:
        '● Miss Minutes • Idle   (🎤)'
        """
        pill_rect = self._get_status_pill_rect()
        px = float(pill_rect.x())
        py = float(pill_rect.y())
        pw = float(pill_rect.width())
        ph = float(pill_rect.height())

        pill_bg = QColor(22, 17, 13, 235)
        pill_border = QColor(245, 158, 11, 120) if state != AssistantState.OFFLINE else QColor(84, 71, 59, 120)

        painter.setBrush(QBrush(pill_bg))
        painter.setPen(QPen(pill_border, 1.2))
        painter.drawRoundedRect(QRectF(px, py, pw, ph), 14.0, 14.0)

        # Status Dot (left side)
        dot_col = cfg.badge_bg
        painter.setBrush(QBrush(dot_col))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(px + 10, py + 10, 7, 7))

        # Status Text: 'Miss Minutes • <Title>'
        state_title = cfg.title.capitalize() if cfg.title.isupper() else cfg.title
        status_text = f"Miss Minutes • {state_title}"

        font = painter.font()
        font.setFamily("Segoe UI")
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#fdf8f0")))
        text_rect = QRectF(px + 22, py, pw - 48, ph)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, status_text)

        # Interactive Microphone Button (right side)
        mx = px + pw - 24.0
        my = py + 3.0
        mw = 22.0
        mh = 22.0

        mic_bg = QColor(245, 158, 11, 80) if self._mic_hovered else QColor(36, 27, 20, 210)
        mic_border = QColor("#fbbf24") if (self._mic_hovered or state == AssistantState.LISTENING) else QColor("#b45309")

        painter.setBrush(QBrush(mic_bg))
        painter.setPen(QPen(mic_border, 1.4))
        painter.drawEllipse(QRectF(mx, my, mw, mh))

        # Microphone Icon glyph
        painter.setPen(QPen(QColor("#fdf8f0"), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(QBrush(QColor("#fdf8f0")))
        # Mic capsule body
        painter.drawRoundedRect(QRectF(mx + 8, my + 4, 6, 8), 3, 3)
        # Mic cradle arc
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(mx + 6, my + 7, 10, 7), 0, -180 * 16)
        # Mic stand line & base
        painter.drawLine(int(mx + 11), int(my + 14), int(mx + 11), int(my + 17))
        painter.drawLine(int(mx + 8), int(my + 17), int(mx + 14), int(my + 17))
