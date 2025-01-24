import utils
import requests
import pandas as pd
from datetime import datetime, timezone


# Get all the commits for a repository 
def get_commits_for_repository(repository, start_date, end_date):
    page = 1
    commits = []

    while True:
        url = f'{utils.BASE_URL}/repos/{utils.ORG_NAME}/{repository}/commits?since={start_date}&until={end_date}&page={page}&per_page=100'

        response = requests.get(url, headers=utils.headers)
        utils.handle_rate_limit(response)

        if response.status_code != 200:
            print(f'Error fetching commits for {repository}: {response.status_code}')
            break

        data = response.json()
        if not data:
            break

        commits.extend(data)
        page += 1

    return commits


# Generate a report of commit counts by author each month over a time period  
@utils.calculate_execution_time
def generate_commit_count_report():
    commit_data = []
    start_date = '2024-01-01T00:00:00Z'
    end_date = datetime.now(timezone.utc)
    
    repos = utils.get_repositories(utils.ORG_NAME)

    for repo in repos:
        repo_name = repo['name']

        commits = get_commits_for_repository(repo_name, start_date, end_date)

        for commit in commits:
            author = commit['commit']['author']
            author_name = author['name']
            commit_date = author['date']
            commit_month = datetime.strptime(
                commit_date, '%Y-%m-%dT%H:%M:%SZ'
            ).strftime('%B')  # Convert month to English

            commit_data.append({
                'repo': repo_name,
                'author': author_name,
                'month': commit_month
            })

    df = pd.DataFrame(commit_data)
    month_order = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    df['month'] = pd.Categorical(df['month'], categories=month_order, ordered=True)

    # Create pivot table with ordered months
    commit_counts = df.pivot_table(index='author', columns='month', aggfunc='size', fill_value=0)

    # Reset index to make 'author' a column
    commit_counts.reset_index(inplace=True)

    file = utils.get_unique_filename(utils.OUTPUT_FOLDER, f'{utils.ORG_NAME} Contribution Report', 'xlsx')
    commit_counts.to_excel(
        file, 
        index=False, 
        sheet_name='Commits by Author'
    )
    print(f'Commit counts by author saved to {file}')


if __name__ == '__main__':
    generate_commit_count_report()
