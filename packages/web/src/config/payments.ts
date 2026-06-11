/**
 * One-time payments kill switch — mirror of the API's PAYMENTS_ENABLED.
 * When off, the tier selector and payment flow are hidden and every
 * generation goes through the free endpoint, which the API upgrades to
 * the full pipeline (enrichment + assessment). Monitoring subscriptions
 * are not affected by this flag.
 */
export function paymentsEnabled(): boolean {
  return import.meta.env.VITE_PAYMENTS_ENABLED === 'true';
}
