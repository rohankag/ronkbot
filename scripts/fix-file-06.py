#!/usr/bin/env python3
"""
Advanced JSON fixer for n8n workflow files with embedded multiline code.

Problem: The jsCode and similar string values contain:
1. Literal newlines (must be escaped as \n)
2. Unescaped double quotes inside code blocks
3. Invalid JSON escape sequences like \{ \} \`

Strategy: rebuild broken jsCode string values by:
1. Finding where a jsCode string "should" end by matching the structural
   JSON pattern (close of parameters object), rather than just finding the
   first unescaped double-quote.
"""

import json
import re
import sys


def escape_code_block(code: str) -> str:
    """Properly JSON-encode a code string value (without outer quotes)."""
    return json.dumps(code)[1:-1]  # json.dumps adds outer "", strip them


def fix_file_06(path: str) -> bool:
    """
    Custom fixer for 06-email-sender.json.
    The file has jsCode values where JS code is inline with literal newlines
    and unescaped double quotes.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    # First fix: try the generic control-char fixer
    # If that works, great
    try:
        parsed = json.loads(raw)
        print(f"OK (already valid): {path}")
        return True
    except json.JSONDecodeError:
        pass

    # Advanced fix: the file has embedded unescaped multiline code in string values
    # We need to find each "jsCode": "...code..." block and re-encode the code

    # Pattern: find "jsCode": "...code...", or "jsCode": "...code..." that spans multiple lines
    # The code block ends when we see the line: }];" or some other structural end

    # Rather than parse, let's use a regex to find the broken areas.
    # The signature of the problem: a JSON string value that spans multiple lines
    # (i.e., "key": "value\nmore value\n...final")

    # Strategy: find all "someKey": "...multiline content..." blobs
    # by looking for lines that end in " (closing quote + optional comma)
    # vs lines that don't end in a quote (are continuation of a string)

    lines = raw.split("\n")
    output_lines = []
    in_code_block = False
    code_key = None
    code_lines = []
    code_indent = ""

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not in_code_block:
            # Check if this line starts a multiline string value
            # Pattern: "key": "value_that_doesnt_end_with_quote_comma_or_just_quote
            m = re.match(r'^(\s*)"([^"]+)":\s*"(.*)', line)
            if m:
                indent = m.group(1)
                key = m.group(2)
                rest = m.group(3)  # everything after the opening "

                # Check if the string closes on this same line
                # A proper single-line JSON string would end with " or ",
                # after properly handling \\ escapes
                # Simple heuristic: if rest ends with \" or "\,  it's closed
                if rest.endswith('",') or rest.endswith('"') or rest.endswith('",\n'):
                    # Looks like a single-line value (possibly with issues inside)
                    output_lines.append(line)
                else:
                    # Multi-line string! Accumulate lines until we find the end
                    in_code_block = True
                    code_key = key
                    code_lines = [rest]
                    code_indent = indent
                    i += 1
                    continue
            else:
                output_lines.append(line)
        else:
            # We're inside a multiline string block
            # Look for the line that ends the code block
            # End indicators: line ends with "; or }];" or similar code endings
            # followed by the JSON structural close: closing "
            if stripped.endswith('";') or stripped.endswith('"];"') or stripped == '";':
                # Possible ending - but we need to be more careful
                code_lines.append(line)
                in_code_block = False
                # Reconstruct the proper JSON line
                full_code = "\n".join(code_lines)
                # Strip the trailing closing quote if present in last line
                # The last line should end with " (closing the JSON string)
                if full_code.endswith('"'):
                    full_code = full_code[:-1]  # remove the trailing "
                encoded = escape_code_block(full_code)
                output_lines.append(f'{code_indent}"{code_key}": "{encoded}",')
                code_lines = []
            elif stripped.endswith('}"') or stripped.endswith(']"') or (stripped.endswith('"') and not stripped.startswith('"')):
                code_lines.append(line.rstrip())
                in_code_block = False
                full_code = "\n".join(code_lines)
                if full_code.endswith('"'):
                    full_code = full_code[:-1]
                encoded = escape_code_block(full_code)
                output_lines.append(f'{code_indent}"{code_key}": "{encoded}",')
                code_lines = []
            else:
                code_lines.append(line)

        i += 1

    fixed = "\n".join(output_lines)

    try:
        parsed = json.loads(fixed)
        print(f"FIXED (advanced): {path}")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2, ensure_ascii=False)
            f.write("\n")
        return True
    except json.JSONDecodeError as e:
        print(f"FAIL (advanced fixer also failed): {path}: {e}")
        # Show context
        fixed_lines = fixed.split("\n")
        line_no = e.lineno - 1
        if 0 <= line_no < len(fixed_lines):
            ctx_start = max(0, line_no - 3)
            for j, ln in enumerate(fixed_lines[ctx_start:line_no+3], start=ctx_start+1):
                print(f"  {j}: {repr(ln[:120])}")
        return False


if __name__ == "__main__":
    result = fix_file_06("n8n-workflows/06-email-sender.json")
    sys.exit(0 if result else 1)
