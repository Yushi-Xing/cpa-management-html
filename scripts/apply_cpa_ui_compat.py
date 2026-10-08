"""Adapt the official single-file CPA panel; no public plugin login resource."""
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PIN = 'ee79a794526a30c03748a8864a9ac6589a31833b'
MARKER = "import { validateZedCallback } from './zedCallback';\n"


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Official CPA panel changed; refusing a partial Zed adaptation')
    return text.replace(old, new)


def apply(destination):
    page_path = destination / 'src/pages/OAuthPage.tsx'
    client_path = destination / 'src/services/api/client.ts'
    oauth_path = destination / 'src/services/api/oauth.ts'
    page = page_path.read_text(encoding='utf-8')
    if MARKER in page:
        if "await oauthApi.submitZedCallback" not in page:
            raise ValueError('Incomplete official Zed adaptation')
        print('Official Zed callback adaptation already applied')
        apply_quota(destination)
        return
    client = client_path.read_text(encoding='utf-8')
    oauth = oauth_path.read_text(encoding='utf-8')
    page = MARKER + replace_once(page,
        "    if (provider === 'devin') {\n      const callbackError = validateDevinCallback",
        "    if (provider === 'zed' && !validateZedCallback(callbackInput, states[provider]?.state)) {\n      showNotification(t('auth_login.zed_callback_invalid'), 'warning');\n      return;\n    }\n    if (provider === 'devin') {\n      const callbackError = validateDevinCallback")
    page = replace_once(page,
        '      await oauthApi.submitCallback(provider, redirectUrl, attempt.signal);',
        "      if (provider === 'zed') {\n        await oauthApi.submitZedCallback(redirectUrl, states[provider]!.state!, attempt.signal);\n      } else {\n        await oauthApi.submitCallback(provider, redirectUrl, attempt.signal);\n      }")
    page = replace_once(page,
        "      updateProviderState(provider, { callbackSubmitting: false, callbackStatus: 'success' });",
        "      updateProviderState(provider, {\n        callbackSubmitting: false,\n        callbackStatus: 'success',\n        ...(provider === 'zed' ? { callbackUrl: '' } : {}),\n      });")
    for suffix in ['hint', 'placeholder']:
        old = f"                    ? 'auth_login.xai_callback_{suffix}'\n                    : provider.id === 'devin'"
        new = f"                    ? 'auth_login.xai_callback_{suffix}'\n                    : provider.id === 'zed'\n                      ? 'auth_login.zed_callback_{suffix}'\n                    : provider.id === 'devin'"
        page = replace_once(page, old, new)
    # The original component already renders the shared callback input for plugins.
    # The extension is authenticated by CPA at its declared v0 path; all ordinary
    # OAuth start/status and credential operations continue to use v8.
    client = replace_once(client, 'class ApiClient {', '''interface PluginRequestConfig extends AxiosRequestConfig {
  pluginConnectionRevision?: number;
}

class ApiClient {''')
    client = replace_once(client, '        // 设置 baseURL', '''        const revision = (config as PluginRequestConfig).pluginConnectionRevision;
        if (revision !== undefined && revision !== this.connectionRevision) {
          throw new axios.CanceledError('Plugin connection changed');
        }
        // 设置 baseURL''')
    anchor = '  /**\n   * PUT 请求\n   */'
    method = '''  async postPlugin<T = unknown>(
    path: string,
    data: unknown,
    config?: AxiosRequestConfig
  ): Promise<T> {
    if (!/^\\/plugins\\/[a-z0-9_-]+\\/[a-z0-9_/-]+$/.test(path)) {
      throw new Error('Invalid plugin management path');
    }
    if (!/\\/v8\\/management\\/?$/.test(this.apiBase)) {
      throw new Error('No management connection');
    }
    const base = this.apiBase.replace(/\\/v8\\/management\\/?$/, '/v0/management');
    const scopedConfig: PluginRequestConfig = {
      ...config,
      pluginConnectionRevision: this.connectionRevision,
    };
    return this.post<T>(base + path, data, scopedConfig);
  }

'''
    client = replace_once(client, anchor, method + anchor)
    oauth = replace_once(oauth, '  submitCallback: (provider:', '''  submitZedCallback: (redirectUrl: string, state: string, signal?: AbortSignal) =>
    apiClient.postPlugin<OAuthCallbackResponse>(
      '/plugins/zed/login/callback',
      { state, redirect_url: redirectUrl },
      signal ? { signal } : undefined
    ),

  submitCallback: (provider:''')
    locale_messages = {
        'zh-CN': ['完成 Zed 登录后，复制地址栏中的完整 127.0.0.1 回调链接；即使页面无法打开，也可在这里提交。', 'http://127.0.0.1:端口/?user_id=...&access_token=...', '请粘贴本次 Zed 认证的完整回调链接。'],
        'zh-TW': ['完成 Zed 登入後，複製網址列中的完整 127.0.0.1 回呼連結；即使網頁無法開啟，也可在此提交。', 'http://127.0.0.1:連接埠/?user_id=...&access_token=...', '請貼上本次 Zed 認證的完整回呼連結。'],
        'en': ['After signing in to Zed, paste the complete 127.0.0.1 redirect from the address bar, even if the page cannot open.', 'http://127.0.0.1:port/?user_id=...&access_token=...', 'Paste the complete callback URL for this Zed login attempt.'],
        'ru': ['После входа в Zed вставьте полный адрес перенаправления 127.0.0.1 из адресной строки, даже если страница не открывается.', 'http://127.0.0.1:port/?user_id=...&access_token=...', 'Вставьте полный URL обратного вызова для текущего входа в Zed.'],
    }
    # This upstream SSR test expects translation keys but has no translation
    # provider. Other suites initialize the shared i18next singleton, making its
    # result depend on test order. Give this test its own key-only instance;
    # retain every original assertion and all application translations.
    fixture_path = destination / 'tests/providerModelOptions.test.ts'
    fixture = fixture_path.read_text(encoding='utf-8')
    fixture = replace_once(fixture,
        "import { renderToStaticMarkup } from 'react-dom/server';",
        "import { renderToStaticMarkup } from 'react-dom/server';\nimport { I18nextProvider } from 'react-i18next';\nimport { createInstance } from 'i18next';\n\nconst modelOptionsI18n = createInstance();\nawait modelOptionsI18n.init({ lng: 'cimode' });")
    fixture = replace_once(fixture,
        "      createElement(ModelAdvancedFields, {\n        entry: { name: 'model', thinkingEnabled: enabled },\n        providerBrand: brand,\n        disabled,\n        supportsThinking: true,\n        onUpdate: () => {},\n      })",
        "      createElement(\n        I18nextProvider,\n        { i18n: modelOptionsI18n },\n        createElement(ModelAdvancedFields, {\n          entry: { name: 'model', thinkingEnabled: enabled },\n          providerBrand: brand,\n          disabled,\n          supportsThinking: true,\n          onUpdate: () => {},\n        })\n      )")
    # Validate every anchor and locale before changing any file.
    locales = {}
    for language, messages in locale_messages.items():
        path = destination / f'src/i18n/locales/{language}.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        for suffix, value in zip(['hint', 'placeholder', 'invalid'], messages):
            data['auth_login']['zed_callback_' + suffix] = value
        data['zed_billing'] = {'expired': {'zh-CN': '账单会话过期时，请更新账单 Cookie。', 'zh-TW': '帳單會話過期時，請更新帳單 Cookie。', 'en': 'If the billing session expired, update the billing cookie.', 'ru': 'Если платёжная сессия истекла, обновите cookie.'}[language]}
        locales[path] = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    for path, content in {page_path: page, client_path: client, oauth_path: oauth, fixture_path: fixture, **locales}.items():
        path.write_text(content, encoding='utf-8')
    shutil.copy2(ROOT / 'compat/cpa/zedCallback.ts', destination / 'src/pages/zedCallback.ts')
    shutil.copy2(ROOT / 'compat/cpa/zedCallback.test.ts', destination / 'tests/zedCallback.test.ts')
    print('Adapted official CPA OAuth card: authenticated Zed paste, original v8 polling and credentials')
    apply_quota(destination)


