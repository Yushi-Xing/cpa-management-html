import { describe, expect, spyOn, test } from 'bun:test';
import { apiClient } from '@/services/api/client';
import { oauthApi } from '@/services/api/oauth';
import { validateZedCallback } from '@/pages/zedCallback';
import { existsSync, readFileSync } from 'node:fs';

const state = 'a'.repeat(48);
const callback = 'http://127.0.0.1:47831/?user_id=123&access_token=encrypted-fixture%3D%3D';

describe('Zed plugin callback on the existing OAuth card', () => {
  test('uses the attempt state because Zed does not return OAuth code or state', async () => {
    expect(validateZedCallback(callback, state)).toBe(true);
    const post = spyOn(apiClient, 'postPlugin').mockResolvedValue({ status: 'ok' });
    const signal = new AbortController().signal;
    try {
      await oauthApi.submitZedCallback(callback, state, signal);
      expect(post).toHaveBeenCalledWith('/plugins/zed/login/callback', {
        state, redirect_url: callback,
      }, { signal });
    } finally { post.mockRestore(); }
  });

  test('preserves plugin extension paths and reverse proxy prefixes on the current host', async () => {
    const post = spyOn(apiClient, 'post').mockResolvedValue({ status: 'ok' });
    try {
      for (const root of ['https://cpa.example', 'https://cpa.example/proxy']) {
        apiClient.setConfig({ apiBase: root, managementKey: 'fixture' });
        await oauthApi.submitZedCallback(callback, state);
        expect(post).toHaveBeenLastCalledWith(
          root + '/v0/management/plugins/zed/login/callback',
          { state, redirect_url: callback }, expect.objectContaining({ pluginConnectionRevision: expect.any(Number) })
        );
      }
      await expect(apiClient.postPlugin('https://other.example', {})).rejects.toThrow();
    } finally { post.mockRestore(); apiClient.setConfig({ apiBase: '', managementKey: '' }); }
  });

  test('never sends a changed connection key to a previous server', async () => {
    apiClient.setConfig({ apiBase: 'https://old.example', managementKey: 'old-fixture' });
    let dispatched = false;
    const request = apiClient.postPlugin('/plugins/zed/login/callback', {}, {
      adapter: async () => { dispatched = true; throw new Error('must not dispatch'); },
    });
    apiClient.setConfig({ apiBase: 'https://new.example', managementKey: 'new-fixture' });
    await expect(request).rejects.toHaveProperty('code', 'ERR_CANCELED');
    expect(dispatched).toBe(false);
    apiClient.setConfig({ apiBase: '', managementKey: '' });
  });

  test('rejects unrelated, incomplete and duplicate callbacks', () => {
    for (const bad of ['', 'code=fixture', callback.replace('127.0.0.1', 'example.com'),
      callback.replace('http:', 'https:'), callback + '&user_id=other', callback + '#fragment',
      callback.replace('127.0.0.1', 'secret@127.0.0.1')]) {
      expect(validateZedCallback(bad, state)).toBe(false);
    }
    expect(validateZedCallback(callback)).toBe(false);
    expect(validateZedCallback(callback, 'expired')).toBe(false);
  });

  test('keeps the existing shared card, cancellation, polling and credential notification', () => {
    const featurePath = new URL('../src/features/oauth/hooks/useOAuthFlows.ts', import.meta.url);
    const featureLayout = existsSync(featurePath);
    const page = readFileSync(featureLayout ? featurePath : new URL('../src/pages/OAuthPage.tsx', import.meta.url), 'utf8');
    const providers = featureLayout
      ? readFileSync(new URL('../src/features/oauth/providers.ts', import.meta.url), 'utf8')
      : page;
    expect(providers).toContain("provider.kind === 'plugin' || CALLBACK_SUPPORTED.has(provider.id)");
    expect(page).toContain('await oauthApi.submitZedCallback(redirectUrl, states[provider]!.state!, attempt.signal)');
    expect(page).toContain('oauthApi.getAuthStatus(state, attempt.signal)');
    expect(page).toContain('notifyAuthFilesChanged()');
    expect(page).not.toContain('/resource/plugins/zed/login');
  });
});
