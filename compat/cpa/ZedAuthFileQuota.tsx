import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { IconRefreshCw } from '@/components/ui/icons';
import { useAuthStore } from '@/stores';
import { apiClient } from '@/services/api/client';
import { zedQuotaApi, quotaPlanLabel, quotaRemainingPercent, type ZedQuota } from '@/services/api/zedQuota';
import styles from './ZedAuthFileQuota.module.scss';
import { ZedBillingSession } from './ZedBillingSession';

export function ZedAuthFileQuota({
  authIndex,
  disabled,
}: {
  authIndex: string | undefined;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const apiBase = useAuthStore((state) => state.apiBase);
  const managementKey = useAuthStore((state) => state.managementKey);
  const supportsPlugin = useAuthStore((state) => state.supportsPlugin);
  const revision = apiClient.getConnectionRevision();
  const scope = JSON.stringify([apiBase, managementKey, authIndex, revision, disabled]);
  const [result, setResult] = useState<{ scope: string; quota: ZedQuota } | null>(null);
  const [status, setStatus] = useState<{ scope: string; error: boolean; loading: boolean } | null>(null);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => { pending.current?.abort(); pending.current = null; }, [scope]);
  const loading = status?.scope === scope && status.loading;
  const failed = status?.scope === scope && status.error;
  const quota = result?.scope === scope ? result.quota : null;
  const refresh = async () => {
    if (disabled || !supportsPlugin || !authIndex || !apiBase || !managementKey || pending.current) return;
    const controller = new AbortController();
    pending.current = controller;
    setStatus({ scope, error: false, loading: true });
    try {
      const data = await zedQuotaApi.fetch(authIndex, { signal: controller.signal });
      if (!controller.signal.aborted && revision === apiClient.getConnectionRevision()) {
        setResult({ scope, quota: data });
      }
    } catch {
      if (!controller.signal.aborted && revision === apiClient.getConnectionRevision()) {
        setResult(null);
        setStatus({ scope, error: true, loading: false });
      }
      return;
    } finally {
      if (pending.current === controller) pending.current = null;
    }
    if (!controller.signal.aborted && revision === apiClient.getConnectionRevision()) {
      setStatus({ scope, error: false, loading: false });
    }
  };
  const remainingPercent = quotaRemainingPercent(quota);
  const percentLabel = remainingPercent == null ? null : new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(remainingPercent) + '%';
  const value = (number: number | null | undefined) => number == null ? t('zed_quota.unknown') : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(number);
  return (
    <section className={styles.section} data-zed-plugin-quota="true" aria-label={t('zed_quota.title')}>
      <div className={styles.header}>
        <strong>{t('zed_quota.title')}</strong>
        <Button type="button" size="sm" variant="secondary" loading={loading}
          disabled={disabled || !supportsPlugin || !authIndex || !apiBase || !managementKey || loading}
          onClick={() => void refresh()}>
          {!loading && <IconRefreshCw size={14} />}{t('zed_quota.refresh')}
        </Button>
      </div>
      {failed && <p className={styles.error} role="alert">{t('zed_quota.error')} {t('zed_billing.expired', { defaultValue: 'If the billing session expired, update the billing cookie.' })}</p>}
      {!quota && !failed && <p className={styles.note}>{t('zed_quota.idle')}</p>}
      {quota && <dl className={styles.metrics}>
        <div><dt>{t('zed_quota.plan')}</dt><dd title={quota.plan ?? undefined}>{quota.plan === 'fixed-display' ? t('zed_quota.fixed_plan') : quotaPlanLabel(quota.plan) ?? t('zed_quota.unknown')}</dd></div>
        <div><dt>{t('zed_quota.used')}</dt><dd>{value(quota.used)}</dd></div>
        <div><dt>{t('zed_quota.limit')}</dt><dd>{value(quota.limit)}</dd></div>
        <div><dt>{t('zed_quota.remaining')}</dt><dd>{value(quota.remaining)}</dd></div>
      </dl>}
      {remainingPercent != null && <div className={styles.progress} data-tone={remainingPercent <= 5 ? 'empty' : remainingPercent <= 20 ? 'low' : 'normal'}>
        <div className={styles.progressHeading}><span>{t('zed_quota.remaining')}</span><strong>{percentLabel}</strong></div>
        <div className={styles.track} role="progressbar" aria-label={t('zed_quota.remaining')} aria-valuemin={0} aria-valuemax={100} aria-valuenow={remainingPercent} aria-valuetext={percentLabel ?? undefined}>
          <div className={styles.fill} style={{ width: `${remainingPercent}%` }} />
        </div>
      </div>}
      {quota?.plan === 'fixed-display' && <p className={styles.note}>{t('zed_quota.fixed_note')}</p>}
      {quota && quota.used == null && <p className={styles.note}>{t('zed_quota.billing_unavailable')}</p>}
      <ZedBillingSession scope={scope}
        disabled={disabled || !supportsPlugin || !authIndex || !apiBase || !managementKey || Boolean(loading)}
        request={(action, cookie, signal) => zedQuotaApi.session(authIndex!, action, cookie, signal)}
        onChange={() => { pending.current?.abort(); pending.current = null; setResult(null); setStatus(null); }} />
    </section>
  );
}
