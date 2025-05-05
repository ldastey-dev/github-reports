import os
import time
import ctypes
import platform
import requests
import subprocess
from datetime import datetime
from dotenv import load_dotenv
import base64


# Setup environment variables
load_dotenv()

# Common settings
ORG_NAME = os.getenv('ORG_NAME')
START_DATE = os.getenv('START_DATE')
GIT_PROVIDER = os.getenv('GIT_PROVIDER', 'github').lower()  # Default to GitHub if not specified

# GitHub specific settings
GITHUB_BASE_URL = os.getenv('GITHUB_BASE_URL', 'https://api.github.com')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# ADO specific settings
ADO_BASE_URL = os.getenv('ADO_BASE_URL')  # e.g., https://dev.azure.com/organization
ADO_PROJECT = os.getenv('ADO_PROJECT')
ADO_USERNAME = os.getenv('ADO_USERNAME')
ADO_PAT = os.getenv('ADO_PAT')  # Personal Access Token

# Set provider-specific variables based on GIT_PROVIDER
if GIT_PROVIDER == 'ado':
    BASE_URL = ADO_BASE_URL
    ORG_NAME = ADO_PROJECT
    print_prefix = f"[ADO: {ADO_PROJECT}]"
else:  # Default to GitHub
    BASE_URL = GITHUB_BASE_URL
    print_prefix = f"[GitHub: {ORG_NAME}]"

# Set output folder based on organization name
OUTPUT_FOLDER = f"output/{ORG_NAME}"

# Authentication headers for GitHub
github_headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'
}

# Authentication headers for ADO
if ADO_USERNAME and ADO_PAT:
    encoded_credentials = base64.b64encode(f"{ADO_USERNAME}:{ADO_PAT}".encode()).decode()
    ado_headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'
    }

# Set the appropriate headers based on the provider
headers = ado_headers if GIT_PROVIDER == 'ado' else github_headers


# Custom print function to ensure proper line breaks and carriage returns
def print_line(*args, **kwargs):
    # Add provider prefix to all output messages
    if len(args) > 0:
        args = (f"{print_prefix} {args[0]}",) + args[1:]
    
    kwargs['end'] = '\n\r'
    kwargs['flush'] = True
    print(*args, **kwargs)


# Prevent the system from sleeping
def disable_system_sleep():
    if (platform.system() == "Windows" and 
        "microsoft" not in platform.uname().release.lower()):
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001) 
    elif platform.system() == "Linux":
        try:
            subprocess.Popen([
                'sudo', 'systemd-inhibit', '--what=handle-lid-switch', 
                '--why="Running Python program"', 'sleep', 'infinity'
            ])
        except Exception as e:
            print_line(f"Failed to inhibit sleep: {e}")


# Allow the system to sleep
def enable_system_sleep():
    if (platform.system() == "Windows" and 
        "microsoft" not in platform.uname().release.lower()):
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    elif platform.system() == "Linux":
        try:
            subprocess.Popen(['sudo', 'pkill', '-f', 'systemd-inhibit'])
        except Exception as e:
            print_line(f"Failed to allow sleep: {e}")


# Decoration wrapper to calculate total execution time
def calculate_execution_time(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            disable_system_sleep()
            result = func(*args, **kwargs)
        except Exception as e:
            print_line(f"Error: {e}")
            result = None
        finally:
            end_time = time.time()
            execution_time = end_time - start_time
            
            print_line(f"Execution time: {execution_time:.2f} seconds")
            
            enable_system_sleep()
        
        return result

    return wrapper


# Rate limit handling ... make sure we stay on the right side of forbidden 
def handle_rate_limit(response):
    remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))

    if remaining == 0:
        sleep_time = max(0, reset_time - time.time())
        reset_dt = datetime.utcfromtimestamp(reset_time)
        reset_time_converted = reset_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        print_line(f'Rate limit exceeded. Reset time: {reset_time_converted}. Sleeping for {sleep_time / 60} minutes.')
        
        time.sleep(sleep_time)


