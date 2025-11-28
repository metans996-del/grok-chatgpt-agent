import unittest
from unittest.mock import patch

from agent.agent_pr_proposer import propose_pr


class TestProposePR(unittest.TestCase):
    @patch('requests.post')
    def test_propose_pr_success(self, mock_post) -> None:
        mock_post.return_value.status_code = 201
        result = propose_pr('owner', 'repo', 'head', 'base', 'token')
        self.assertEqual(result['status'], 'success')

    @patch('requests.post')
    def test_propose_pr_failure(self, mock_post) -> None:
        mock_post.return_value.status_code = 400
        result = propose_pr('owner', 'repo', 'head', 'base', 'token')
        self.assertEqual(result['status'], 'failure')

if __name__ == '__main__':
    unittest.main()
