# UI/UX & Logic Optimization Plan

## 1. Voice Persistence & Logic Fix (app.js)
- **Goal**: Ensure the selected voice persists across page reloads and never changes randomly during a session.
- **Action**:
    - Modify `init`: Check `localStorage.getItem('easyinterview_voice')` before falling back to random.
    - Modify `voiceSelect` event listener: Save selection to `localStorage`.
    - Modify `enterRoom`: Remove any remaining ambiguity about voice selection.

## 2. Dropdown UI Fix (index.html)
- **Goal**: Make the voice selection dropdown clearly clickable and functional.
- **Action**:
    - Remove `appearance-none` from `#voice-select` to restore the native dropdown arrow.
    - Ensure background and text colors are distinct for readability.
    - Verify `pointer-events` to ensure it's clickable.

## 3. Subtitle Style Optimization (index.html)
- **Goal**: Make subtitles "smaller" and "fully at the bottom" as requested.
- **Action**:
    - Reduce font size to `text-xs md:text-sm`.
    - Ensure the container is `w-full` and `bottom-0` with a semi-transparent background.

## 4. Verification
- **Visual**: Confirm dropdown has an arrow and subtitles are small/bottom-aligned.
- **Functional**: Reload page and check if previously selected voice is remembered. Confirm voice doesn't change between turns.