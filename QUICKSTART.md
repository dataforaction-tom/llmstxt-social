# Quick Start Guide

## Installation (After Import Fixes)

The import errors have been fixed. Now reinstall the packages:

```bash
# Make sure you're in your virtual environment
# If not, activate it:
.venv\Scripts\activate

# Reinstall core package
cd packages/core
pip install -e . --force-reinstall

# Reinstall CLI package
cd ../cli
pip install -e . --force-reinstall

# Go back to root
cd ../..
```

## Verify Installation

```bash
# Test the command
llmstxt --version

# Should output:
# llmstxt-social version 0.2.0
```

## Quick Test

```bash
# Generate llms.txt for a charity
llmstxt generate https://example-charity.org.uk

# Assess quality
llmstxt assess https://example-charity.org.uk

# Validate existing file
llmstxt validate ./llms.txt
```

## What Was Fixed

The `__init__.py` file in the core package had incorrect imports:
- Changed `LLMSTxtValidator` → `validate_llmstxt` (function, not class)
- Changed `Assessment` → `AssessmentResult` (correct class name)
- Changed `FindingSeverity` → `IssueSeverity` (correct enum name)

All modules now import correctly!
