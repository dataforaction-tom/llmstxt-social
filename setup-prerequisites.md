# Setup & Prerequisites

## Before You Start

### 1. API Keys

**Anthropic API Key** (required)
- Sign up at https://console.anthropic.com
- Create an API key
- You'll need this in your `.env` file

**Charity Commission API** (optional, for enrichment)
- Register at https://register-of-charities.charitycommission.gov.uk/charity-search/-/api-documentation
- Free tier is sufficient
- Can skip for MVP and add later

### 2. Python Environment

Recommend using `uv` for fast dependency management:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create project
uv init llmstxt-social
cd llmstxt-social

# Create venv
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
```

### 3. Test Websites

Good candidates to test against (mix of sizes, platforms):

**Small charities:**
- A local charity you know well (can verify accuracy)
- FODI or similar from your network

**Medium charities:**
- Regional refugee support org
- Community foundation

**Funders:**
- A community foundation with clear eligibility info
- A family trust with good website

Having 3-4 test sites ready will help iterate on prompts quickly.

### 4. Git Repository

```bash
# Create repo
gh repo create llmstxt-social --public --clone
cd llmstxt-social

# Or manually
git init
git remote add origin git@github.com:yourusername/llmstxt-social.git
```

---

## Project Initialisation Commands

When you start Claude Code, you might want to run these first:

```bash
# Create directory structure
mkdir -p src/llmstxt_social/enrichers src/llmstxt_social/templates tests examples/charities examples/funders

# Create __init__.py files
touch src/llmstxt_social/__init__.py
touch src/llmstxt_social/enrichers/__init__.py
touch src/llmstxt_social/templates/__init__.py
touch tests/__init__.py

# Create .env.example
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env.example

# Create .gitignore
cat > .gitignore << 'EOF'
.venv/
__pycache__/
*.pyc
.env
dist/
*.egg-info/
.ruff_cache/
EOF
```

---

## Claude Code Session Tips

1. **Start with the spec** - Paste the full spec document first so Claude Code has context

2. **Build incrementally** - Don't try to build everything at once:
   - First: crawler.py + basic test
   - Then: extractor.py
   - Then: analyzer.py with prompts
   - Then: generator.py
   - Then: cli.py to tie it together
   - Finally: validator.py

3. **Test early** - After building crawler, test on a real site before moving on

4. **Prompt iteration** - The LLM prompts in analyzer.py will need tuning. Keep examples of good/bad outputs.

5. **Keep the spec handy** - Reference it when making decisions about structure

---

## First Milestone Checklist

Before considering the CLI "done", you should be able to:

```bash
# Generate for a charity
llmstxt generate https://some-charity.org.uk -o test-charity.txt
cat test-charity.txt  # Should be valid llms.txt format

# Generate for a funder  
llmstxt generate https://some-foundation.org.uk --template funder -o test-funder.txt
cat test-funder.txt  # Should have For Applicants section

# Validate
llmstxt validate test-charity.txt  # Should pass

# Preview
llmstxt preview https://some-charity.org.uk  # Should show crawl plan
```

---

## Useful References

- **llms.txt spec**: https://llmstxt.org/
- **Anthropic Python SDK**: https://docs.anthropic.com/en/api/client-sdks
- **Typer docs**: https://typer.tiangolo.com/
- **Rich docs**: https://rich.readthedocs.io/
- **Charity Commission API**: https://register-of-charities.charitycommission.gov.uk/charity-search/-/api-documentation
- **BeautifulSoup docs**: https://www.crummy.com/software/BeautifulSoup/bs4/doc/

---

## If You Get Stuck

Common issues and fixes:

**Rate limiting on crawl**
- Add delays between requests (1 req/sec default)
- Some hosts block rapid crawling

**Claude API errors**
- Check API key is set correctly
- Check you have credits
- Sonnet is recommended (fast + cheap)

**Page classification wrong**
- The rule-based classifier in extractor.py will need tuning for edge cases
- Consider adding more URL patterns

**Output format wrong**
- Check against llmstxt.org spec
- Validate with the validator before manual review

---

## Publishing (Later)

When ready to publish to PyPI:

```bash
# Build
uv build

# Publish (need PyPI account)
uv publish
```

For now, focus on getting it working locally first.
