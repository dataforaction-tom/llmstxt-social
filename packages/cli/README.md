# llmstxt-social CLI

Command-line tool to generate and assess llms.txt files for UK social sector organisations.

This is the CLI interface for the llmstxt-core library. It provides an easy-to-use command-line interface for generating llms.txt files, validating them, and assessing their quality.

## Installation

```bash
cd packages/cli
pip install -e .
```

This will also install the core library as a dependency.

## Usage

```bash
# Generate llms.txt for a charity
llmstxt generate https://example-charity.org.uk

# Generate for a funder
llmstxt generate https://example-trust.org.uk --template funder

# Assess quality
llmstxt assess https://example-charity.org.uk

# Validate existing file
llmstxt validate ./llms.txt

# Preview what would be crawled
llmstxt preview https://example.org.uk
```

## Documentation

See the main repository README for full documentation.

## License

MIT
