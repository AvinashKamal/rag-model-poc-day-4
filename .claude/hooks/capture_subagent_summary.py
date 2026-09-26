import json
import re
import sys
import datetime

state_file = sys.argv[1]
data = json.load(sys.stdin)

# agent_transcript_path is the subagent's own transcript; transcript_path is
# the parent session's transcript. Reading transcript_path here was the bug:
# every SubagentStop fired against the same shared parent transcript, so
# entries collided/duplicated instead of reading each subagent's own report.
transcript_path = data.get("agent_transcript_path") or data.get("transcript_path", "")
agent_name = (
    data.get("agent_type")
    or data.get("subagent_type")
    or data.get("agent")
    or "unknown"
)

block = None
if transcript_path:
    try:
        with open(transcript_path, "r") as f:
            lines = f.readlines()
        for line in reversed(lines):
            try:
                entry = json.loads(line)
            except Exception:
                continue
            msg = entry.get("message", entry)
            content = msg.get("content") if isinstance(msg, dict) else None
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "text":
                        text += part.get("text", "")
                    # The final report is often delivered via a
                    # SubagentHandback tool call rather than plain assistant
                    # text (the trailing text part is just a stub like
                    # "Report delivered via SubagentHandback."); the actual
                    # STATUS/FILES_CHANGED block lives in the tool call's
                    # input.message.
                    elif (
                        part.get("type") == "tool_use"
                        and part.get("name") == "SubagentHandback"
                    ):
                        input_message = part.get("input", {}).get("message")
                        if isinstance(input_message, str):
                            text += input_message
            if "STATUS:" in text and "FILES_CHANGED:" in text:
                m = re.search(
                    r"STATUS:\s*(.*?)\nFILES_CHANGED:\s*(.*?)\nKEY_DECISIONS:\s*(.*?)\nOPEN_ISSUES:\s*(.*?)(?:\n```|\Z)",
                    text,
                    re.S,
                )
                if m:
                    block = {
                        "status": m.group(1).strip(),
                        "files_changed": m.group(2).strip(),
                        "key_decisions": m.group(3).strip(),
                        "open_issues": m.group(4).strip(),
                    }
                break
    except Exception:
        pass

if block is None:
    sys.exit(0)

date = datetime.date.today().isoformat()
entry = (
    f"\n## {date} — {agent_name}\n"
    f"STATUS: {block['status']}\n"
    f"FILES_CHANGED: {block['files_changed']}\n"
    f"KEY_DECISIONS: {block['key_decisions']}\n"
    f"OPEN_ISSUES: {block['open_issues']}\n"
)

with open(state_file, "a") as f:
    f.write(entry)
