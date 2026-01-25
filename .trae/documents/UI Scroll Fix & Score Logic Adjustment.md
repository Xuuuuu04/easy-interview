# UI & Logic Fix Plan

## 1. Fix Plan Panel Scrolling (index.html)
- **Problem**: The right-side plan panel (`#plan-checklist`) lacks a scrollbar, causing items to be cut off.
- **Action**: Ensure the parent container has `overflow-y-auto` and a defined height/flex-grow structure. Specifically, check `.right-panel-content` and `#plan-checklist` styles in `index.html`. It seems `pr-1` and `custom-scrollbar` are present, but the parent flex container might not be constraining height correctly.

## 2. Fix Zero Score Bug (interview_service.py)
- **Problem**: Users are seeing 0/100 scores.
- **Reason**: The `mark_item_complete` tool call might be defaulting to 0 if the LLM doesn't output a score, or the prompt logic allows 0 too easily.
- **Action**:
    - Modify `mark_item_complete` in `app/services/interview_service.py` to enforce a minimum score (e.g., 60) if the answer is "passable".
    - Update the system prompt to explicitly instruct the LLM: "If the answer is acceptable, score between 60-100. Only score < 60 for complete failure/refusal."
    - Add a fallback in the python code: `score = max(60, fn_args.get('score', 60))` if the evaluation is positive.

## 3. Verification
- **Visual**: Check if the scrollbar appears on the right panel when there are many items.
- **Logic**: Simulate a conversation turn where the user gives a short but correct answer, ensuring the score is reasonable (not 0).