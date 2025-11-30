def run_issue_command(repo, issue, new_branch_name, base_branch_name, commit_message, pr_title, pr_body):
    # ... существующий код ...
    try:
        pr = repo.create_pull(title=pr_title, body=pr_body, head=new_branch_name, base=base_branch_name)
        repo.get_git_ref(f"heads/{new_branch_name}").delete()
    except Exception as e:
        print(f"Ошибка удаления ветки: {e}")
    # ... существующий код ...
