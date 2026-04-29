import api from './client'

export interface OnboardingStatusParams {
  client_id?: string
}

export function getOnboardingStatus(params: OnboardingStatusParams = {}) {
  return api.get('/onboarding/status', { params })
}
