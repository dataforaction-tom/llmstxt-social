import { Link } from 'react-router-dom';
import { Check } from 'lucide-react';

export default function PricingPage() {
  return (
    <div className="bg-gray-50 py-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Simple, Transparent Pricing
          </h1>
          <p className="text-xl text-gray-600">
            Choose the tier that works for your organization
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {/* Free Tier */}
          <PricingCard
            name="Free"
            price="£0"
            period=""
            description="Try it out with basic generation"
            features={[
              '10 generations per day',
              'All 4 templates',
              'Basic llms.txt generation',
              'No enrichment data',
              'No quality assessment',
              'Results expire after 7 days',
            ]}
            cta="Get Started Free"
            ctaLink="/generate"
            highlighted={false}
          />

          {/* Paid Tier */}
          <PricingCard
            name="Paid"
            price="£29"
            period="one-time"
            description="Full generation with assessment"
            features={[
              'Unlimited generations',
              'All 4 templates',
              'Charity Commission enrichment',
              '360Giving data for funders',
              'Full quality assessment',
              'AI-powered analysis',
              'Website gap detection',
              'JSON + Markdown reports',
              'Valid for 30 days',
            ]}
            cta="Generate with Assessment"
            ctaLink="/generate"
            highlighted={true}
          />

          {/* Subscription Tier */}
          <PricingCard
            name="Subscription"
            price="£9"
            period="per month"
            description="Automated monitoring and updates"
            features={[
              'All paid tier features',
              'Weekly or monthly monitoring',
              'Auto-regeneration on changes',
              'Email notifications',
              'Change history tracking',
              'Comparison reports',
              'Dashboard access',
              'Cancel anytime',
            ]}
            cta="Coming Soon"
            ctaLink="#"
            highlighted={false}
            comingSoon={true}
          />
        </div>

        {/* FAQs */}
        <div className="mt-20 max-w-3xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
            Frequently Asked Questions
          </h2>
          <div className="space-y-6">
            <FAQItem
              question="What's included in the free tier?"
              answer="The free tier gives you basic llms.txt generation for any UK social sector organization. You can generate up to 10 files per day, but they won't include quality assessment or enrichment data from external sources."
            />
            <FAQItem
              question="What is enrichment data?"
              answer="Enrichment data includes official information from the Charity Commission (for charities) and 360Giving (for funders). This adds verified details about registration numbers, financial data, and grant history to your llms.txt file."
            />
            <FAQItem
              question="How does the quality assessment work?"
              answer="Our AI-powered assessment analyzes your llms.txt file for completeness, clarity, and compliance with the specification. You'll receive a detailed report with scores, findings, and actionable recommendations to improve your file."
            />
            <FAQItem
              question="What's the difference between paid and subscription?"
              answer="The paid tier (£29) is a one-time payment for a single generation with full assessment. The subscription tier (£9/month) includes automatic monitoring - we'll regenerate your llms.txt whenever your website changes and notify you of updates."
            />
            <FAQItem
              question="Can I use this for multiple organizations?"
              answer="Yes! Each generation is per URL, so you can generate llms.txt files for as many organizations as you need. The free tier has a daily limit, while paid and subscription tiers are unlimited."
            />
            <FAQItem
              question="Do you support organizations outside the UK?"
              answer="Currently, we specialize in UK social sector organizations (charities, funders, public sector). Our enrichment integrations are UK-specific (Charity Commission, 360Giving). However, the basic generation works for any organization worldwide."
            />
          </div>
        </div>
      </div>
    </div>
  );
}

interface PricingCardProps {
  name: string;
  price: string;
  period: string;
  description: string;
  features: string[];
  cta: string;
  ctaLink: string;
  highlighted: boolean;
  comingSoon?: boolean;
}

function PricingCard({
  name,
  price,
  period,
  description,
  features,
  cta,
  ctaLink,
  highlighted,
  comingSoon,
}: PricingCardProps) {
  return (
    <div
      className={`bg-white rounded-2xl shadow-lg overflow-hidden ${
        highlighted ? 'ring-2 ring-primary-600 scale-105' : ''
      }`}
    >
      {highlighted && (
        <div className="bg-primary-600 text-white text-center py-2 text-sm font-semibold">
          Most Popular
        </div>
      )}

      <div className="p-8">
        <h3 className="text-2xl font-bold text-gray-900 mb-2">{name}</h3>
        <p className="text-gray-600 mb-6">{description}</p>

        <div className="mb-6">
          <span className="text-4xl font-bold text-gray-900">{price}</span>
          {period && <span className="text-gray-600 ml-2">/ {period}</span>}
        </div>

        <ul className="space-y-3 mb-8">
          {features.map((feature, idx) => (
            <li key={idx} className="flex items-start gap-3">
              <Check className="w-5 h-5 text-primary-600 flex-shrink-0 mt-0.5" />
              <span className="text-gray-700">{feature}</span>
            </li>
          ))}
        </ul>

        {comingSoon ? (
          <button disabled className="btn btn-secondary w-full opacity-50 cursor-not-allowed">
            {cta}
          </button>
        ) : (
          <Link to={ctaLink} className={`btn ${highlighted ? 'btn-primary' : 'btn-outline'} w-full block text-center`}>
            {cta}
          </Link>
        )}
      </div>
    </div>
  );
}

function FAQItem({ question, answer }: { question: string; answer: string }) {
  return (
    <div className="bg-white rounded-lg p-6 shadow-sm">
      <h3 className="text-lg font-semibold text-gray-900 mb-2">{question}</h3>
      <p className="text-gray-600">{answer}</p>
    </div>
  );
}
