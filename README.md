# Commit Utils Project

## Overview

This project is designed to offer capabilities to extract GitHub data for an Organisation, including:

- Counting the total commits across an Organisations repositories
- Extracting a monthly contribution count for all contributors to all repositories for an Organisation
- Exporting all contributions for a particular contributor within an Organisation

It includes functionality for handling API requests, managing rate limits, and calculating execution time.

## Files

- `src/count_total_commits.py`: Contains the main logic for counting total commits.
- `src/utils/__init__.py`: Intended for utility functions or classes.
- `requirements.txt`: Lists the dependencies required for the project.
- `.env.template`: The global environment variables you need to set for the program to run. Should be renamed to .env and modifications ignored by git as it will contain sensitive information

## Setup Instructions

1. Clone the repository:

   ```bash
   git clone <repository-url>
   ```

2. Navigate to the project directory:

   ```bash
   cd commit-utils
   ```

3. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

To count the total commits in a GitHub repository, run the following command:

```bash
python src/count_total_commits.py
```

To export all commits by a given contributor, run the following command:

```bash
python src/export_all_commits_by_author.py
```

To export commit counts for all users each month from 1 Jan 2024 until now, run the following command:

```bash
python src/export_commit_count_by_authors.py
```

## License

This project is licensedto Leigh Dastey (<https://github.com/ldastey-dev>) under the MIT License.
