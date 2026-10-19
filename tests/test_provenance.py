import unittest
from mbss import pipeline


class ProvenanceTests(unittest.TestCase):
    def context(self, commit='a' * 40, **overrides):
        env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'example/mbss',
             'GITHUB_SHA':'a' * 40,'GITHUB_RUN_ID':'12345'}
        env.update(overrides)
        fn=getattr(pipeline,'publication_context',None)
        self.assertTrue(callable(fn), 'publication context must replace fixed unpublished metadata')
        return fn(commit,env)

    def test_matching_ci_records_repository_and_exact_run(self):
        value=self.context()
        self.assertEqual(value['github_repository'],'https://github.com/example/mbss')
        self.assertEqual(value['workflow_run_url'],'https://github.com/example/mbss/actions/runs/12345')
        self.assertEqual(value['execution_context'],'GITHUB_ACTIONS_MATCHING_CHECKOUT')
        self.assertEqual(value['release'],'NOT_CHECKED')

    def test_local_execution_does_not_assert_repository_unpublished(self):
        value=self.context(GITHUB_ACTIONS='false')
        self.assertEqual(value['github_repository'],'UNKNOWN_NOT_CHECKED')
        self.assertEqual(value['release'],'NOT_CHECKED')
        self.assertIsNone(value['workflow_run_url'])

    def test_mismatched_checkout_cannot_claim_ci_source(self):
        value=self.context(commit='b' * 40)
        self.assertEqual(value['github_repository'],'UNKNOWN_NOT_CHECKED')
        self.assertIsNone(value['workflow_run_url'])

    def test_unchecked_repository_or_run_cannot_make_links(self):
        for overrides in ({'GITHUB_REPOSITORY':'example/mbss/tree/main'},
                          {'GITHUB_RUN_ID':'12345?other'}, {'GITHUB_SHA':''}):
            self.assertIsNone(self.context(**overrides)['workflow_run_url'])


if __name__=='__main__':
    unittest.main()
