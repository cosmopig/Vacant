export const BUDGET_RE = /\b(?:budget|limit|maximum|max|at most|no more than|up to)\b[^.\n]{0,40}?\b(\d{1,4})\s+(?:model\s+|agent\s+|llm\s+)?(?:turns|steps|iterations)\b/i;
