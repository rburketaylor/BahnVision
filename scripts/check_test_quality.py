#!/usr/bin/env python3
"""Detect tests that may not be asserting anything meaningful.

This script scans test files for test functions that don't contain
any assertions, which may indicate tests that pass without actually
validating behavior.

Usage:
    python scripts/check_test_quality.py [directory]

Examples:
    python scripts/check_test_quality.py backend/tests
    python scripts/check_test_quality.py frontend/src/tests
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


def find_test_files(directory: Path) -> list[Path]:
    """Find Python and TypeScript/TSX test files in the given directory."""
    test_files = []
    for pattern in [
        "test_*.py",
        "*_test.py",
        "*.test.ts",
        "*.test.tsx",
        "*.spec.ts",
        "*.spec.tsx",
    ]:
        test_files.extend(directory.rglob(pattern))
    return sorted(test_files)


def check_python_test_file(filepath: Path) -> list[str]:
    """Check a Python test file for functions without assertions.

    Returns a list of issue descriptions.
    """
    issues = []

    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError as e:
        return [f"{filepath}:0: Syntax error: {e}"]

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("test_"):
                continue

            # Skip fixtures decorated with @pytest.fixture
            if _is_fixture(node):
                continue

            has_assert = _function_has_assertions(node)

            if not has_assert:
                issues.append(
                    f"{filepath}:{node.lineno}: {node.name}() has no assertions"
                )

    return issues


def _is_fixture(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function is decorated with @pytest.fixture."""
    for decorator in func_node.decorator_list:
        # Simple @pytest.fixture
        if isinstance(decorator, ast.Attribute):
            if decorator.attr == "fixture":
                return True
        # @pytest.fixture() with parentheses
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr == "fixture":
                    return True
        # Just @fixture (imported directly)
        if isinstance(decorator, ast.Name):
            if decorator.id == "fixture":
                return True
    return False


def _function_has_assertions(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function contains any assertions."""
    # Common assertion patterns
    assert_attrs = {
        # pytest assertions
        "assert",
        "fail",  # pytest.fail()
        # unittest assertions
        "assertEqual",
        "assertNotEqual",
        "assertTrue",
        "assertFalse",
        "assertIs",
        "assertIsNot",
        "assertIsNone",
        "assertIsNotNone",
        "assertIn",
        "assertNotIn",
        "assertIsInstance",
        "assertNotIsInstance",
        "assertRaises",
        "assertRaisesRegex",
        "assertWarns",
        "assertWarnsRegex",
        "assertAlmostEqual",
        "assertNotAlmostEqual",
        "assertGreater",
        "assertGreaterEqual",
        "assertLess",
        "assertLessEqual",
        "assertRegex",
        "assertNotRegex",
        "assertCountEqual",
        # pytest.raises context manager
        "raises",
        # unittest.mock assertions (sync)
        "assert_called", "assert_called_once", "assert_called_with",
        "assert_called_once_with", "assert_any_call", "assert_has_calls",
        "assert_not_called",
        # unittest.mock assertions (async)
        "assert_awaited", "assert_awaited_once", "assert_awaited_with",
        "assert_awaited_once_with", "assert_any_await", "assert_has_awaits",
        "assert_not_awaited",
    }

    for child in ast.walk(func_node):
        # Check for assert statements
        if isinstance(child, ast.Assert):
            return True

        # Check for method calls like self.assertEqual(), pytest.raises()
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Attribute):
                if child.func.attr in assert_attrs:
                    return True
            # Check for pytest.raises
            if isinstance(child.func, ast.Attribute):
                if child.func.attr == "raises":
                    return True
        
        # Check for context managers (with pytest.raises)
        if isinstance(child, ast.With):
            for item in child.items:
                if isinstance(item.context_expr, ast.Call):
                    if isinstance(item.context_expr.func, ast.Attribute):
                        if item.context_expr.func.attr == "raises":
                            return True

    return False


_TS_TEST_START_RE = re.compile(r"\b(?:it|test)\s*\(")
_TS_ASSERT_RE = re.compile(
    r"\bexpect\s*\(|\bassert\s*\(|\bto(Be|Equal|StrictEqual|Match|Contain|Throw)\b"
)


def check_typescript_test_file(filepath: Path) -> list[str]:
    """Check a TS/TSX test file for test blocks without assertions."""
    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()
    issues: list[str] = []

    for start_line, block in _extract_ts_test_blocks(lines):
        if not _TS_ASSERT_RE.search(block):
            issues.append(
                f"{filepath}:{start_line}: test block appears to have no assertions"
            )

    return issues


def _extract_ts_test_blocks(lines: list[str]) -> list[tuple[int, str]]:
    """Extract rough test blocks for `it(...)` / `test(...)` patterns."""
    blocks: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not _TS_TEST_START_RE.search(line):
            i += 1
            continue

        start_line = i + 1
        block_lines = [line]
        brace_depth = line.count("{") - line.count("}")
        i += 1

        while i < len(lines):
            block_lines.append(lines[i])
            brace_depth += lines[i].count("{") - lines[i].count("}")
            if brace_depth <= 0 and ");" in lines[i]:
                i += 1
                break
            i += 1

        blocks.append((start_line, "\n".join(block_lines)))

    return blocks


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python check_test_quality.py <directory>")
        print("Example: python check_test_quality.py backend/tests")
        return 1
    
    directory = Path(sys.argv[1])
    if not directory.exists():
        print(f"Error: Directory '{directory}' does not exist")
        return 1
    
    test_files = find_test_files(directory)
    
    if not test_files:
        print(f"No test files found in {directory}")
        return 0
    
    print(f"Checking {len(test_files)} test files for assertion quality...\n")
    
    all_issues: list[str] = []
    for filepath in test_files:
        if filepath.suffix == ".py":
            issues = check_python_test_file(filepath)
        elif filepath.suffix in {".ts", ".tsx"}:
            issues = check_typescript_test_file(filepath)
        else:
            issues = []
        all_issues.extend(issues)
    
    if all_issues:
        print("⚠️  Tests without assertions detected:\n")
        for issue in all_issues:
            print(f"  {issue}")
        print(f"\n{len(all_issues)} potential issues found.")
        print("\nThese tests may pass without actually validating behavior.")
        print("Consider adding assertions or using pytest.raises() for exception testing.")
        return 1
    else:
        print("✅ All test functions contain assertions!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
