import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { IconSettings } from '@/components/ui/icons';
import styles from './ZedBillingSession.module.scss';

export function ZedBillingSession({ scope, disabled, request, onChange }: {
  scope: string;
  disabled: boolean;
  request: (action: 'status' | 'save' | 'remove', cookie: string, signal: AbortSignal) => Promise<{ configured: boolean }>;
  onChange: () => void;
}) {
  const { t, i18n } = useTranslation();
  const text = (key: string, en: string, zh: string) => t(`zed_billing.${key}`, { defaultValue: i18n?.resolvedLanguage?.startsWith('zh') ? zh : en });
  const [open, setOpen] = useState(false);
  const [cookie, setCookie] = useState('');
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const generation = useRef(0);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => {
    generation.current += 1;
    pending.current?.abort(); pending.current = null;
    setOpen(false); setCookie(''); setConfigured(null); setBusy(false); setFailed(false);
    return () => { generation.current += 1; pending.current?.abort(); };
  }, [scope]);
  const send = async (action: 'status' | 'save' | 'remove') => {
    if (disabled || pending.current) return;
    const controller = new AbortController();
    pending.current = controller;
    const revision = ++generation.current;
    setBusy(true); setFailed(false);
    try {
      const result = await request(action, action === 'save' ? cookie : '', controller.signal);
      if (controller.signal.aborted || revision !== generation.current) return;
      setConfigured(result.configured);
      if (action !== 'status') { setCookie(''); onChange(); }
    } catch {
      if (!controller.signal.aborted && revision === generation.current) setFailed(true);
    } finally {
      if (pending.current === controller) pending.current = null;
      if (revision === generation.current) setBusy(false);
    }
  };
  const close = () => {
    generation.current += 1; pending.current?.abort(); pending.current = null;
    setCookie(''); setBusy(false); setFailed(false); setOpen(false);
  };
  return <div className={styles.root} data-zed-billing-session="true">
    <Button type="button" size="sm" variant="secondary" disabled={disabled || busy} onClick={() => { setOpen(true); void send('status'); }}>
      <IconSettings size={14} />
      {text('configure', 'Billing cookie', '账单设置')}
    </Button>
    {open && <div className={styles.panel} role="dialog" aria-label={text('configure', 'Billing cookie', '账单设置')}>
      <p className={styles.hint}>{text('hint', 'Paste zed.session from your Zed dashboard. It is used only for billing refresh.', '粘贴 Zed 网页中的 zed.session，仅用于刷新账单额度。')}</p>
      <p className={styles.status} data-configured={configured === true}>{configured === null ? '—' : configured ? text('configured', 'Billing session configured', '已配置账单会话') : text('absent', 'No billing session configured', '尚未配置账单会话')}</p>
      <label className={styles.label}>{text('value', 'Zed session cookie', 'Zed 会话 Cookie')}
        <input className={styles.input} type="password" autoComplete="off" maxLength={8192} value={cookie} placeholder="zed.session=..."
          disabled={busy || disabled} onChange={event => setCookie(event.target.value)} />
      </label>
      {failed && <p className={styles.error} role="alert">{text('error', 'Unable to update the billing session. Check the cookie and try again.', '账单会话操作失败，请检查 Cookie 后重试。')}</p>}
      <div className={styles.actions}>
      <Button type="button" size="sm" loading={busy} disabled={busy || disabled || !cookie.trim()} onClick={() => void send('save')}>{text('save', 'Save billing cookie', '保存账单 Cookie')}</Button>
      <Button type="button" size="sm" variant="secondary" className={styles.remove} disabled={busy || disabled || !configured} onClick={() => void send('remove')}>{text('remove', 'Remove billing cookie', '删除账单 Cookie')}</Button>
      <Button type="button" size="sm" variant="secondary" onClick={close}>{text('close', 'Close', '关闭')}</Button>
      </div>
      <p className={styles.hint}>{text('refresh_hint', 'After saving, click Refresh quota. An expired session needs a new cookie.', '保存后点击刷新额度；会话过期时需要更新 Cookie。')}</p>
    </div>}
  </div>;
}
