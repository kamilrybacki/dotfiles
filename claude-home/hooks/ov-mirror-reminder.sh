#!/usr/bin/env bash
# PostToolUse (Write|Edit): after a Claude memory file is saved, require mirroring its
# durable content to OpenViking in the same turn (the only memory other agents can read).
f=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty')
case "$f" in
  */.claude/projects/*/memory/MEMORY.md) exit 0 ;;
  */.claude/projects/*/memory/*.md) ;;
  *) exit 0 ;;
esac
name=$(basename "$f")
jq -n --arg n "$name" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:("Memory file " + $n + " was just saved. OpenViking is the mandatory shared memory: in THIS turn, mirror its durable content (gotchas, root causes, decisions + why, runbooks) with openviking__write mode=append or openviking__edit into the matching viking://resources/homelab-knowledge/<area>-gotchas.md, secrets redacted. Skip only for a personal preference that no other agent needs, and say so.")}}'
