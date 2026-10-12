"""Check callback adaptation and fail-closed behavior against an upstream checkout."""
import argparse
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from apply_cpa_ui_compat import apply

SOURCE = None


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


class AdaptationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='cpa-panel-adaptation-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in ('src', 'tests'):
            shutil.copytree(SOURCE / name, self.root / name)
        self.feature_layout = (self.root / 'src/features/oauth/hooks/useOAuthFlows.ts').is_file()
        self.callback_path = self.root / ('src/features/oauth/hooks/useOAuthFlows.ts'
                                         if self.feature_layout else 'src/pages/OAuthPage.tsx')

    def test_preserves_callback_quota_and_is_idempotent(self):
        apply(self.root)
        first = snapshot(self.root)
        apply(self.root)
        self.assertEqual(first, snapshot(self.root))
        callback = self.callback_path.read_text()
        self.assertIn('validateZedCallback(callbackInput, states[provider]?.state)', callback)
        self.assertIn('await oauthApi.submitZedCallback', callback)
        self.assertIn('oauthApi.getAuthStatus(state, attempt.signal)', callback)
        self.assertIn('notifyAuthFilesChanged()', callback)
        self.assertIn('callbackUrl:', callback)
        client = (self.root / 'src/services/api/client.ts').read_text()
        self.assertIn('pluginConnectionRevision', client)
        self.assertIn('async postPluginQuota', client)
        self.assertIn("'/v0/management'", client)
        oauth = (self.root / 'src/services/api/oauth.ts').read_text()
        self.assertIn('/plugins/zed/login/callback', oauth)
        card = (self.root / 'src/features/authFiles/components/AuthFileCard.tsx').read_text()
        self.assertIn('<ZedAuthFileQuota', card)
        self.assertEqual(card.count("import { ZedAuthFileQuota }"), 1)
        if self.feature_layout:
            dialog = (self.root / 'src/features/oauth/components/OAuthFlowDialog.tsx').read_text()
            self.assertIn('auth_login.zed_callback_hint', dialog)
            self.assertIn('auth_login.zed_callback_placeholder', dialog)
            self.assertIn("rejectInput('auth_login.zed_callback_invalid')", callback)
            self.assertTrue((self.root / 'src/features/oauth/zedCallback.ts').is_file())

    def test_changed_callback_anchor_fails_without_partial_writes(self):
        callback = self.callback_path.read_text()
        anchor = 'await oauthApi.submitCallback(provider, redirectUrl, attempt.signal);'
        self.assertIn(anchor, callback)
        self.callback_path.write_text(callback.replace(anchor, 'await changedUpstreamContract();'))
        before = snapshot(self.root)
        with self.assertRaisesRegex(ValueError, 'refusing a partial Zed adaptation'):
            apply(self.root)
        self.assertEqual(before, snapshot(self.root))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    SOURCE = parser.parse_args().source.resolve()
    unittest.main(argv=['test_apply_cpa_ui_compat'], verbosity=2)