def apply_quota(destination):
    card_path = destination / 'src/features/authFiles/components/AuthFileCard.tsx'
    client_path = destination / 'src/services/api/client.ts'
    card = card_path.read_text(encoding='utf-8')
    client = client_path.read_text(encoding='utf-8')
    marker = "import { ZedAuthFileQuota } from './ZedAuthFileQuota';\n"
    if marker not in card:
        card = marker + replace_once(card,
            '      <footer className={styles.actions}>',
            '''      {providerKey === 'zed' && !isRuntimeOnly && (
        <ZedAuthFileQuota
          authIndex={authIndexKey ?? undefined}
          disabled={disableControls || file.disabled === true}
        />
      )}

      <footer className={styles.actions}>''')
    if '  async postPluginQuota<' not in client:
        method = '''  async postPluginQuota<T = unknown>(
    plugin: string,
    authIndex: string,
    config?: AxiosRequestConfig
  ): Promise<T> {
    if (!/^[a-z0-9_-]+$/.test(plugin)) throw new Error('Invalid plugin identifier');
    const scopedConfig: PluginRequestConfig = {
      ...config,
      pluginConnectionRevision: this.connectionRevision,
    };
    return this.post<T>(`/plugins/${plugin}/quota`, { auth_index: authIndex }, scopedConfig);
  }

'''
        client = replace_once(client, '  /**\n   * PUT 请求\n   */', method + '  /**\n   * PUT 请求\n   */')
    messages = {
        'zh-CN': ['Zed 额度', '刷新额度', '点击刷新查询当前套餐和用量。', '额度查询失败，请检查网络和凭证后重试。', '套餐', 'Token Spend（美元）', '金额上限（美元）', '剩余额度（美元）', '未提供', '模型按钮列出此凭证从 Zed 动态发现的模型，默认使用原始模型名。'],
        'zh-TW': ['Zed 額度', '重新整理額度', '點擊重新整理以查詢目前方案與用量。', '額度查詢失敗，請檢查網路與憑證後重試。', '方案', 'Token Spend（美元）', '金額上限（美元）', '剩餘額度（美元）', '未提供', '模型按鈕列出此憑證從 Zed 動態發現的模型，預設使用原始模型名稱。'],
        'en': ['Zed quota', 'Refresh quota', 'Refresh to read the current plan and usage.', 'Unable to read quota. Check the network and credential, then retry.', 'Plan', 'Token Spend (USD)', 'Token spend limit (USD)', 'Remaining credit (USD)', 'Not provided', 'Models lists the dynamically discovered models for this credential, using original names by default.'],
        'ru': ['Квота Zed', 'Обновить квоту', 'Обновите, чтобы получить текущий тариф и использование.', 'Не удалось получить квоту. Проверьте сеть и учётные данные.', 'Тариф', 'Token Spend (USD)', 'Лимит расходов (USD)', 'Остаток (USD)', 'Не указано', 'Кнопка моделей показывает динамический каталог учётной записи с исходными именами моделей.'],
    }
    keys = ['title', 'refresh', 'idle', 'error', 'plan', 'used', 'limit', 'remaining', 'unknown', 'model_hint']
    locales = {}
    for language, values in messages.items():
        path = destination / f'src/i18n/locales/{language}.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['zed_quota'] = dict(zip(keys, values))
        data['zed_quota']['billing_unavailable'] = {
            'zh-CN': '编辑器登录凭证未提供 Token Spend。请求次数不代表金额，请到 Zed 账单页面查看实际金额用量。',
            'zh-TW': '編輯器登入憑證未提供 Token Spend。請求次數不代表金額，請至 Zed 帳單頁面查看實際金額用量。',
            'en': 'The editor credential does not provide Token Spend. Request counts are not dollar amounts. View actual spend in the Zed billing dashboard.',
            'ru': 'Учётные данные редактора не предоставляют Token Spend. Число запросов не является суммой в долларах. Фактические расходы доступны в платёжной панели Zed.',
        }[language]
        data['zed_quota']['fixed_plan'] = {'zh-CN': '固定显示', 'zh-TW': '固定顯示', 'en': 'Fixed display', 'ru': 'Фиксированное отображение'}[language]
        data['zed_quota']['fixed_note'] = {
            'zh-CN': '按配置固定显示：已用 $0 / 总额度 $10，刷新不变。这不是 Zed 实际账单，不会自动扣减或限制请求。',
            'zh-TW': '依設定固定顯示：已用 $0 / 總額度 $10，重新整理不變。這不是 Zed 實際帳單，不會自動扣減或限制請求。',
            'en': 'Fixed display: $0 used of $10, always unchanged. This is not actual Zed billing and does not impose a spending limit.',
            'ru': 'Фиксированное отображение: использовано $0 из $10. Не отражает фактические расходы Zed и не ограничивает запросы.',
        }[language]
        data['zed_billing'] = {'expired': {'zh-CN': '账单会话过期时，请更新账单 Cookie。', 'zh-TW': '帳單會話過期時，請更新帳單 Cookie。', 'en': 'If the billing session expired, update the billing cookie.', 'ru': 'Если платёжная сессия истекла, обновите cookie.'}[language]}
        locales[path] = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    for path, text in {card_path: card, client_path: client, **locales}.items():
        path.write_text(text, encoding='utf-8')
    for name in ['ZedAuthFileQuota.tsx', 'ZedAuthFileQuota.module.scss', 'ZedBillingSession.tsx', 'ZedBillingSession.module.scss']:
        shutil.copy2(ROOT / 'compat/cpa' / name, card_path.parent / name)
    shutil.copy2(ROOT / 'compat/cpa/zedQuota.ts', destination / 'src/services/api/zedQuota.ts')
    shutil.copy2(ROOT / 'compat/cpa/zedQuota.test.ts', destination / 'tests/zedQuota.test.ts')
    print('Adapted existing Zed credential card: native v8 quota, manual refresh and model guidance')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    apply(parser.parse_args().source)
