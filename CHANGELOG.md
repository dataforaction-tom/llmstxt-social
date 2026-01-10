# Changelog

All notable changes to llmstxt-social will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-01-10

### Added

- **Charity Commission API Integration**
  - Fetch official charity data from the Charity Commission
  - Support for both API (with key) and public register scraping (fallback)
  - Enriches charity profiles with:
    - Official name, status, and registration details
    - Latest financial data (income/expenditure)
    - Charitable objects and activities
    - Trustee information
    - Contact details
  - Enabled by default with `--enrich` flag (use `--no-enrich` to disable)

- **360Giving Data Enrichment for Funders**
  - Integration with 360Giving open grants data
  - Fetches comprehensive funder grant history
  - Analyzes grant patterns:
    - Total grants and amounts
    - Average grant size and ranges
    - Geographic distribution
    - Funding themes and priorities
    - Sample recipients
    - Grants over time trends
  - Enable with `--enrich-360` flag

- **Playwright Support for JavaScript Sites**
  - Full browser rendering for JavaScript-heavy websites
  - Handles single-page applications (React, Vue, Angular)
  - Dynamic content loading support
  - Enable with `--playwright` flag
  - Automatically waits for network idle
  - Headless Chrome integration

- **New CLI Options**
  - `--enrich-360/--no-enrich-360` - 360Giving data enrichment
  - `--playwright/--no-playwright` - JavaScript rendering
  - `--enrich/--no-enrich` - Now enabled by default

- **New Dependencies**
  - `playwright>=1.40` - Browser automation
  - `pandas>=2.0` - Data analysis for grants data

- **Tests**
  - `tests/test_charity_commission.py` - Charity Commission tests
  - `tests/test_360giving.py` - 360Giving enrichment tests

### Changed

- Updated version from 0.1.0 to 0.2.0
- Changed `--enrich` flag to be enabled by default (was disabled in 0.1.0)
- Improved user agent strings for better website compatibility
- Enhanced error handling in all enrichment modules

### Fixed

- Better handling of missing data in enrichment modules
- Improved charity number detection patterns
- Fixed rate limiting for browser-based crawling

## [0.1.0] - 2026-01-09

### Added

- Initial release
- Smart website crawling with robots.txt respect
- Content extraction and HTML parsing
- Page type classification (14 types)
- Claude AI-powered analysis
- Charity and funder templates
- Comprehensive validation
- Rich CLI with progress bars
- Test suite for core modules
- MIT license
- Comprehensive documentation
