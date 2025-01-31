import os
import time
import ctypes
import platform
import requests
import subprocess
from datetime import datetime
from dotenv import load_dotenv


# Setup environment variables
load_dotenv()

BASE_URL = os.getenv('BASE_URL')
ORG_NAME = os.getenv('ORG_NAME')

OUTPUT_FOLDER = 'output'
# 


# Authentication headers
# Using Chrome user agent to fly low and avoid the radar :)
headers = {
    'Authorization': f'token {os.getenv("GITHUB_TOKEN")}',
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'
}


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
            print(f"Failed to inhibit sleep: {e}")


# Allow the system to sleep
def enable_system_sleep():
    if (platform.system() == "Windows" and 
        "microsoft" not in platform.uname().release.lower()):
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    elif platform.system() == "Linux":
        try:
            subprocess.Popen(['sudo', 'pkill', '-f', 'systemd-inhibit'])
        except Exception as e:
            print(f"Failed to allow sleep: {e}")


# Decoration wrapper to calculate total execution time
def calculate_execution_time(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            disable_system_sleep()
            result = func(*args, **kwargs)
        except Exception as e:
            print(f"Error: {e}")
            result = None
        finally:
            end_time = time.time()
            execution_time = end_time - start_time
            
            print(f"Execution time: {execution_time:.2f} seconds")
            
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
        
        print(f'Rate limit exceeded. Reset time: {reset_time_converted}.\nSleeping for {sleep_time / 60} minutes.')
        
        time.sleep(sleep_time)


# Generate a unique file name so subsequent runs don't overwrite local edits!
def get_unique_filename(folder, fname, extension):
    counter = 1
    file = f"{folder}/{fname}.{extension}"

    os.makedirs(folder, exist_ok=True)

    while os.path.exists(file):
        file = f"{folder}/{fname}_{counter}.{extension}"
        counter += 1
    return file


# Retrieve all repositories for the organisation
def get_repositories(org_name):
    page = 1
    repos = []

    while True:
        url = f'{BASE_URL}/orgs/{org_name}/repos?page={page}&per_page=100'

        response = requests.get(url, headers=headers)
        handle_rate_limit(response)

        if response.status_code != 200:
            print(f'Error fetching repositories: {response.status_code}')
            break

        data = response.json()
        if not data:
            break
        
        repos.extend(data)
        page += 1

    return repos
