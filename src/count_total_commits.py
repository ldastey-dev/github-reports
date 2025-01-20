import os
import utils
import requests
from datetime import datetime


# Get the list of branches in a repository 
def get_branches(org, repository):
    page = 1
    branches = []

    while True:
        url = f'{utils.BASE_URL}/repos/{org}/{repository}/branches?page={page}&per_page=100'

        response = requests.get(url, headers=utils.headers)
        utils.handle_rate_limit(response)

        if response.status_code != 200:
            print(f'Error fetching branches for {org}/{repository}: {response.status_code}')
            break

        data = response.json()
        if not data:
            break

        branches.extend(data)
        
        page += 1

    return branches


# Get the number of commits in a branch from 1 January 2024 to present
def get_commit_count(org, repository, branch_name):
    start_date = os.getenv('START_DATE')
    end_date = datetime.utcnow().isoformat() + 'Z'
    url = f'{utils.BASE_URL}/repos/{org}/{repository}/commits?sha={branch_name}&since={start_date}&until={end_date}'
    
    response = requests.get(url, headers=utils.headers)
    utils.handle_rate_limit(response)

    if response.status_code != 200:
        print(f'Error fetching commits for {org}/{repository} on branch {branch_name}: {response.status_code}')
        return 0

    return len(response.json())


@utils.calculate_execution_time
def main():
    total_commits = 0;
    org = os.getenv('ORG_NAME')

    repos = utils.get_repositories(org)

    for repository in repos:
        repository_name = repository['name']

        branches = get_branches(org, repository_name)

        for branch in branches:
            branch_name = branch['name']

            if branch_name not in ['main', 'master']:
                commit_count = get_commit_count(org, repository_name, branch_name)
                
                total_commits += commit_count
                print(f'Repo: {org}/{repository_name}, Branch: {branch_name}, Commits: {commit_count}')
                print(f'TOTAL COMMIT COUNT: {total_commits}')


if __name__ == '__main__':
    main()