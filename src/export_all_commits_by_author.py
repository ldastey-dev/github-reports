import utils
import requests
import pandas as pd


# Gets all commits for a given author in a repository
def get_commits_by_author(org, repository, author):
    page = 1
    commits = []

    while True:
        url = f'{utils.BASE_URL}/repos/{org}/{repository}/commits?author={author}&page={page}&per_page=100'
        
        response = requests.get(url, headers=utils.headers)
        utils.handle_rate_limit(response)

        if response.status_code != 200:
            utils.print_line(f'Error fetching commits for {org}/{repository}: {response.status_code}')
            break

        data = response.json()
        if not data:
            break
        
        commits.extend(data)
        page += 1

    return commits


# Generate a report showing all commits by a given author
@utils.calculate_execution_time
def generate_author_commit_report(author):
    all_commits = []
    org = utils.ORG_NAME
    
    repos = utils.get_repositories(org)
    utils.print_line(f"Found {len(repos)} repositories for {org}")

    for repo in repos:
        repository = repo['name']
        utils.print_line(f"Processing repository: {repository}")

        commits = get_commits_by_author(org, repository, author)
        utils.print_line(f"Found {len(commits)} commits by {author} in {repository}")

        for commit in commits:
            commit_data = {
                'repo': repository,
                'date': commit['commit']['author']['date'],
                'message': commit['commit']['message'],
                'url': commit['html_url'],
                'sha': commit['sha']
            }
            all_commits.append(commit_data)

    df = pd.DataFrame(all_commits)

    file = utils.get_unique_filename(utils.OUTPUT_FOLDER, f'{author} Commit History', 'xlsx')
    df.to_excel(file, index=False)
    utils.print_line(f'Commits by author {author} saved to {file}')


if __name__ == '__main__':
    author = input("Enter the author's GitHub username: ")
    generate_author_commit_report(author.strip())
