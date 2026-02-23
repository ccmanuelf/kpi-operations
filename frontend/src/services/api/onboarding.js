/**
 * Onboarding API Service
 *
 * Provides access to the onboarding status endpoint for checking
 * which getting-started steps have been completed for a client.
 */
import api from './client'

/**
 * Fetch onboarding step completion status for the given client.
 *
 * @param {Object} [params] - Query parameters
 * @param {string} [params.client_id] - Client ID to check (optional for operators)
 * @returns {Promise<import('axios').AxiosResponse>} Response with steps, completed_count, total_steps, all_complete
 */
export function getOnboardingStatus(params = {}) {
  return api.get('/onboarding/status', { params })
}
