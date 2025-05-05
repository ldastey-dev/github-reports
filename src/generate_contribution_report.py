import utils
import requests
import pandas as pd
from datetime import datetime, timezone
import calendar


# Get username from commit data (works for both GitHub and ADO)
def get_username(commit):
    # Check if there's author data in the API response
    if 'author' in commit and commit['author']:
        # Return username if available
        return commit['author']['login']
    # If no username is available, fall back to commit author name
    return commit['commit']['author']['name']


def parse_start_date(start_date):
    try:
        return datetime.strptime(start_date, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError as e:
        utils.print_line(f"ERROR: Failed to parse START_DATE '{start_date}': {e}")
        utils.print_line("Make sure START_DATE in .env is in format 'YYYY-MM-DDThh:mm:ssZ', e.g. 2024-01-01T00:00:00Z")
        return None


def get_month_range(start_dt, end_dt):
    naive_start = start_dt.replace(tzinfo=None, day=1)
    naive_end = end_dt.replace(tzinfo=None, day=1)

    return pd.date_range(start=naive_start, end=naive_end, freq='MS')


def collect_commit_data(repos, start_date, end_date_str, start_dt):
    commit_data = []
    username_to_author_map = {}

    for repo in repos:
        # Extract repository name - different between GitHub and ADO
        if utils.GIT_PROVIDER == 'ado':
            repo_name = repo['name']
            repo_id = repo['id']
        else:
            repo_name = repo['name']
            repo_id = repo_name  # For GitHub, name is the identifier
            
        utils.print_line("Processing repository:", repo_name)
        
        # Use the new generic get_commits function that works for both providers
        commits = utils.get_commits(repo, start_date, end_date_str)
        utils.print_line(f"Found {len(commits)} commits in {repo_name}")
        
        for commit in commits:
            author = commit['commit']['author']
            author_name = author['name']
            commit_date = author['date']
            commit_dt = datetime.strptime(commit_date, '%Y-%m-%dT%H:%M:%SZ')
        
            username = get_username(commit)
        
            if username not in username_to_author_map:
                username_to_author_map[username] = set()
 
            username_to_author_map[username].add(author_name)

            if commit_dt >= start_dt.replace(tzinfo=None):
                display_month_year = commit_dt.strftime('%b %y')
                commit_data.append({
                    'repo': repo_name,
                    'username': username,
                    'author': author_name,
                    'month_year': display_month_year,
                    'commit_date': commit_dt
                })

    return commit_data, username_to_author_map


def create_commit_pivot_table(commit_data, all_month_years):
    df = pd.DataFrame(commit_data)
    commit_counts = df.groupby(['username', 'month_year']).size().reset_index(name='count')

    pivot_table = pd.pivot_table(
        commit_counts,
        values='count',
        index=['username'],
        columns=['month_year'],
        fill_value=0
    )

    for month_year in all_month_years:
        if month_year not in pivot_table.columns:
            pivot_table[month_year] = 0

    pivot_table = pivot_table.reindex(columns=all_month_years)
    pivot_table.reset_index(inplace=True)

    return pivot_table


def create_username_map_df(username_to_author_map):
    # Adjust column names based on provider
    username_column = "ADO Username" if utils.GIT_PROVIDER == 'ado' else "GitHub Username" 
    
    return pd.DataFrame([
        {username_column: username, 'Author Names': ', '.join(names)}
        for username, names in username_to_author_map.items()
    ])


def write_report_excel(pivot_table, username_map_df, file):
    # Adjust sheet name based on provider
    username_sheet_name = "Commits by ADO Username" if utils.GIT_PROVIDER == 'ado' else "Commits by GitHub Username"
    
    with pd.ExcelWriter(file) as writer:
        pivot_table.to_excel(writer, index=False, sheet_name=username_sheet_name)
        username_map_df.to_excel(writer, index=False, sheet_name='Username Mapping')


def print_reconciliation_info(username_to_author_map):
    provider = "ADO" if utils.GIT_PROVIDER == 'ado' else "GitHub"
    utils.print_line("\nAuthor name reconciliation information:")

    for username, names in username_to_author_map.items():
        if len(names) > 1:
            utils.print_line(f"{provider} user '{username}' has commits under multiple names: {', '.join(names)}")


@utils.calculate_execution_time
def generate_commit_count_report():
    start_date = utils.START_DATE
    current_date = datetime.now(timezone.utc)
 
    end_date = current_date.replace(day=calendar.monthrange(current_date.year, current_date.month)[1], hour=23, minute=59, second=59)
    end_date_str = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
    start_dt = parse_start_date(start_date)

    if not start_dt:
        return

    utils.print_line(f"Generating report from {start_dt.strftime('%B %Y')} to {end_date.strftime('%B %Y')}")
    utils.print_line(f"Report should include {(end_date.year - start_dt.year) * 12 + end_date.month - start_dt.month + 1} months")

    repos = utils.get_repositories()
    utils.print_line(f"Found {len(repos)} repositories")

    commit_data, username_to_author_map = collect_commit_data(repos, start_date, end_date_str, start_dt)

    if not commit_data:
        utils.print_line("No commits found in the specified date range")
        return

    month_range = get_month_range(start_dt, end_date)
    all_month_years = [d.strftime('%b %y') for d in month_range]
    utils.print_line("Report will include these months:", all_month_years)
    utils.print_line("Total months in report:", len(all_month_years))

    print_reconciliation_info(username_to_author_map)

    pivot_table = create_commit_pivot_table(commit_data, all_month_years)
    username_map_df = create_username_map_df(username_to_author_map)

    # Use organization/project name from utils
    file = utils.get_unique_filename(utils.OUTPUT_FOLDER, f'{utils.ORG_NAME} Contribution Report', 'xlsx')
    write_report_excel(pivot_table, username_map_df, file)
    utils.print_line("Commit counts by username saved to", file)


if __name__ == '__main__':
    generate_commit_count_report()
