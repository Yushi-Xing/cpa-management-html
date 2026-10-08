import { describe, expect, spyOn, test } from 'bun:test';
import { readFileSync } from 'node:fs';
import { apiClient } from '@/services/api/client';
import { normalizeZedQuota, quotaPlanLabel, quotaRemainingPercent, zedQuotaApi } from '@/services/api/zedQuota';

describe('Zed quota on the existing credential card', () => {
  test('keeps undisclosed limits unknown and preserves zero remaining', () => {
    expect(normalizeZedQuota({ subscription: { plan: 'zed_student' }, summary: [{ key: 'used', unit: 'USD', value: 0 }] }))
      .toEqual({ plan: 'zed_student', used: 0, limit: null, remaining: null });
    expect(normalizeZedQuota({ summary: [{ key: 'remaining', unit: 'USD', value: 0 }] }).remaining).toBe(0);
    expect(normalizeZedQuota({ subscription: { plan: 'unknown' }, summary: [{ key: 'used', value: -1 }, { key: 'limit', value: '100' }] }))
      .toEqual({ plan: null, used: null, limit: null, remaining: null });
  });
  test('never interprets legacy request counts as Token Spend', () => {
    expect(normalizeZedQuota({ summary: [{ key: 'used', unit: 'requests', value: 0 }, { key: 'limit', unit: 'requests', value: 0 }] }).used).toBeNull();
  });
  test('uses honest bounded remaining percentages and compact known plan labels', () => {
    expect(quotaRemainingPercent({ plan: null, used: .69, limit: 10, remaining: 9.31 })).toBeCloseTo(93.1);
    for (const limit of [0, null, Infinity]) expect(quotaRemainingPercent({ plan: null, used: 0, limit, remaining: 0 })).toBeNull();
    expect(quotaRemainingPercent({ plan: null, used: 10, limit: 10, remaining: 0 })).toBe(0);
    expect(quotaRemainingPercent({ plan: null, used: 0, limit: 10, remaining: 20 })).toBe(100);
    expect(quotaPlanLabel('token_based_zed_student')).toBe('Student');
    expect(quotaPlanLabel('unknown-future-plan')).toBe('unknown-future-plan');
  });
  test('sends only the credential index through the native quota API', async () => {
    const post = spyOn(apiClient, 'postPluginQuota').mockResolvedValue({ subscription: { plan: 'pro' }, summary: [] });
    const signal = new AbortController().signal;
    try {
      await zedQuotaApi.fetch('fixture-index', { signal });
      expect(post).toHaveBeenCalledWith('zed', 'fixture-index', { signal });
      await expect(zedQuotaApi.fetch('', { signal })).rejects.toThrow();
    } finally { post.mockRestore(); }
  });
  test('uses v8 quota paths, including proxy prefixes, and guards connection changes', async () => {
    const post = spyOn(apiClient, 'post').mockResolvedValue({});
    try {
      apiClient.setConfig({ apiBase: 'https://fixture.example/proxy', managementKey: 'fixture' });
      await apiClient.postPluginQuota('zed', 'index');
      expect(post).toHaveBeenCalledWith('/plugins/zed/quota', { auth_index: 'index' }, expect.objectContaining({ pluginConnectionRevision: expect.any(Number) }));
      await expect(apiClient.postPluginQuota('../other', 'index')).rejects.toThrow();
    } finally { post.mockRestore(); }
    let dispatched = false;
    const pending = apiClient.postPluginQuota('zed', 'index', {
      adapter: async () => { dispatched = true; throw new Error('must not dispatch'); },
    });
    apiClient.setConfig({ apiBase: 'https://other.example', managementKey: 'new-fixture' });
    await expect(pending).rejects.toHaveProperty('code', 'ERR_CANCELED');
    expect(dispatched).toBe(false);
    apiClient.setConfig({ apiBase: '', managementKey: '' });
  });
  test('keeps quotas inside Zed cards and makes refresh an explicit user action', () => {
    const card = readFileSync(new URL('../src/features/authFiles/components/AuthFileCard.tsx', import.meta.url), 'utf8');
    const quota = readFileSync(new URL('../src/features/authFiles/components/ZedAuthFileQuota.tsx', import.meta.url), 'utf8');
    expect(card).toContain("providerKey === 'zed' && !isRuntimeOnly");
    expect(quota).toContain('pending.current?.abort()');
    expect(quota).toContain('onClick={() => void refresh()}');
    expect(quota).not.toContain('setInterval');
    expect(quota).not.toContain('localStorage');
  });
});
