import { Link } from 'react-router-dom';
import { FileText, Zap, CheckCircle, TrendingUp, ArrowRight, Bot, Globe, Search, MessageSquare } from 'lucide-react';
import SEOHead from '../components/SEOHead';
import SchemaScript, { generateOrganizationSchema, generateWebSiteSchema } from '../components/SchemaScript';

export default function HomePage() {
  return (
    <>
      <SEOHead
        canonicalPath="/"
        description="Generate spec-compliant llms.txt files for charities, foundations, public sector organisations, and social enterprises. Make your organisation AI-discoverable with free or paid assessment options."
      />
      <SchemaScript schema={generateOrganizationSchema()} />
      <SchemaScript schema={generateWebSiteSchema()} />
      <div className="bg-gradient-to-b from-primary-50 to-white">
      {/* Hero Section */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center">
          <h1 className="text-5xl font-bold text-gray-900 mb-6">
            AI-Ready Documentation for the Social Sector
          </h1>
          <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto">
            Generate llms.txt files for your charity, foundation, or social enterprise.
            Make your organization AI-discoverable with spec-compliant documentation.
          </p>
          <div className="flex gap-4 justify-center">
            <Link to="/generate" className="btn btn-primary text-lg px-8 py-3">
              Generate Free <ArrowRight className="inline-block ml-2 w-5 h-5" />
            </Link>
            <Link to="/pricing" className="btn btn-outline text-lg px-8 py-3">
              View Pricing
            </Link>
          </div>
        </div>

        {/* Demo Preview */}
        <div className="mt-16 max-w-4xl mx-auto">
          <div className="bg-gray-900 rounded-xl shadow-2xl overflow-hidden">
            <div className="bg-gray-800 px-4 py-2 flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500"></div>
              <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
              <div className="w-3 h-3 rounded-full bg-green-500"></div>
              <span className="ml-4 text-gray-400 text-sm">llms.txt</span>
            </div>
            <div className="p-6 font-mono text-sm text-gray-300">
              <pre className="whitespace-pre-wrap">
{`# Example Charity

> Helping vulnerable communities thrive

UK Registered Charity #1234567. Supporting homeless
individuals across London since 1995.

## About

- [About Us](url): Our mission and history
- [Our Team](url): Meet the people behind our work

## Services

- Emergency Accommodation: Safe shelter for rough sleepers
- Skills Training: Employment support and education
- Mental Health Support: Counseling and therapy services

## For Funders

- Registration: 1234567
- Geography: Greater London
- Themes: homelessness, mental health, employment
- Contact: grants@example-charity.org.uk`}
              </pre>
            </div>
          </div>
        </div>
      </div>

      {/* What is llms.txt Section */}
      <div className="bg-white py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">
              What is an llms.txt file?
            </h2>
            <p className="text-lg text-gray-600 max-w-3xl mx-auto">
              An llms.txt file is a standardized way to make your organization's information
              easily accessible to AI systems like ChatGPT, Claude, and other large language models.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-12 items-center mb-16">
            <div>
              <h3 className="text-2xl font-bold text-gray-900 mb-4">Think of it as SEO for AI</h3>
              <p className="text-gray-600 mb-6">
                Just like robots.txt tells search engines how to crawl your site, <strong>llms.txt tells AI assistants
                what your organization does</strong>. When someone asks an AI "What charities support homeless people in London?",
                a well-crafted llms.txt helps your organization appear in the response.
              </p>
              <ul className="space-y-3">
                <li className="flex items-start gap-3">
                  <Bot className="w-5 h-5 text-primary-600 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-700">AI assistants can accurately describe your services</span>
                </li>
                <li className="flex items-start gap-3">
                  <Search className="w-5 h-5 text-primary-600 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-700">Your organization gets recommended to relevant queries</span>
                </li>
                <li className="flex items-start gap-3">
                  <MessageSquare className="w-5 h-5 text-primary-600 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-700">Funders and partners can discover you through AI tools</span>
                </li>
              </ul>
            </div>
            <div className="bg-gray-50 rounded-xl p-6">
              <h4 className="font-semibold text-gray-900 mb-4">How to use your llms.txt file</h4>
              <ol className="space-y-4 text-gray-700">
                <li className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-primary-600 text-white rounded-full flex items-center justify-center text-sm font-medium">1</span>
                  <div>
                    <strong>Generate</strong> your llms.txt using our tool (free or enhanced)
                  </div>
                </li>
                <li className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-primary-600 text-white rounded-full flex items-center justify-center text-sm font-medium">2</span>
                  <div>
                    <strong>Upload</strong> the file to your website's root directory (e.g., yoursite.org/llms.txt)
                  </div>
                </li>
                <li className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-primary-600 text-white rounded-full flex items-center justify-center text-sm font-medium">3</span>
                  <div>
                    <strong>Done!</strong> AI systems will automatically discover and use your file
                  </div>
                </li>
              </ol>
              <div className="mt-6 p-4 bg-primary-50 rounded-lg">
                <p className="text-sm text-primary-800">
                  <strong>Pro tip:</strong> Use our monitoring subscription to automatically regenerate
                  your llms.txt when your website content changes, keeping your AI presence up to date.
                </p>
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-r from-gray-50 to-gray-100 rounded-2xl p-8">
            <h3 className="text-xl font-bold text-gray-900 mb-4 text-center">The llms.txt Specification</h3>
            <p className="text-gray-600 text-center max-w-2xl mx-auto mb-6">
              llms.txt follows an open specification designed for AI readability. It uses simple Markdown
              formatting with standardized sections that AI systems understand.
            </p>
            <div className="grid md:grid-cols-3 gap-6">
              <div className="bg-white rounded-lg p-5 shadow-sm">
                <Globe className="w-8 h-8 text-primary-600 mb-3" />
                <h4 className="font-semibold text-gray-900 mb-2">Universal Format</h4>
                <p className="text-sm text-gray-600">
                  Works with all major AI systems including ChatGPT, Claude, Gemini, and more
                </p>
              </div>
              <div className="bg-white rounded-lg p-5 shadow-sm">
                <FileText className="w-8 h-8 text-primary-600 mb-3" />
                <h4 className="font-semibold text-gray-900 mb-2">Simple Structure</h4>
                <p className="text-sm text-gray-600">
                  Markdown-based format with clear sections for organization details, services, and contact info
                </p>
              </div>
              <div className="bg-white rounded-lg p-5 shadow-sm">
                <CheckCircle className="w-8 h-8 text-primary-600 mb-3" />
                <h4 className="font-semibold text-gray-900 mb-2">Open Standard</h4>
                <p className="text-sm text-gray-600">
                  Based on the <a href="https://llmstxt.org" target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">llmstxt.org</a> specification,
                  adopted by organizations worldwide
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
          Why use our generator?
        </h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          <FeatureCard
            icon={<FileText className="w-10 h-10 text-primary-600" />}
            title="AI-Discoverable"
            description="Make your organization easy for AI assistants to understand and recommend"
          />
          <FeatureCard
            icon={<Zap className="w-10 h-10 text-primary-600" />}
            title="Spec Compliant"
            description="Follows the official llms.txt specification for maximum compatibility"
          />
          <FeatureCard
            icon={<CheckCircle className="w-10 h-10 text-primary-600" />}
            title="Quality Assessment"
            description="Get detailed feedback on completeness and quality (paid tier)"
          />
          <FeatureCard
            icon={<TrendingUp className="w-10 h-10 text-primary-600" />}
            title="Data Enrichment"
            description="Automatic integration with Charity Commission and 360Giving data"
          />
        </div>
      </div>

      {/* Templates Section */}
      <div className="bg-gray-50 py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
            Templates for Every Organization
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            <TemplateCard
              title="Charity"
              description="For UK charities and VCSE organizations"
              features={['Services', 'Impact metrics', 'Beneficiary info']}
            />
            <TemplateCard
              title="Funder"
              description="For foundations and grant makers"
              features={['What we fund', 'How to apply', 'Eligibility']}
            />
            <TemplateCard
              title="Public Sector"
              description="For councils and NHS trusts"
              features={['Services by category', 'Eligibility', 'Contact']}
            />
            <TemplateCard
              title="Startup"
              description="For social enterprises"
              features={['Product info', 'Customers', 'Investors']}
            />
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="bg-primary-600 rounded-2xl p-12 text-center text-white">
          <h2 className="text-3xl font-bold mb-4">
            Ready to make your organization AI-ready?
          </h2>
          <p className="text-xl mb-8 text-primary-100">
            Start with a free generation, or upgrade for full assessment and enrichment.
          </p>
          <Link to="/generate" className="btn bg-white text-primary-600 hover:bg-gray-100 text-lg px-8 py-3">
            Get Started Free
          </Link>
        </div>
      </div>
      </div>
    </>
  );
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <article className="text-center">
      <div className="flex justify-center mb-4" aria-hidden="true">{icon}</div>
      <h3 className="text-xl font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </article>
  );
}

function TemplateCard({ title, description, features }: { title: string; description: string; features: string[] }) {
  return (
    <article className="card">
      <h3 className="text-xl font-bold text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-600 mb-4">{description}</p>
      <ul className="space-y-2" aria-label={`${title} template features`}>
        {features.map((feature, idx) => (
          <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
            <CheckCircle className="w-4 h-4 text-primary-600 mt-0.5 flex-shrink-0" aria-hidden="true" />
            <span>{feature}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}
