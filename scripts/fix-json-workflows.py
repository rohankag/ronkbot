#!/usr/bin/env python3
"""
Fix n8n workflow JSON files that contain unescaped control characters
(raw newlines, raw backslash-newline sequences) inside JSON string values.
"""

import json
import sys


def fix_json_strings(text: str) -> str:
    """
    Walk the raw JSON text character-by-character and, inside JSON string values,
    replace any bare control characters (< U+0020) with their proper \\uXXXX or
    named escape, and replace invalid \\<ctrl> sequences with the correct escape.
    """
    NAMED = {"\n": "n", "\r": "r", "\t": "t", "\b": "b", "\f": "f"}
    BARE_NAMED = {"\n": "\\n", "\r": "\\r", "\t": "\\t", "\b": "\\b", "\f": "\\f"}

    result = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(text):
        c = text[i]

        if escape_next:
            # c is the character after a backslash inside a string
            valid_escapes = '"\\bfnrtu/'
            if c in valid_escapes:
                result.append(c)
            elif ord(c) < 0x20:
                # Invalid: backslash followed by a raw control char
                # The backslash is already appended; just convert the control char
                esc = NAMED.get(c, f"u{ord(c):04x}")
                result.append(esc)
            else:
                # Unknown escape like \{ \} \` \! — not valid in JSON.
                # Escape the backslash so \X becomes \\X (literal backslash + X).
                result[-1] = "\\\\"  # replace the already-appended single \
                result.append(c)
            escape_next = False
            i += 1
            continue

        if in_string:
            if c == "\\":
                escape_next = True
                result.append(c)
            elif c == '"':
                in_string = False
                result.append(c)
            elif ord(c) < 0x20:
                # Bare control character inside a JSON string — must be escaped
                result.append(BARE_NAMED.get(c, f"\\u{ord(c):04x}"))
            else:
                result.append(c)
        else:
            if c == '"':
                in_string = True
                result.append(c)
            else:
                result.append(c)

        i += 1

    return "".join(result)


FILES = [
    "n8n-workflows/03-command-handler.json",
    "n8n-workflows/04-gmail-authentication.json",
    "n8n-workflows/05-email-reader.json",
    "n8n-workflows/06-email-sender.json",
]

overall_ok = True

for path in FILES:
    with open(path, "r", encoding="utf-8") as fh:
        original = fh.read()

    try:
        json.loads(original)
        print(f"OK (already valid): {path}")
        continue
    except json.JSONDecodeError:
        pass

    fixed = fix_json_strings(original)

    try:
        parsed = json.loads(fixed)
    except json.JSONDecodeError as e:
        print(f"FAIL (still broken after fix): {path}: {e}")
        overall_ok = False
        continue

    # Write back nicely-formatted
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(parsed, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"FIXED: {path}")

if not overall_ok:
    sys.exit(1)

print("\nAll workflow JSON files are now valid.")
