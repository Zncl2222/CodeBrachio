from __future__ import annotations

import re


def parse_diff(diff_text: str, file_name: str) -> list[dict[str, str | int]]:
    result = []
    lines = diff_text.splitlines()
    for i, line in enumerate(lines):
        match = re.match(
            r'@@ -(?P<old_start>\d+),(?P<old_count>\d+) \+(?P<new_start>\d+),(?P<new_count>\d+) @@',
            line,
        )
        if match:
            start_line = int(match.group('new_start'))
            end_line = start_line + int(match.group('new_count')) - 1

            # Extract code snippet
            snippet_lines = []
            j = i
            while j < len(lines) and not lines[j].startswith('diff --git'):
                snippet_lines.append(lines[j][0:].split('@@')[-1])
                j += 1

            code_snippet = '\n'.join(snippet_lines)

            result.append(
                {
                    'file': file_name,
                    'start_line': start_line,
                    'end_line': end_line,
                    'code_snippet': code_snippet,
                }
            )

    return result
