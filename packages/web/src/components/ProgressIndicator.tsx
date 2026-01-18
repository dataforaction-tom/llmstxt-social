import { Globe, FileText, Sparkles, Brain, FileCode, ClipboardCheck, CheckCircle2, XCircle } from 'lucide-react';
import type { ProgressStage, Tier } from '../types';

interface ProgressIndicatorProps {
  stage?: ProgressStage;
  detail?: string;
  pagesCrawled?: number;
  totalPages?: number;
  tier: Tier;
}

interface StageConfig {
  id: ProgressStage;
  label: string;
  icon: React.ReactNode;
  description: string;
}

const FREE_STAGES: StageConfig[] = [
  { id: 'crawling', label: 'Crawling', icon: <Globe className="w-5 h-5" aria-hidden="true" />, description: 'Discovering website pages' },
  { id: 'extracting', label: 'Extracting', icon: <FileText className="w-5 h-5" aria-hidden="true" />, description: 'Reading page content' },
  { id: 'analyzing', label: 'Analyzing', icon: <Brain className="w-5 h-5" aria-hidden="true" />, description: 'AI analysis with Claude' },
  { id: 'generating', label: 'Generating', icon: <FileCode className="w-5 h-5" aria-hidden="true" />, description: 'Creating llms.txt' },
];

const PAID_STAGES: StageConfig[] = [
  { id: 'crawling', label: 'Crawling', icon: <Globe className="w-5 h-5" aria-hidden="true" />, description: 'Discovering website pages' },
  { id: 'extracting', label: 'Extracting', icon: <FileText className="w-5 h-5" aria-hidden="true" />, description: 'Reading page content' },
  { id: 'enriching', label: 'Enriching', icon: <Sparkles className="w-5 h-5" aria-hidden="true" />, description: 'Fetching additional data' },
  { id: 'analyzing', label: 'Analyzing', icon: <Brain className="w-5 h-5" aria-hidden="true" />, description: 'AI analysis with Claude' },
  { id: 'generating', label: 'Generating', icon: <FileCode className="w-5 h-5" aria-hidden="true" />, description: 'Creating llms.txt' },
  { id: 'assessing', label: 'Assessing', icon: <ClipboardCheck className="w-5 h-5" aria-hidden="true" />, description: 'Quality assessment' },
];

function getStageIndex(stages: StageConfig[], currentStage?: ProgressStage): number {
  if (!currentStage) return -1;
  return stages.findIndex(s => s.id === currentStage);
}

export default function ProgressIndicator({
  stage,
  detail,
  pagesCrawled,
  totalPages,
  tier
}: ProgressIndicatorProps) {
  const stages = tier === 'paid' ? PAID_STAGES : FREE_STAGES;
  const currentIndex = getStageIndex(stages, stage);
  const isFailed = stage === 'failed';
  const isCompleted = stage === 'completed';

  return (
    <div className="space-y-6" role="region" aria-label="Generation progress">
      {/* Screen reader announcement for stage changes */}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {isCompleted && 'Generation complete. Your llms.txt file is ready to download.'}
        {isFailed && 'Generation failed. Please try again.'}
        {!isCompleted && !isFailed && stages[currentIndex]?.description}
      </div>

      {/* Stage progress bar */}
      <div className="relative" aria-hidden="true">
        {/* Background line */}
        <div className="absolute top-5 left-0 right-0 h-0.5 bg-gray-200" />

        {/* Progress line */}
        <div
          className="absolute top-5 left-0 h-0.5 bg-primary-500 transition-all duration-500"
          style={{
            width: isCompleted
              ? '100%'
              : `${Math.max(0, (currentIndex / (stages.length - 1)) * 100)}%`
          }}
        />

        {/* Stage icons */}
        <div className="relative flex justify-between">
          {stages.map((stageConfig, index) => {
            const isPast = currentIndex > index || isCompleted;
            const isCurrent = currentIndex === index && !isCompleted && !isFailed;
            const isFuture = currentIndex < index && !isCompleted;

            return (
              <div key={stageConfig.id} className="flex flex-col items-center">
                <div
                  className={`
                    w-10 h-10 rounded-full flex items-center justify-center
                    transition-all duration-300 relative z-10
                    ${isPast ? 'bg-primary-500 text-white' : ''}
                    ${isCurrent ? 'bg-primary-500 text-white ring-4 ring-primary-200 animate-pulse' : ''}
                    ${isFuture ? 'bg-gray-100 text-gray-400' : ''}
                    ${isFailed && isCurrent ? 'bg-red-500 text-white ring-4 ring-red-200' : ''}
                  `}
                >
                  {isPast && !isCurrent ? (
                    <CheckCircle2 className="w-5 h-5" aria-hidden="true" />
                  ) : isFailed && isCurrent ? (
                    <XCircle className="w-5 h-5" aria-hidden="true" />
                  ) : (
                    stageConfig.icon
                  )}
                </div>
                <span className={`
                  mt-2 text-xs font-medium
                  ${isPast || isCurrent ? 'text-primary-600' : 'text-gray-400'}
                  ${isFailed && isCurrent ? 'text-red-600' : ''}
                `}>
                  {stageConfig.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Current stage details */}
      <div className="bg-gray-50 rounded-lg p-4">
        <div className="flex items-center gap-3">
          {!isCompleted && !isFailed && (
            <div className="relative">
              <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
                {stages[currentIndex]?.icon || <Globe className="w-4 h-4 text-primary-600" aria-hidden="true" />}
              </div>
              <div className="absolute inset-0 rounded-full border-2 border-primary-500 border-t-transparent animate-spin" aria-hidden="true" />
            </div>
          )}
          {isCompleted && (
            <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
              <CheckCircle2 className="w-4 h-4 text-green-600" aria-hidden="true" />
            </div>
          )}
          {isFailed && (
            <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center">
              <XCircle className="w-4 h-4 text-red-600" aria-hidden="true" />
            </div>
          )}
          <div className="flex-1">
            <p className={`font-medium ${isFailed ? 'text-red-700' : 'text-gray-900'}`}>
              {isCompleted ? 'Generation Complete!' :
               isFailed ? 'Generation Failed' :
               stages[currentIndex]?.description || 'Starting...'}
            </p>
            {detail && (
              <p className="text-sm text-gray-600 mt-0.5">{detail}</p>
            )}
          </div>
        </div>

        {/* Pages crawled indicator */}
        {stage === 'crawling' && totalPages && (
          <div className="mt-4">
            <div className="flex justify-between text-xs text-gray-600 mb-1">
              <span>Pages discovered</span>
              <span>{pagesCrawled || 0} / {totalPages} max</span>
            </div>
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary-500 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, ((pagesCrawled || 0) / totalPages) * 100)}%` }}
              />
            </div>
          </div>
        )}

        {/* Extracted pages count */}
        {(stage === 'extracting' || stage === 'analyzing' || stage === 'generating') && pagesCrawled && (
          <div className="mt-3 flex items-center gap-2 text-sm text-gray-600">
            <FileText className="w-4 h-4" aria-hidden="true" />
            <span>Processing {pagesCrawled} pages</span>
          </div>
        )}
      </div>

      {/* Estimated time */}
      {!isCompleted && !isFailed && (
        <p className="text-center text-sm text-gray-600">
          This typically takes 30-60 seconds depending on website size
        </p>
      )}
    </div>
  );
}
