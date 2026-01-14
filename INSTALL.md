# Installation Guide

## Windows Installation Issues

If you encounter errors like:
```
ERROR: Could not install packages due to an OSError: [WinError 2]
The system cannot find the file specified: 'C:\\Python311\\Scripts\\*.exe'
```

This is a Windows file locking issue. Try these solutions:

### Solution 1: Close conflicting processes
1. Close any terminal windows running Python
2. Close VS Code or other IDEs
3. Try the install again

### Solution 2: Use --force-reinstall
```bash
cd packages/core
pip install -e . --force-reinstall --no-deps
pip install -e .

cd ../cli
pip install -e . --force-reinstall --no-deps
pip install -e .
```

### Solution 3: Install in a virtual environment (Recommended)
```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install packages
cd packages/core && pip install -e . && cd ../..
cd packages/cli && pip install -e . && cd ../..
```

### Solution 4: Update pip
```bash
python -m pip install --upgrade pip
```

## Standard Installation

### 1. Install Core Package
```bash
cd packages/core
pip install -e .
```

### 2. Install CLI Package
```bash
cd ../cli
pip install -e .
```

### 3. Verify Installation
```bash
llmstxt --version
```

Or test with Python:
```bash
python test_monorepo.py
```

## Optional: Playwright for JavaScript Sites
```bash
playwright install chromium
```

## Troubleshooting

### "command not found: llmstxt"
The Scripts directory might not be in your PATH. Try:
```bash
python -m llmstxt_social.cli --version
```

Or add Python Scripts to PATH:
- Windows: `C:\Python311\Scripts`
- Add to System Environment Variables

### Import errors
Make sure both core and CLI packages are installed:
```bash
pip list | grep llmstxt
```

Should show:
```
llmstxt-core       0.2.0
llmstxt-social     0.2.0
```
