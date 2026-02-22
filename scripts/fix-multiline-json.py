#!/usr/bin/env python3
"""
Targeted fixer for n8n workflow JSON files that have multiline code in jsCode keys.

The file has patterns like:
    "jsCode": "// first line of code
second line
...
return [{ json: {...} }];"

Where:
- The opening " starts the JSON string
- The code has literal newlines (need \n escaping)
- The code may have unescaped " chars inside (need \" escaping)
- The closing " of the JSON string is on the last line of code, after }];

Strategy:
1. Use regex to find each raw multiline code block
2. json.dumps() the code block content to get a properly escaped JSON string
3. Replace the raw block with the properly escaped version
"""

import json
import re
import sys
import textwrap


def extract_and_fix_multiline_strings(text: str) -> str:
    """
    Find all multiline JSON string values in the text and re-encode them.

    A multiline string value is one where the opening " and closing " are not
    on the same line. We detect the close by finding a line that ends with "
    (possibly followed by whitespace/comma) where the content before the "
    looks like a JS code-block ending or is just a clean line-end.

    Simple heuristic: a closing " is one that either:
    - Is the only meaningful char on the line (i.e., the line is just whitespace + ")
    - Or follows a JS statement terminator: }]; or }; or ]; or );"
    """
    lines = text.split("\n")
    result_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this line starts a problematic multiline JSON string value
        # Pattern: <indent>"key": "value_that_doesnt_close
        # (value_that_doesnt_close = the " at the end of "key": "..." is missing on this line)
        m = re.match(r'^(\s*)"(jsCode|jsExpression|code|expression|body|content|text)":\s*"(.*)', line)
        if m:
            indent = m.group(1)
            key = m.group(2)
            first_line_content = m.group(3)  # everything after the opening "

            # Check if the string CLOSES on this same line
            # We check by counting unescaped " chars in first_line_content
            #   - if it ends with " (unescaped) or ", it's closed here
            # Simple check: does the reconstructed line end with '" or '",?
            stripped_content = first_line_content.rstrip()
            if (stripped_content.endswith('"') or stripped_content.endswith('",')) and not stripped_content.endswith('\\"'):
                # Appears to close on this same line - check if it's valid
                # Test: try to parse just this key-value pair
                test = f'{{"k": "{first_line_content.rstrip(",").rstrip()}'
                if test.endswith('"'):
                    try:
                        json.loads(test + "}")
                        # It's valid single-line, pass through as-is
                        result_lines.append(line)
                        i += 1
                        continue
                    except json.JSONDecodeError:
                        pass

            # It's a multiline string. Collect lines until we find the closing "
            # The closing " is either:
            #   - A line that ends with "}];" followed immediately by "
            #   - A line that ends with "};" followed by "
            #   - A line that is just whitespace + " (or "},")
            code_content_lines = [first_line_content]
            i += 1
            closed = False

            while i < len(lines):
                cline = lines[i]
                stripped = cline.strip()

                # Check if this line is the closing line of the code block
                # Patterns that indicate end of JS code + JSON string close:
                is_closing = False

                # Pattern 1: line ends with "; (code end + string close)
                if stripped.endswith('}];"') or stripped.endswith('};"') or stripped.endswith('];"'):
                    # Last code char + closing JSON "
                    code_content_lines.append(stripped[:-1])  # strip the closing "
                    is_closing = True

                # Pattern 2: line is just " or ", (dangling closing quote)
                elif stripped in ('"', '",', '"\\n"', '""'):
                    # Don't add this line as code content - it's just the close
                    is_closing = True

                # Pattern 3: line ends with just " after some code that seems like statement end
                elif stripped.endswith('"') and not stripped.endswith('\\"'):
                    # Could be closing - check if it ends with a JS statement terminator + "
                    code_before_quote = stripped[:-1].rstrip()
                    if code_before_quote and code_before_quote[-1] in (';', '}', ']', ')'):
                        code_content_lines.append(stripped[:-1])
                        is_closing = True

                if is_closing:
                    # Reconstruct the properly-encoded JSON string
                    full_code = "\n".join(code_content_lines)
                    # json.dumps properly escapes newlines, quotes, backslashes, etc.
                    encoded_value = json.dumps(full_code)  # includes outer quotes
                    # Don't add trailing comma — let the surrounding structure provide it
                    result_lines.append(f"{indent}\"{key}\": {encoded_value}")
                    closed = True
                    i += 1
                    break
                else:
                    code_content_lines.append(cline)
                    i += 1

            if not closed:
                # Didn't find a close - pass through as-is (shouldn't happen)
                result_lines.append(f'{indent}"{key}": "{first_line_content}')
                result_lines.extend(code_content_lines[1:])
        else:
            result_lines.append(line)
            i += 1

    return "\n".join(result_lines)


FILES = [
    "n8n-workflows/06-email-sender.json",
]

overall_ok = True

for path in FILES:
    with open(path, "r", encoding="utf-8") as fh:
        original = fh.read()

    # Try original first
    try:
        json.loads(original)
        print(f"OK (already valid): {path}")
        continue
    except json.JSONDecodeError:
        pass

    # Apply multiline string fixer
    fixed = extract_and_fix_multiline_strings(original)

    try:
        parsed = json.loads(fixed)
        print(f"FIXED: {path}")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(parsed, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    except json.JSONDecodeError as e:
        print(f"FAIL (still broken): {path}: {e}")
        # Debug: show context around the error
        flines = fixed.split("\n")
        ln = e.lineno - 1
        for j, fl in enumerate(flines[max(0, ln-3):ln+4], start=max(0, ln-3)+1):
            print(f"  {j}: {repr(fl[:150])}")
        overall_ok = False

if not overall_ok:
    sys.exit(1)
