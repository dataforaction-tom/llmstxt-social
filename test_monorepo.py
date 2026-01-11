"""Test script to verify monorepo refactor structure is correct."""

import sys
from pathlib import Path

print("Testing monorepo structure...")
print("=" * 50)

# Test 1: Verify package directories exist
core_pkg = Path(__file__).parent / "packages" / "core" / "src" / "llmstxt_core"
cli_pkg = Path(__file__).parent / "packages" / "cli" / "src" / "llmstxt_social"

if core_pkg.exists() and core_pkg.is_dir():
    print("[OK] Core package directory exists")
else:
    print("[FAIL] Core package directory missing")
    sys.exit(1)

if cli_pkg.exists() and cli_pkg.is_dir():
    print("[OK] CLI package directory exists")
else:
    print("[FAIL] CLI package directory missing")
    sys.exit(1)

# Test 2: Verify core package has all modules
required_core_modules = [
    "crawler.py",
    "crawler_playwright.py",
    "extractor.py",
    "analyzer.py",
    "generator.py",
    "validator.py",
    "assessor.py",
    "__init__.py"
]

for module in required_core_modules:
    module_path = core_pkg / module
    if module_path.exists():
        print(f"[OK] Core module exists: {module}")
    else:
        print(f"[FAIL] Core module missing: {module}")
        sys.exit(1)

# Test 3: Verify core package has subdirectories
required_core_dirs = ["enrichers", "templates"]
for dirname in required_core_dirs:
    dir_path = core_pkg / dirname
    if dir_path.exists() and dir_path.is_dir():
        print(f"[OK] Core directory exists: {dirname}/")
    else:
        print(f"[FAIL] Core directory missing: {dirname}/")
        sys.exit(1)

# Test 4: Verify CLI has cli.py
cli_file = cli_pkg / "cli.py"
if cli_file.exists():
    print("[OK] CLI module exists: cli.py")
else:
    print("[FAIL] CLI module missing: cli.py")
    sys.exit(1)

# Test 5: Verify CLI imports from llmstxt_core (not relative imports)
with open(cli_file, 'r', encoding='utf-8') as f:
    cli_content = f.read()
    if 'from llmstxt_core.crawler import' in cli_content:
        print("[OK] CLI uses llmstxt_core imports")
    else:
        print("[FAIL] CLI not using llmstxt_core imports")
        sys.exit(1)

    if 'from .crawler import' in cli_content:
        print("[FAIL] CLI still has relative imports")
        sys.exit(1)

# Test 6: Verify pyproject.toml files exist
core_pyproject = Path(__file__).parent / "packages" / "core" / "pyproject.toml"
cli_pyproject = Path(__file__).parent / "packages" / "cli" / "pyproject.toml"

if core_pyproject.exists():
    print("[OK] Core pyproject.toml exists")
else:
    print("[FAIL] Core pyproject.toml missing")
    sys.exit(1)

if cli_pyproject.exists():
    print("[OK] CLI pyproject.toml exists")
else:
    print("[FAIL] CLI pyproject.toml missing")
    sys.exit(1)

print("=" * 50)
print("All structure tests passed! Monorepo refactor is successful.")
print("\nNext steps:")
print("1. Install packages: cd packages/core && pip install -e .")
print("2. Install CLI: cd packages/cli && pip install -e .")
print("3. Test CLI: llmstxt --version")
