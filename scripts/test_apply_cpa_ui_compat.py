"""Check callback adaptation and fail-closed behavior against an upstream checkout."""
import argparse
import hashlib
from pathlib import Path
import re
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

    def assert_client_adaptation_is_stable(self):
        apply(self.root)
        client = (self.root / 'src/services/api/client.ts').read_text()
        self.assertEqual(client.count('async postPlugin<'), 1)
        self.assertEqual(client.count('async postPluginQuota<'), 1)
        self.assertLess(client.index('const revision = (config as PluginRequestConfig)'),
                        client.index('config.baseURL = this.apiBase;'))
        self.assertLess(client.index('async postPluginQuota<'), client.index('async put<'))
        first = snapshot(self.root)
        apply(self.root)
        self.assertEqual(first, snapshot(self.root))

    def test_client_comment_translation_preserves_adaptation_and_documentation(self):
        path = self.root / 'src/services/api/client.ts'
        client = path.read_text()
        client = re.sub(r'(?m)^        // .*baseURL.*$',
                        '        // Arbitrary translated request comment', client)
        client = re.sub(r'(?m)^   \* PUT .*$', '   * Arbitrary translated method comment', client)
        path.write_text(client)
        self.assert_client_adaptation_is_stable()
        adapted = path.read_text()
        self.assertIn('  /**\n   * Arbitrary translated method comment\n   */\n  async put<', adapted)

    def test_client_comments_are_optional(self):
        path = self.root / 'src/services/api/client.ts'
        client = re.sub(r'/\*[\s\S]*?\*/|(?m:^[ \t]*//[^\n]*)', '', path.read_text())
        path.write_text(client)
        self.assert_client_adaptation_is_stable()

    def test_changed_or_ambiguous_client_code_fails_without_partial_writes(self):
        path = self.root / 'src/services/api/client.ts'
        original = path.read_text()
        for anchor in ('        config.baseURL = this.apiBase;', '  async put<T = unknown>('):
            self.assertEqual(original.count(anchor), 1)
            for count in (0, 2):
                with self.subTest(anchor=anchor, count=count):
                    path.write_text(original.replace(anchor, anchor * count))
                    before = snapshot(self.root)
                    with self.assertRaisesRegex(ValueError, 'refusing a partial Zed adaptation'):
                        apply(self.root)
                    self.assertEqual(before, snapshot(self.root))
        path.write_text(original)

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
