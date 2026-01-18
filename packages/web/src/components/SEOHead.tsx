import helmetAsync from 'react-helmet-async';
const { Helmet } = helmetAsync;

interface SEOHeadProps {
  title?: string;
  description?: string;
  canonicalPath?: string;
  ogType?: 'website' | 'article';
  noIndex?: boolean;
}

const BASE_URL = 'https://llmstxt.social';
const DEFAULT_TITLE = 'llms.txt Generator - AI-Ready Documentation for Social Sector';
const DEFAULT_DESCRIPTION = 'Generate spec-compliant llms.txt files for charities, foundations, public sector organisations, and social enterprises. Make your organisation AI-discoverable.';

export default function SEOHead({
  title,
  description = DEFAULT_DESCRIPTION,
  canonicalPath = '',
  ogType = 'website',
  noIndex = false,
}: SEOHeadProps) {
  const fullTitle = title ? `${title} | llms.txt Generator` : DEFAULT_TITLE;
  const canonicalUrl = `${BASE_URL}${canonicalPath}`;

  return (
    <Helmet>
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      <link rel="canonical" href={canonicalUrl} />

      {/* Open Graph */}
      <meta property="og:type" content={ogType} />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:url" content={canonicalUrl} />
      <meta property="og:site_name" content="llms.txt Generator" />

      {/* Twitter Card */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />

      {/* Robots */}
      {noIndex && <meta name="robots" content="noindex, nofollow" />}
    </Helmet>
  );
}
