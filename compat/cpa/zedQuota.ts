import type { AxiosRequestConfig } from 'axios';
import { apiClient } from '@/services/api/client';

export interface ZedQuota {
  plan: string | null;
  used: number | null;
  limit: number | null;
  remaining: number | null;
}

const record = (value: unknown): Record<string, unknown> | null =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;

export function normalizeZedQuota(response: unknown): ZedQuota {
  const root = record(response);
  const plan = record(root?.subscription)?.plan;
  const quota: ZedQuota = {
    plan: typeof plan === 'string' && plan && plan !== 'unknown' ? plan : null,
    used: null,
    limit: null,
    remaining: null,
  };
  if (Array.isArray(root?.summary)) {
    for (const value of root.summary) {
      const item = record(value);
      if (
        item && (item.key === 'used' || item.key === 'limit' || item.key === 'remaining') &&
        item.unit === 'USD' && typeof item.value === 'number' && Number.isFinite(item.value) && item.value >= 0
      ) {
        quota[item.key] = item.value;
      }
    }
  }
  return quota;
}

export function quotaRemainingPercent(quota: ZedQuota | null): number | null {
  if (!quota || quota.limit == null || quota.remaining == null || !Number.isFinite(quota.limit) ||
      !Number.isFinite(quota.remaining) || quota.limit <= 0 || quota.remaining < 0) return null;
  return Math.min(100, Math.max(0, quota.remaining / quota.limit * 100));
}

export function quotaPlanLabel(plan: string | null): string | null {
  const labels: Record<string, string> = {
    token_based_zed_student: 'Student', token_based_zed_pro: 'Pro',
    token_based_zed_free: 'Free', zed_student: 'Student', zed_pro: 'Pro',
  };
  return plan ? labels[plan] ?? plan : null;
}

export const zedQuotaApi = {
  session: (authIndex: string, action: 'status' | 'save' | 'remove', cookie: string, signal: AbortSignal) =>
    apiClient.postPlugin<{ configured: boolean }>('/plugins/zed/billing/session',
      { auth_index: authIndex, action, ...(action === 'save' ? { cookie } : {}) }, { signal }),
  fetch: async (authIndex: string, config?: AxiosRequestConfig): Promise<ZedQuota> => {
    if (!authIndex.trim()) throw new Error('Missing credential index');
    // Native quota is a v8 API, unlike Zed's declared custom callback route.
    const response = await apiClient.postPluginQuota('zed', authIndex, config);
    return normalizeZedQuota(response);
  },
};
