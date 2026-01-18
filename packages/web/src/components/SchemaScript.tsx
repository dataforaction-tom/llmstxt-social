import helmetAsync from 'react-helmet-async';
const { Helmet } = helmetAsync;

interface SchemaScriptProps {
  schema: object;
}

export default function SchemaScript({ schema }: SchemaScriptProps) {
  return (
    <Helmet>
      <script type="application/ld+json">
        {JSON.stringify(schema)}
      </script>
    </Helmet>
  );
}

// Common schema generators

export function generateOrganizationSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'llms.txt Generator',
    url: 'https://llmstxt.social',
    description: 'AI-ready documentation generator for charities, foundations, public sector organisations, and social enterprises.',
    sameAs: [],
  };
}

export function generateWebSiteSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'llms.txt Generator',
    url: 'https://llmstxt.social',
    description: 'Generate spec-compliant llms.txt files for the social sector',
    potentialAction: {
      '@type': 'SearchAction',
      target: 'https://llmstxt.social/generate?url={search_term_string}',
      'query-input': 'required name=search_term_string',
    },
  };
}

export function generateFAQSchema(faqs: Array<{ question: string; answer: string }>) {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqs.map((faq) => ({
      '@type': 'Question',
      name: faq.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: faq.answer,
      },
    })),
  };
}

export function generateHowToSchema(
  title: string,
  description: string,
  steps: Array<{ name: string; text: string }>
) {
  return {
    '@context': 'https://schema.org',
    '@type': 'HowTo',
    name: title,
    description: description,
    step: steps.map((step, index) => ({
      '@type': 'HowToStep',
      position: index + 1,
      name: step.name,
      text: step.text,
    })),
  };
}

export function generateProductSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: 'llms.txt Generator',
    description: 'AI-ready documentation generator for the social sector',
    offers: [
      {
        '@type': 'Offer',
        name: 'Free Tier',
        price: '0',
        priceCurrency: 'GBP',
        description: 'Basic llms.txt generation with 10/day limit',
      },
      {
        '@type': 'Offer',
        name: 'Paid Tier',
        price: '9',
        priceCurrency: 'GBP',
        description: 'Full generation with AI assessment and data enrichment',
      },
      {
        '@type': 'Offer',
        name: 'Subscription',
        price: '9',
        priceCurrency: 'GBP',
        priceSpecification: {
          '@type': 'UnitPriceSpecification',
          billingDuration: 'P1M',
        },
        description: 'Automated monthly monitoring with change detection',
      },
    ],
  };
}

export function generateBreadcrumbSchema(items: Array<{ name: string; url: string }>) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: item.url,
    })),
  };
}
