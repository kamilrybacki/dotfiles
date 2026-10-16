#!/usr/bin/env bash
# SessionStart: Paperclip items waiting for the operator (silent on failure).
exec python3 "$HOME/.claude/hooks/paperclip-inbox.py"
