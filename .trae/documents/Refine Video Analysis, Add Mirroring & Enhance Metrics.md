# Video Analysis & UI Enhancement Plan

## 1. Backend: Refine Video Analysis Logic (`interview.py`)
- **Objective**: Reduce false positive cheat alerts, implement tiered warnings, and add useful interview metrics.
- **Action**: Update the system prompt in `analyze_video` API:
    - **Cheat Detection**: Instruct model to be lenient on gaze (allow screen reading) and only flag *obvious* anomalies (phones, other people, total darkness) as 'critical'. Define 'warning' for minor issues (lighting, partial face).
    - **New Metrics**: Request specific scores (0-100) for:
        - `confidence_score` (自信程度)
        - `attire_score` (衣着得体度)
        - `clarity_score` (画面清晰度)
        - `eye_contact_score` (眼神交流 - lenient)
    - **Response Structure**: Return `alert_level` ('none', 'warning', 'critical') and `alert_reason_cn` (Chinese explanation).

## 2. Frontend: Biometrics & Mirroring (`index.html`)
- **Biometrics Panel**: Replace the simple Emotion/Gaze bars with the new detailed metrics (Confidence, Attire, Clarity, Eye Contact).
- **Mirror Button**: Add a toggle button (`[↔]`) in the video overlay area to flip the video feed horizontally.
- **Alert Toast**: Update the alert toast structure to support two visual styles:
    - **Yellow (Warning)**: For lighting issues or minor suspicions.
    - **Red (Critical)**: For high-probability cheating.

## 3. Logic: Update UI Handlers (`app.js`)
- **Analysis Loop**: Parse the new JSON fields from the backend.
- **Visual Feedback**:
    - Update the new metric bars dynamically.
    - Show the appropriate Yellow or Red toast based on `alert_level`.
- **Mirror Logic**: Implement `toggleMirror()` to apply `transform: scaleX(-1)` to the video element.

## 4. Verification
- **Test**: Simulate video analysis response with different alert levels to ensure toasts appear correctly. Check if the mirror button flips the video feed. Verify new metrics are updating.