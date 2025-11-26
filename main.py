import os

from agent.agent_pr_proposer import AgentPRProposer


def main():
    github_token = os.environ["GITHUB_TOKEN"]
    repo_name = os.environ["GITHUB_REPOSITORY"]
    pr_title = os.environ["PR_TITLE"]
    pr_body = os.environ["PR_BODY"]

    agent = AgentPRProposer(github_token, repo_name)
    agent.propose_pr(pr_title, pr_body)


if __name__ == "__main__":
    main()
