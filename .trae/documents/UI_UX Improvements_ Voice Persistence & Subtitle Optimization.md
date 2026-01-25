# UI/UX Optimization Plan

## 1. Remove Redundant Alert Box
- **Target**: `index.html` (Biometrics Panel)
- **Action**: Delete the `div` block containing `#stat-cheat-count` and `#cheat-alert-msg`. This removes the duplicate "Cheat Alert" from the right sidebar, as requested.

## 2. Fix Voice Persistence Logic
- **Target**: `app.js`
- **Issue**: `enterRoom` function was re-randomizing the voice, overwriting the user's selection or the initial default shown in the dropdown.
- **Action**: Remove the random voice assignment in `enterRoom`. The voice will now strictly follow the state set by the initialization (random default) or the user's dropdown selection.

## 3. Optimize Subtitle Style
- **Target**: `index.html` (`#current-question-box`)
- **Action**:
    - Change layout from a floating "bubble" to a **full-width bottom bar** (`w-full`, `bottom-0`).
    - Reduce text size to `text-sm` or `text-base` (from `text-2xl`).
    - Use a semi-transparent dark background (`bg-black/80`) with a top border to fit the "terminal" theme.
    - Ensure it sits neatly above the control bar or at the bottom of the video feed.

## 4. Verification
- **Visual**: Confirm subtitles are low-profile and full-width.
- **Functional**: Confirm changing the voice dropdown persists across turns and matches the audio heard.
- **Cleanup**: Confirm the right sidebar no longer shows the red alert box.