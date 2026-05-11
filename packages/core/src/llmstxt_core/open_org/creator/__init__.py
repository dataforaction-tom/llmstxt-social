"""Open Org strategy / idea chat creator.

Drives a conversational flow that produces validated Open Org markdown for a
new strategy or idea. Implemented as a thin orchestration layer over
``CachedAnthropic.stream`` plus prompts persisted in ``prompts/``.
"""
