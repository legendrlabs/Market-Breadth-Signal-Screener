import importlib.util
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-b', 'main')
        (self.root / 'pyproject.toml').write_text('[project]\nversion = "0.1.0"\n')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'initial')
        path = Path(__file__).resolve().parents[1] / 'scripts/release_metadata.py'
        self.assertTrue(path.exists(), 'release metadata generator missing')
        spec = importlib.util.spec_from_file_location('mbss_release_metadata', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def build(self, **kwargs):
        return self.module.build_metadata(self.root, kwargs.get('sha', self.git('rev-parse', 'HEAD')))

    def test_metadata_hashes_only_committed_source_and_preserves_hold(self):
        (self.root / 'untracked.txt').write_text('private')
        value = self.build()
        self.assertEqual(value['version'], '0.1.0')
        self.assertEqual(value['tag'], 'v0.1.0')
        self.assertEqual(set(value['managed_files']), {'pyproject.toml'})
        self.assertFalse(value['SAFE_TO_ACT'])
        self.assertEqual(value['historical_claims_status'], 'UNVERIFIED')
        self.assertFalse(value['skip_publish'])

    def test_source_must_be_tested_head(self):
        with self.assertRaisesRegex(ValueError, 'tested'):
            self.build(sha='a' * 40)

    def test_dirty_tracked_source_cannot_publish(self):
        (self.root / 'pyproject.toml').write_text('[project]\nversion = "0.2.0"\n')
        with self.assertRaisesRegex(ValueError, 'tracked'):
            self.build()

    def test_tracked_provider_data_is_rejected(self):
        (self.root / 'data').mkdir()
        (self.root / 'data/raw.csv').write_text('private')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'accidental data')
        with self.assertRaisesRegex(ValueError, 'path'):
            self.build()

    def test_existing_version_at_other_commit_is_never_moved(self):
        self.git('tag', 'v0.1.0')
        before = self.git('rev-parse', 'v0.1.0')
        (self.root / 'README.md').write_text('later')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'later')
        self.assertTrue(self.build()['skip_publish'])
        self.assertEqual(self.git('rev-parse', 'v0.1.0'), before)

    def test_same_commit_draft_can_be_retried(self):
        self.git('tag', 'v0.1.0')
        self.assertFalse(self.build()['skip_publish'])


if __name__ == '__main__':
    unittest.main()
