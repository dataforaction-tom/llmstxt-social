# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- **Privacy-friendly analytics** — the site now uses Plausible Analytics, which respects your privacy and doesn't use cookies or track individuals
- **Improved production stability** — background processing is now more reliable with better health checks and database connection handling
- **Database migrations managed properly** — all database changes now go through a controlled migration process, reducing the risk of issues during updates

### Changed

- **Full generation is now free** — every generation includes data enrichment (Charity Commission, 360Giving) and the AI-powered quality assessment, at no cost. The limit of 10 generations per day still applies, and results are stored for 7 days.
- **The £9 one-time tier has been withdrawn** — there's no longer anything to pay for on a one-off generation, so the tier selector and payment step are gone. Monitoring subscriptions (£9/month) are unchanged.
- **Your dashboard now lists every assessed generation** — previously only paid generations appeared; now any generation with a quality assessment linked to your account shows up.
- **Streamlined deployment configuration** — removed outdated settings from the deployment files for a cleaner setup

## 2024-12 — SEO and AI visibility improvements

### Added

- **Your site is now easier to find** — improved search engine optimisation and accessibility across all pages, including better page titles, descriptions, and structured data
- **Pre-rendered marketing pages** — the home, pricing, and other public pages now load faster and are more visible to search engines and AI crawlers
- **llms.txt discovery** — added sitemap entries and standard discovery mechanisms so AI systems can find your llms.txt file automatically
- **Startup and public sector validation** — generation for startups and public sector organisations now includes tailored quality checks

### Fixed

- **Contact information handling** — fixed an issue where missing contact details could cause generation to fail
- **Better compatibility with modern browsers** — resolved technical issues with how the site loads in different environments

## 2024-11 — Authentication, payments, and the web platform

### Added

- **Passwordless sign-in** — you can now log in with just your email address via a magic link, no password needed
- **Stripe payments** — pay securely for one-time paid generations (£9) or subscribe to monitoring (£9/month)
- **User dashboard** — view your generations, manage subscriptions, and track monitoring history after signing in
- **Paid jobs linked to your account** — when you sign in, all your paid generations are automatically associated with your account
- **Subscriptions linked to your account** — monitoring subscriptions are now tied to your user profile for easy management
- **Sector and goal selection** — choose your specific sector and primary goal during generation for more tailored results
- **Dismissable assessment findings** — you can now dismiss individual assessment recommendations that aren't relevant to your organisation
- **Visual progress indicator** — see real-time progress as your llms.txt is being generated, including which pages are being crawled

### Changed

- **Updated generation page** — the generation form has been redesigned with clearer options and a smoother payment flow
- **Simplified deployment** — the platform now runs on a single server setup, making it easier and cheaper to host

### Fixed

- **CORS and routing issues** — resolved problems that could prevent the web app from communicating with the backend
- **Web application path handling** — fixed an issue where the frontend wasn't being served correctly

## 2024-10 — Monorepo, assessment, and enrichment

### Added

- **Quality assessment** — every paid generation now includes a detailed assessment with scores, grades, and actionable recommendations
- **Charity Commission enrichment** — paid generations for charities automatically pull in official data including registration details, financial information, and trustee names
- **360Giving enrichment for funders** — funder profiles are enriched with grants data including amounts, geographic distribution, and trends
- **Monorepo structure** — the project is now organised into separate packages (core library, CLI, API, and web frontend) that share the same underlying logic

### Fixed

- **Charity Commission data extraction** — fixed several issues with how charity names, numbers, and other details were being read from the official register
- **Enrichment data now included in output** — enrichment information is properly integrated into the generated llms.txt file

## 2024-09 — Initial release

### Added

- **llms.txt generation** — automatically crawl any website and generate a standards-compliant llms.txt file
- **Four organisation templates** — specialised templates for charities, funders, public sector bodies, and startups
- **Smart web crawling** — respects robots.txt, follows sitemaps, and intelligently discovers the most important pages
- **JavaScript support** — can render and extract content from modern JavaScript-heavy websites
- **AI-powered analysis** — uses Claude to understand your organisation's mission, services, and impact
- **Command-line tool** — open-source CLI for generating, assessing, and validating llms.txt files
- **Free and paid tiers** — basic generation is free (up to 10 per day), with enrichment and assessment available for a one-time payment
