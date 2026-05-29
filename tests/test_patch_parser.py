from ai_pr_review.models import PRFile
from ai_pr_review.patch_parser import parse_file_patch, parse_pr_file


def test_parse_file_patch_tracks_added_line_numbers_in_single_hunk() -> None:
    patch = """@@ -10,3 +10,4 @@ def run():
 context = build_context()
-old_call()
+new_call()
+return context
 unchanged()
"""

    parsed = parse_file_patch(patch)

    assert len(parsed.hunks) == 1
    assert parsed.hunks[0].old_start == 10
    assert parsed.hunks[0].new_start == 10
    added = parsed.added_lines()
    assert [(line.new_line_number, line.content) for line in added] == [
        (11, "new_call()"),
        (12, "return context"),
    ]


def test_parse_file_patch_tracks_multiple_hunks_independently() -> None:
    patch = """@@ -1,2 +1,2 @@
-import os
+import pathlib
 keep = True
@@ -20,2 +20,3 @@ def render():
 value = 1
+print(value)
 return value
"""

    parsed = parse_file_patch(patch)

    assert len(parsed.hunks) == 2
    assert [(line.new_line_number, line.content) for line in parsed.added_lines()] == [
        (1, "import pathlib"),
        (21, "print(value)"),
    ]


def test_parse_file_patch_ignores_file_headers() -> None:
    patch = """--- a/app.py
+++ b/app.py
@@ -1,1 +1,2 @@
 print("hello")
+print("world")
"""

    parsed = parse_file_patch(patch)

    assert [(line.new_line_number, line.content) for line in parsed.added_lines()] == [
        (2, 'print("world")')
    ]


def test_parse_file_patch_handles_new_file_hunks() -> None:
    patch = """@@ -0,0 +1,3 @@
+def main():
+    return 1
+
"""

    parsed = parse_file_patch(patch)

    assert [(line.new_line_number, line.content) for line in parsed.added_lines()] == [
        (1, "def main():"),
        (2, "    return 1"),
        (3, ""),
    ]


def test_parse_file_patch_tracks_deleted_lines_without_advancing_new_line() -> None:
    patch = """@@ -5,3 +5,3 @@
 keep_before()
-remove_me()
+add_me()
 keep_after()
"""

    parsed = parse_file_patch(patch)

    hunk_lines = parsed.hunks[0].lines
    deleted = [line for line in hunk_lines if line.kind == "delete"]
    added = [line for line in hunk_lines if line.kind == "add"]
    assert [(line.old_line_number, line.content) for line in deleted] == [(6, "remove_me()")]
    assert [(line.new_line_number, line.content) for line in added] == [(6, "add_me()")]


def test_parse_pr_file_handles_missing_patch_without_hunks() -> None:
    file = PRFile(
        filename="large.bin",
        status="modified",
        additions=0,
        deletions=0,
        patch="",
    )

    parsed = parse_pr_file(file)

    assert parsed.filename == "large.bin"
    assert parsed.status == "modified"
    assert parsed.hunks == []
    assert parsed.added_lines() == []
