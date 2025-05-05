import utils
import requests
import pandas as pd


# Gets all commits for a given author in a GitHub repository
def get_github_commits_by_author(org, repository, author):
    page = 1
    commits = []

    while True:
        url = f'{utils.GITHUB_BASE_URL}/repos/{org}/{repository}/commits?author={author}&page={page}&per_page=100'
        
        response = requests.get(url, headers=utils.github_headers)
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


# Gets all commits for a given author in an ADO repository
def get_ado_commits_by_author(repository_id, author):
    commits = []
    page_size = 100
    skip = 0
    
    while True:
        # ADO pagination works differently than GitHub
        url = (f'{utils.ADO_BASE_URL}/{utils.ADO_PROJECT}/_apis/git/repositories/{repository_id}/commits'
               f'?searchCriteria.author={author}'
               f'&searchCriteria.$skip={skip}'
               f'&searchCriteria.$top={page_size}'
               f'&api-version=6.0')
        
        response = requests.get(url, headers=utils.ado_headers)
        
        if response.status_code != 200:
            utils.print_line(f'Error fetching ADO commits: {response.status_code} - {response.text}')
            break
        
        data = response.json()
        
        if not data.get('value'):
            break
            
        # Transform ADO commit format to match GitHub format
        for commit in data['value']:
            github_style_commit = {
                'sha': commit['commitId'],
                'html_url': commit.get('remoteUrl', ''),
                'commit': {
                    'author': {
                        'name': commit['author']['name'],
                        'email': commit['author']['email'],
                        'date': commit['author']['date']
                    },
                    'message': commit['comment']
                },
                'author': {
                    'login': commit['author']['name']
                }
            }
            commits.append(github_style_commit)
        
        # ADO will return fewer items than page_size when we've reached the end
        if len(data['value']) < page_size:
            break
            
        skip += page_size
    
    return commits


# Generic function to get commits by author for either GitHub or ADO
def get_commits_by_author(repository, author):
    if utils.GIT_PROVIDER == 'ado':
        return get_ado_commits_by_author(repository['id'], author)
    else:
        return get_github_commits_by_author(utils.ORG_NAME, repository['name'], author)


# Generate a report showing all commits by a given author
@utils.calculate_execution_time
def generate_author_commit_report(author):
    all_commits = []
    
    repos = utils.get_repositories()
    utils.print_line(f"Found {len(repos)} repositories")

    for repo in repos:
        if utils.GIT_PROVIDER == 'ado':
            repository_name = repo['name']
            repository_id = repo['id']
        else:
            repository_name = repo['name']
            repository_id = repo['name']
            
        utils.print_line(f"Processing repository: {repository_name}")

        commits = get_commits_by_author(repo, author)
        utils.print_line(f"Found {len(commits)} commits by {author} in {repository_name}")

        for commit in commits:
            commit_data = {
                'repo': repository_name,
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
    provider_name = "ADO" if utils.GIT_PROVIDER == 'ado' else "GitHub"
    author = input(f"Enter the author's {provider_name} username: ")
    generate_author_commit_report(author.strip())
