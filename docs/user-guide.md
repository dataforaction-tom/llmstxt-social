# User Guide

This guide covers everything you need to know about using llmstxt-social to generate and maintain your organisation's llms.txt file.

## Generating your llms.txt file

### Free generation

You can generate a basic llms.txt file at no cost:

1. Go to the **Generate** page
2. Enter your organisation's website URL
3. Choose your **organisation type** — charity, funder, public sector, or startup
4. Select the **sector** and **primary goal** that best describe your work
5. Click **Generate Free**

You'll see real-time progress as the system crawls your website, extracts content, and generates your file. Once complete, you can preview the result and download it.

Free generation is limited to 10 per day and does not include data enrichment or quality assessment.

### Paid generation

For a one-off payment of £9, you get a more thorough result:

1. Follow the same steps as above, but select the **Paid** tier
2. Click **Generate (Proceed to Payment)**
3. Enter your card details in the secure payment form (powered by Stripe)
4. Once payment is confirmed, generation begins automatically

Paid generation includes everything in the free tier, plus:

- **Enrichment data** from official sources (see below)
- **Quality assessment** with scores, grades, and recommendations
- **Website gap analysis** highlighting missing information
- Results are available for 30 days, during which you can revisit them

### Understanding your results

After generation completes, you'll see:

- **Your llms.txt file** — ready to download and upload to your website's root directory
- **Quality scores** (paid tier) — an overall score out of 100, plus separate completeness and quality grades from A to F
- **Recommendations** (paid tier) — specific, actionable suggestions for improving your AI visibility
- **Enrichment data** (paid tier) — official information cross-referenced from external sources

## Organisation types and templates

llmstxt-social uses specialised templates for different types of organisation. Each template knows what information matters most for your sector.

### Charity

Designed for UK charities and voluntary, community, and social enterprise (VCSE) organisations. The template focuses on your charitable objects, services, beneficiaries, and impact. If your charity is registered with the Charity Commission, paid generation will automatically pull in official data including registration details, financial information, and trustee names.

### Funder

Built for foundations, trusts, and grant-making bodies. The template highlights your funding programmes, eligibility criteria, application processes, and grant-making priorities. Paid generation enriches your profile with data from 360Giving, including grant amounts, geographic distribution, and funding trends.

### Public sector

Tailored for local councils, NHS trusts, government departments, and other public bodies. The template emphasises public services, contact channels, and how residents can access support.

### Startup

For social enterprises, impact-driven startups, and mission-led businesses. The template covers your product or service, target market, social impact, and how to work with you.

## Sectors and goals

Within each organisation type, you can select a more specific **sector** (such as health, education, environment, or housing) and a **primary goal** (such as direct service delivery, advocacy, or capacity building). These choices help the AI tailor your llms.txt to emphasise what matters most for your area of work.

## Data enrichment

Paid generation automatically enriches your llms.txt with data from trusted external sources:

### Charity Commission (for charities)

If your organisation is a registered UK charity, the system looks up your official record and incorporates:

- Registration number and date
- Official charitable objects
- Financial summary (income and spending)
- Trustee information
- Classification and activities

This helps ensure your llms.txt is accurate and consistent with your official registration.

### 360Giving (for funders)

If your organisation publishes grants data through 360Giving, the system pulls in:

- Total grant amounts and number of grants
- Geographic distribution of funding
- Funding trends over time
- Types of organisations you fund

This gives AI systems a richer picture of your grant-making activity.

## Quality assessment

Every paid generation includes a detailed quality assessment. This tells you how well your llms.txt represents your organisation and where there's room to improve.

### Scores and grades

- **Overall score** — a number from 0 to 100 reflecting the overall quality
- **Completeness grade** — how much essential information is present (A to F)
- **Quality grade** — how clear, accurate, and well-structured the content is (A to F)

### Recommendations

The assessment includes specific recommendations, grouped by priority. These might suggest adding missing contact information, clarifying your services, or improving the structure of your website so future generations are even better.

### Website gap analysis

The assessment also identifies pages that are missing from your website but would improve your AI visibility — for example, a dedicated services page, an impact report, or a clear "about us" section.

## Signing in

llmstxt-social uses passwordless sign-in:

1. Enter your email address on the **Login** page
2. Check your inbox for a magic link
3. Click the link to sign in — no password needed

Once signed in, your paid generations and subscriptions are linked to your account, and you can access them from the dashboard.

## Dashboard

After signing in, the dashboard shows:

- **Your generations** — all paid generations linked to your account, with their status and results
- **Active subscriptions** — any URLs you're monitoring with a subscription
- **Monitoring history** — a record of changes detected on your monitored sites

## Subscriptions and monitoring

With a subscription (£9/month per URL), your llms.txt is automatically kept up to date:

- The system regularly checks your website for changes
- When changes are detected, your llms.txt is regenerated automatically
- You receive an email notification with a summary of what changed
- The dashboard shows a full history of updates and changes

You can manage your subscriptions from the dashboard, including cancelling at any time.

## Uploading your llms.txt

Once you've generated your file, upload it to the root of your website so it's accessible at:

```
https://yourwebsite.org/llms.txt
```

This is the standard location where AI systems look for the file. If you're not sure how to upload files to your website, ask your web administrator or hosting provider to place the file in the same directory as your homepage.

## Using the command-line tool

llmstxt-social also includes an open-source command-line tool for users who prefer working in a terminal.

### Generate a file

```bash
llmstxt generate https://your-website.org.uk
```

### Assess an existing file

```bash
llmstxt assess https://your-website.org.uk
```

### Validate a file against the specification

```bash
llmstxt validate ./llms.txt
```

### Preview what would be crawled

```bash
llmstxt preview https://your-website.org.uk
```

The CLI requires an Anthropic API key set as the `ANTHROPIC_API_KEY` environment variable. Optionally, set `CHARITY_COMMISSION_API_KEY` for charity enrichment.

## Privacy and analytics

The site uses Plausible Analytics, a privacy-friendly analytics tool that does not use cookies or track individual users. No personal data is collected through analytics.

Payment processing is handled securely by Stripe. Your card details are never stored on our servers.
