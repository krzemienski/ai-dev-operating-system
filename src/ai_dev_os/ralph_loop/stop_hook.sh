#!/usr/bin/env bash
# =============================================================================
# Ralph Loop Stop Hook
#
# This script is called by Claude Code's stop hook mechanism to enforce
# loop continuation. When the AI tries to stop working, this hook checks
# if the Ralph Loop state indicates incomplete work. If incomplete, it
# outputs the "boulder" signal to prevent the session from ending.
#
# The hook mechanism works by:
# 1. Claude Code checks for stop hooks before ending a session
# 2. If a stop hook exits non-zero or prints specific content, the session continues
# 3. The "The boulder never stops" message signals ralph/ultrawork mode to continue
#
# Usage (configured in .claude/settings.json):
#   "stopHooks": [{ "command": "bash .omc/stop_hook.sh" }]
#
# Or as a PreToolUse hook on exit signals to prevent early termination.
# =============================================================================

set -euo pipefail

# Path to the Ralph Loop state file (relative to worktree root)
RALPH_STATE_FILE=".omc/state/ralph-state.json"

# Check if the state file exists
if [[ ! -f "$RALPH_STATE_FILE" ]]; then
    # No active Ralph Loop — allow exit
    exit 0
fi

# Parse the state file with jq (required dependency)
if ! command -v jq &>/dev/null; then
    echo "Warning: jq not found, skipping Ralph Loop check" >&2
    exit 0
fi

# Extract key fields from the state
STATUS=$(jq -r '.status // "unknown"' "$RALPH_STATE_FILE" 2>/dev/null)
ITERATION=$(jq -r '.iteration // 0' "$RALPH_STATE_FILE" 2>/dev/null)
MAX_ITERATIONS=$(jq -r '.max_iterations // 100' "$RALPH_STATE_FILE" 2>/dev/null)
TOTAL_TASKS=$(jq -r '.task_list | length' "$RALPH_STATE_FILE" 2>/dev/null)
COMPLETED_TASKS=$(jq -r '[.task_list[] | select(.status == "completed")] | length' "$RALPH_STATE_FILE" 2>/dev/null)

# Terminal states — allow exit
if [[ "$STATUS" == "complete" ]] || [[ "$STATUS" == "cancelled" ]] || [[ "$STATUS" == "failed" ]]; then
    echo "Ralph Loop terminal state: $STATUS" >&2
    exit 0
fi

# Max iterations reached — allow exit
if [[ "$ITERATION" -ge "$MAX_ITERATIONS" ]]; then
    echo "Ralph Loop max iterations ($MAX_ITERATIONS) reached" >&2
    exit 0
fi

# Check if all tasks are complete
if [[ "$TOTAL_TASKS" -gt 0 ]] && [[ "$COMPLETED_TASKS" -ge "$TOTAL_TASKS" ]]; then
    echo "Ralph Loop: All $TOTAL_TASKS tasks completed" >&2
    exit 0
fi

# Work remains — emit the boulder signal to prevent exit
# This message is detected by the OMC hooks system to signal continuation
REMAINING=$((TOTAL_TASKS - COMPLETED_TASKS))
echo "The boulder never stops"
echo ""
echo "Ralph Loop Status:"
echo "  Iteration: $ITERATION / $MAX_ITERATIONS"
echo "  Progress: $COMPLETED_TASKS / $TOTAL_TASKS tasks completed"
echo "  Remaining: $REMAINING tasks pending"
echo ""
echo "Continue working until all tasks are complete."

# Exit non-zero to signal the hook runner that work must continue
exit 1
