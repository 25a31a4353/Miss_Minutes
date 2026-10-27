"""
ui/expressions.py - Visual State & Expression Definitions for Miss Minutes.

Maps each of the 12 FSM states defined in Miss_Minutes_PRD.md and illustrated
in the 'Miss Minutes - Expressions & States' design reference to concrete
procedural drawing tokens (eyes, eyebrows, mouth, arms, legs, and props).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict

from PySide6.QtGui import QColor

from ui.state_machine import AssistantState


class EyeShape(str, Enum):
    SLEEPING = "SLEEPING"              # Curved closed eyes (OFLLINE)
    HAPPY_OPEN = "HAPPY_OPEN"          # Big friendly cartoon pupils (IDLE)
    ALERT_WIDE = "ALERT_WIDE"          # Surprised wide eyes (WAKE_DETECTED)
    LISTENING_CLOSED = "LISTENING_CLOSED"  # Attentive peaceful closed curves (LISTENING)
    FOCUSED_DOWN = "FOCUSED_DOWN"      # Pupils directed down toward tablet (TRANSCRIBING)
    THINKING_UP = "THINKING_UP"        # Pupils looking up-right thoughtfully (THINKING)
    VALIDATING = "VALIDATING"          # One eye magnified, one winking/squinting (VALIDATING)
    ENERGETIC = "ENERGETIC"            # Wide bright pupils (WORKING)
    SPEAKING = "SPEAKING"              # Lively open eyes (SPEAKING)
    WINKING = "WINKING"                # Winking left, sparkling right (SUCCESS)
    SAD_DROOPY = "SAD_DROOPY"          # Drooping sad pupils (ERROR)
    STERN = "STERN"                    # Determined firm gaze (BLOCKED)


class MouthShape(str, Enum):
    RESTING = "RESTING"                # Gentle straight/curved slit (OFFLINE)
    WARM_SMILE = "WARM_SMILE"          # Cheerful open smile (IDLE)
    ALERT_O = "ALERT_O"                # Small round 'O' mouth (WAKE_DETECTED)
    LISTENING_SMILE = "LISTENING_SMILE"  # Peaceful gentle smile (LISTENING)
    FOCUSED_LINE = "FOCUSED_LINE"      # Small focused smirk (TRANSCRIBING)
    PUCKER = "PUCKER"                  # Thoughtful pursed lips (THINKING)
    VALIDATING_SMIRK = "VALIDATING_SMIRK"  # Reassuring confident smile (VALIDATING)
    WIDE_OPEN = "WIDE_OPEN"            # Enthusiastic open smile (WORKING)
    TALKING = "TALKING"                # Open phoneme mouth for speech (SPEAKING)
    BEAMING = "BEAMING"                # Huge celebratory grin (SUCCESS)
    FROWN = "FROWN"                    # Sad downward curve (ERROR)
    FIRM_LINE = "FIRM_LINE"            # Resolute protective line (BLOCKED)


class EyebrowType(str, Enum):
    RELAXED = "RELAXED"
    GENTLE = "GENTLE"
    RAISED = "RAISED"
    FOCUS = "FOCUS"
    ONE_RAISED = "ONE_RAISED"
    SAD_SLANTED = "SAD_SLANTED"
    STERN_ANGLED = "STERN_ANGLED"


class ArmPose(str, Enum):
    RESTING = "RESTING"
    HIP_LEFT = "HIP_LEFT"
    WAVING_RIGHT = "WAVING_RIGHT"
    ALERT_EAR = "ALERT_EAR"
    CUPPED_EAR = "CUPPED_EAR"
    HOLDING_TABLET = "HOLDING_TABLET"
    CHIN_THINKER = "CHIN_THINKER"
    HOLDING_MAGNIFIER = "HOLDING_MAGNIFIER"
    STRIDE_RUN = "STRIDE_RUN"
    GESTURE_OUT = "GESTURE_OUT"
    DOUBLE_THUMBS_UP = "DOUBLE_THUMBS_UP"
    DROOPING = "DROOPING"
    STOP_PALM = "STOP_PALM"


class LegPose(str, Enum):
    SITTING = "SITTING"
    STANDING = "STANDING"
    STRIDE = "STRIDE"
    CELEBRATING = "CELEBRATING"


class StateProp(str, Enum):
    NONE = "NONE"
    ZZZ_BUBBLES = "ZZZ_BUBBLES"
    ALERT_BURST = "ALERT_BURST"
    SOUNDWAVES_BLUE = "SOUNDWAVES_BLUE"
    HOLOGRAM_TABLET = "HOLOGRAM_TABLET"
    THOUGHT_CLOUD = "THOUGHT_CLOUD"
    MAGNIFYING_GLASS = "MAGNIFYING_GLASS"
    SPINNING_GEARS = "SPINNING_GEARS"
    SPEECH_WAVES = "SPEECH_WAVES"
    SUCCESS_SPARKLES = "SUCCESS_SPARKLES"
    ERROR_SCRIBBLE = "ERROR_SCRIBBLE"
    BLOCKED_SHIELD = "BLOCKED_SHIELD"


@dataclass(frozen=True)
class StateVisualConfig:
    """Configuration bundle defining the complete visual appearance for a state."""

    state: AssistantState
    title: str
    description: str
    eye_shape: EyeShape
    mouth_shape: MouthShape
    eyebrow_type: EyebrowType
    arm_pose: ArmPose
    leg_pose: LegPose
    prop: StateProp
    bezel_color: QColor
    face_color: QColor
    eye_color: QColor
    accent_color: QColor
    glow_intensity: float
    badge_text: str
    badge_bg: QColor
    dialogue: str = ""


STATE_VISUALS: Dict[AssistantState, StateVisualConfig] = {
    AssistantState.OFFLINE: StateVisualConfig(
        state=AssistantState.OFFLINE,
        title="OFFLINE",
        description="Assistant is OFF. Not listening, not working.",
        eye_shape=EyeShape.SLEEPING,
        mouth_shape=MouthShape.RESTING,
        eyebrow_type=EyebrowType.RELAXED,
        arm_pose=ArmPose.RESTING,
        leg_pose=LegPose.SITTING,
        prop=StateProp.ZZZ_BUBBLES,
        bezel_color=QColor("#54473b"),
        face_color=QColor("#d4cbba"),
        eye_color=QColor("#4a3f35"),
        accent_color=QColor("#78716c"),
        glow_intensity=0.0,
        badge_text="OFF",
        badge_bg=QColor("#991b1b"),
        dialogue="Assistant is OFF. Not listening, not working.",
    ),
    AssistantState.IDLE: StateVisualConfig(
        state=AssistantState.IDLE,
        title="IDLE",
        description="Ready and waiting for your command!",
        eye_shape=EyeShape.HAPPY_OPEN,
        mouth_shape=MouthShape.WARM_SMILE,
        eyebrow_type=EyebrowType.GENTLE,
        arm_pose=ArmPose.WAVING_RIGHT,
        leg_pose=LegPose.STANDING,
        prop=StateProp.NONE,
        bezel_color=QColor("#d97706"),
        face_color=QColor("#fefbf3"),
        eye_color=QColor("#451a03"),
        accent_color=QColor("#f59e0b"),
        glow_intensity=0.45,
        badge_text="ON",
        badge_bg=QColor("#059669"),
        dialogue="Ready and waiting for your command!",
    ),
    AssistantState.WAKE_DETECTED: StateVisualConfig(
        state=AssistantState.WAKE_DETECTED,
        title="WAKE DETECTED",
        description="Hey Minutes? Yes? I'm listening...",
        eye_shape=EyeShape.ALERT_WIDE,
        mouth_shape=MouthShape.ALERT_O,
        eyebrow_type=EyebrowType.RAISED,
        arm_pose=ArmPose.ALERT_EAR,
        leg_pose=LegPose.STANDING,
        prop=StateProp.ALERT_BURST,
        bezel_color=QColor("#eab308"),
        face_color=QColor("#fefce8"),
        eye_color=QColor("#451a03"),
        accent_color=QColor("#facc15"),
        glow_intensity=0.6,
        badge_text="WAKE",
        badge_bg=QColor("#d97706"),
        dialogue="Yes? I'm listening...",
    ),
    AssistantState.LISTENING: StateVisualConfig(
        state=AssistantState.LISTENING,
        title="LISTENING",
        description="Listening to your voice...",
        eye_shape=EyeShape.LISTENING_CLOSED,
        mouth_shape=MouthShape.LISTENING_SMILE,
        eyebrow_type=EyebrowType.GENTLE,
        arm_pose=ArmPose.CUPPED_EAR,
        leg_pose=LegPose.STANDING,
        prop=StateProp.SOUNDWAVES_BLUE,
        bezel_color=QColor("#0284c7"),
        face_color=QColor("#f0f9ff"),
        eye_color=QColor("#0369a1"),
        accent_color=QColor("#38bdf8"),
        glow_intensity=0.55,
        badge_text="MIC",
        badge_bg=QColor("#0284c7"),
        dialogue="Listening to your voice...",
    ),
    AssistantState.TRANSCRIBING: StateVisualConfig(
        state=AssistantState.TRANSCRIBING,
        title="TRANSCRIBING",
        description="Converting your speech to text...",
        eye_shape=EyeShape.FOCUSED_DOWN,
        mouth_shape=MouthShape.FOCUSED_LINE,
        eyebrow_type=EyebrowType.FOCUS,
        arm_pose=ArmPose.HOLDING_TABLET,
        leg_pose=LegPose.STANDING,
        prop=StateProp.HOLOGRAM_TABLET,
        bezel_color=QColor("#7c3aed"),
        face_color=QColor("#f5f3ff"),
        eye_color=QColor("#5b21b6"),
        accent_color=QColor("#a855f7"),
        glow_intensity=0.5,
        badge_text="TXT",
        badge_bg=QColor("#7c3aed"),
        dialogue="Converting your speech to text...",
    ),
    AssistantState.THINKING: StateVisualConfig(
        state=AssistantState.THINKING,
        title="THINKING",
        description="Let me think...",
        eye_shape=EyeShape.THINKING_UP,
        mouth_shape=MouthShape.PUCKER,
        eyebrow_type=EyebrowType.ONE_RAISED,
        arm_pose=ArmPose.CHIN_THINKER,
        leg_pose=LegPose.STANDING,
        prop=StateProp.THOUGHT_CLOUD,
        bezel_color=QColor("#ea580c"),
        face_color=QColor("#fff7ed"),
        eye_color=QColor("#7c2d12"),
        accent_color=QColor("#fb923c"),
        glow_intensity=0.5,
        badge_text="THK",
        badge_bg=QColor("#c2410c"),
        dialogue="Let me think...",
    ),
    AssistantState.VALIDATING: StateVisualConfig(
        state=AssistantState.VALIDATING,
        title="VALIDATING",
        description="Checking if this is safe...",
        eye_shape=EyeShape.VALIDATING,
        mouth_shape=MouthShape.VALIDATING_SMIRK,
        eyebrow_type=EyebrowType.FOCUS,
        arm_pose=ArmPose.HOLDING_MAGNIFIER,
        leg_pose=LegPose.STANDING,
        prop=StateProp.MAGNIFYING_GLASS,
        bezel_color=QColor("#0284c7"),
        face_color=QColor("#f0fdf4"),
        eye_color=QColor("#0369a1"),
        accent_color=QColor("#38bdf8"),
        glow_intensity=0.55,
        badge_text="SEC",
        badge_bg=QColor("#0369a1"),
        dialogue="Checking if this is safe...",
    ),
    AssistantState.WORKING: StateVisualConfig(
        state=AssistantState.WORKING,
        title="WORKING",
        description="Working on it...",
        eye_shape=EyeShape.ENERGETIC,
        mouth_shape=MouthShape.WIDE_OPEN,
        eyebrow_type=EyebrowType.GENTLE,
        arm_pose=ArmPose.STRIDE_RUN,
        leg_pose=LegPose.STRIDE,
        prop=StateProp.SPINNING_GEARS,
        bezel_color=QColor("#d97706"),
        face_color=QColor("#fefbf3"),
        eye_color=QColor("#451a03"),
        accent_color=QColor("#f59e0b"),
        glow_intensity=0.6,
        badge_text="RUN",
        badge_bg=QColor("#b45309"),
        dialogue="Working on it...",
    ),
    AssistantState.SPEAKING: StateVisualConfig(
        state=AssistantState.SPEAKING,
        title="SPEAKING",
        description="Here's your answer!",
        eye_shape=EyeShape.SPEAKING,
        mouth_shape=MouthShape.TALKING,
        eyebrow_type=EyebrowType.GENTLE,
        arm_pose=ArmPose.GESTURE_OUT,
        leg_pose=LegPose.STANDING,
        prop=StateProp.SPEECH_WAVES,
        bezel_color=QColor("#db2777"),
        face_color=QColor("#fdf2f8"),
        eye_color=QColor("#831843"),
        accent_color=QColor("#f472b6"),
        glow_intensity=0.55,
        badge_text="TTS",
        badge_bg=QColor("#be185d"),
        dialogue="Here's your answer!",
    ),
    AssistantState.SUCCESS: StateVisualConfig(
        state=AssistantState.SUCCESS,
        title="SUCCESS",
        description="Done! Operation succeeded.",
        eye_shape=EyeShape.WINKING,
        mouth_shape=MouthShape.BEAMING,
        eyebrow_type=EyebrowType.GENTLE,
        arm_pose=ArmPose.DOUBLE_THUMBS_UP,
        leg_pose=LegPose.CELEBRATING,
        prop=StateProp.SUCCESS_SPARKLES,
        bezel_color=QColor("#059669"),
        face_color=QColor("#f0fdf4"),
        eye_color=QColor("#064e3b"),
        accent_color=QColor("#34d399"),
        glow_intensity=0.65,
        badge_text="DONE",
        badge_bg=QColor("#059669"),
        dialogue="Done! ✅",
    ),
    AssistantState.ERROR: StateVisualConfig(
        state=AssistantState.ERROR,
        title="ERROR",
        description="Oops! Something went wrong.",
        eye_shape=EyeShape.SAD_DROOPY,
        mouth_shape=MouthShape.FROWN,
        eyebrow_type=EyebrowType.SAD_SLANTED,
        arm_pose=ArmPose.DROOPING,
        leg_pose=LegPose.STANDING,
        prop=StateProp.ERROR_SCRIBBLE,
        bezel_color=QColor("#dc2626"),
        face_color=QColor("#fef2f2"),
        eye_color=QColor("#7f1d1d"),
        accent_color=QColor("#f87171"),
        glow_intensity=0.5,
        badge_text="ERR",
        badge_bg=QColor("#b91c1c"),
        dialogue="Oops! Something went wrong.",
    ),
    AssistantState.BLOCKED: StateVisualConfig(
        state=AssistantState.BLOCKED,
        title="BLOCKED",
        description="This action is restricted for your safety.",
        eye_shape=EyeShape.STERN,
        mouth_shape=MouthShape.FIRM_LINE,
        eyebrow_type=EyebrowType.STERN_ANGLED,
        arm_pose=ArmPose.STOP_PALM,
        leg_pose=LegPose.STANDING,
        prop=StateProp.BLOCKED_SHIELD,
        bezel_color=QColor("#b91c1c"),
        face_color=QColor("#fff1f2"),
        eye_color=QColor("#881337"),
        accent_color=QColor("#f43f5e"),
        glow_intensity=0.6,
        badge_text="HALT",
        badge_bg=QColor("#991b1b"),
        dialogue="This action is restricted for your safety.",
    ),
}


def get_visual_config(state: AssistantState) -> StateVisualConfig:
    """Returns the visual configuration for a given assistant state."""
    return STATE_VISUALS.get(state, STATE_VISUALS[AssistantState.IDLE])