# Generate a unique file name so subsequent runs don't overwrite local edits!
def get_unique_filename(folder, fname, extension):
    counter = 1

    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = f'{os.path.join(base_dir, '..', '..')}/{folder}'
    
    file = f"{path}/{fname}.{extension}"

    os.makedirs(path, exist_ok=True)

    while os.path.exists(file):
        file = f"{path}/{fname}_{counter}.{extension}"
        counter += 1
    return file


# Retrieve all repositories for the organisation - GitHub specific implementation
def get_github_repositories(org_name):
    page = 1
    repos = []

    while True:
        url = f'{GITHUB_BASE_URL}/orgs/{org_name}/repos?page={page}&per_page=100'

        response = requests.get(url, headers=github_headers)
        handle_rate_limit(response)

        if response.status_code != 200:
            print_line(f'Error fetching GitHub repositories: {response.status_code}')
            break

        data = response.json()
        if not data:
            break
        
        repos.extend(data)
        page += 1

    return repos


# Retrieve all repositories for the project - ADO specific implementation
def get_ado_repositories(org_name, project_name):
    # ADO API uses a different endpoint structure
    url = f'{ADO_BASE_URL}/{org_name}/{project_name}/_apis/git/repositories?api-version=6.0'
    
    response = requests.get(url, headers=ado_headers)
    
    if response.status_code != 200:
        print_line(f'Error fetching ADO repositories: {response.status_code} - {response.text}')
        return []
    
    data = response.json()
    
    # ADO returns repositories in a different structure than GitHub
    if 'value' in data:
        return data['value']
    
    return []


# Get repository commits from ADO
def get_ado_repository_commits(repository_id, start_date, end_date):
    # Convert dates to ISO format if needed
    commits = []
    page_size = 100
    skip = 0
    
    while True:
        # ADO pagination works differently than GitHub
        url = (f'{ADO_BASE_URL}/{ORG_NAME}/{ADO_PROJECT}/_apis/git/repositories/{repository_id}/commits'
               f'?searchCriteria.fromDate={start_date}'
               f'&searchCriteria.toDate={end_date}'
               f'&searchCriteria.$skip={skip}'
               f'&searchCriteria.$top={page_size}'
               f'&api-version=6.0')
        
        response = requests.get(url, headers=ado_headers)
        
        if response.status_code != 200:
            print_line(f'Error fetching ADO commits: {response.status_code} - {response.text}')
            break
        
        data = response.json()
        
        if not data.get('value'):
            break
            
        # Transform ADO commit format to match GitHub format for consistency
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
                    'login': commit['author']['name']  # ADO doesn't have username like GitHub, using name
                }
            }
            commits.append(github_style_commit)
        
        # ADO will return fewer items than page_size when we've reached the end
        if len(data['value']) < page_size:
            break
            
        skip += page_size
    
    return commits


# Generic repository retrieval function that delegates to the appropriate implementation
def get_repositories(org_name=None, project_name=None):
    org_name = org_name or ORG_NAME
    project_name = project_name or ADO_PROJECT
    
    if GIT_PROVIDER == 'ado':
        return get_ado_repositories(org_name, project_name)
    else:
        return get_github_repositories(org_name)


# Generic function to get commits for a repository
def get_commits(repository, start_date, end_date):
    if GIT_PROVIDER == 'ado':
        # For ADO, repository is expected to be a dict with repositoryId
        repository_id = repository['id']
        return get_ado_repository_commits(repository_id, start_date, end_date)
    else:
        # For GitHub, use existing implementation
        return get_commits_for_repository(repository['name'], start_date, end_date)


# GitHub-specific implementation (existing function)
def get_commits_for_repository(repository, start_date, end_date):
    page = 1
    commits = []

    while True:
        url = f'{GITHUB_BASE_URL}/repos/{ORG_NAME}/{repository}/commits?since={start_date}&until={end_date}&page={page}&per_page=100'

        response = requests.get(url, headers=github_headers)
        handle_rate_limit(response)

        if response.status_code != 200:
            print_line(f'Error fetching commits for {repository}: {response.status_code}')
            break

        data = response.json()
        if not data:
            break

        commits.extend(data)
        page += 1

    return commits
