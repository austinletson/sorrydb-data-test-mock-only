import subprocess
import os
import sys
from datetime import datetime

# Configuration
REPO_DIR = "/home/austin/development/lean/sorry-index/sorry-db-data-test-mock-only"
DOCKER_IMAGE = "sorrydb:latest"
DATABASE_FILE_PATH = "/data/sorry_database.json"
STATS_FILE_PATH = "/data/update_database_stats.json"
DEDUPLICATED_SORRIES_PATH = "/data/deduplicated_sorries.json"
LOG_DIR_IN_CONTAINER = "/data/logs"

def run_command(command, check=True, shell=False, cwd=None):
    """Helper function to run shell commands."""
    try:
        process = subprocess.run(command, check=check, shell=shell, text=True, capture_output=True, cwd=cwd)
        if process.stdout:
            print(process.stdout)
        if process.stderr:
            print(process.stderr, file=sys.stderr)
        return process
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(command) if isinstance(command, list) else command}", file=sys.stderr)
        print(f"Stdout: {e.stdout}", file=sys.stderr)
        print(f"Stderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        cmd_str = command[0] if isinstance(command, list) else command.split()[0]
        print(f"Error: Command '{cmd_str}' not found. Please ensure it is installed and in your PATH.", file=sys.stderr)
        sys.exit(1)

def handle_error(message):
    """Function to handle errors."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)

def main():
    # Change to the repository directory
    try:
        os.chdir(REPO_DIR)
    except FileNotFoundError:
        handle_error(f"Failed to change to repository directory: {REPO_DIR}")
    except Exception as e:
        handle_error(f"An unexpected error occurred while changing directory: {e}")

    # Get current timestamp
    current_time_dt = datetime.now()
    current_time_str = current_time_dt.strftime("%Y-%m-%dT%H:%M:%S")
    
    log_file_name = f"{current_time_str}_logs"
    log_file_container_path = f"{LOG_DIR_IN_CONTAINER}/{log_file_name}"

    print(log_file_name)

    print("Updating database...")
    # Run the Docker container
    docker_command = [
        "docker", "run",
        "--mount", f"type=bind,source={REPO_DIR},target=/data",
        DOCKER_IMAGE,
        "sh", "-c",
        (
            f"poetry run update_db --database-file {DATABASE_FILE_PATH} --stats-file {STATS_FILE_PATH} --log-file \"{log_file_container_path}\" --log-level DEBUG "
            f"&& poetry run deduplicate_db --database-file {DATABASE_FILE_PATH} --results-file {DEDUPLICATED_SORRIES_PATH} --log-file \"{log_file_container_path}\" --log-level DEBUG"
        )
    ]
    run_command(docker_command)

    print("Staging changes...")
    run_command(["git", "add", "."])

    # Check if there are changes to commit
    # `git diff --staged --quiet` exits with 0 if no changes, 1 if changes.
    # So, if it exits with non-zero (changes exist), we proceed.
    git_diff_process = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=REPO_DIR)
    
    if git_diff_process.returncode != 0:
        print("Committing changes...")
        commit_message = f"Updating SorryDB at {current_time_str}"
        run_command(["git", "commit", "-m", commit_message])

        print("Creating tag with today's date...")
        tag_date = current_time_dt.strftime("%Y-%m-%d")
        tag_message = f"Database update on {current_time_str}"
        run_command(["git", "tag", "-a", tag_date, "-m", tag_message])

        print("Pushing changes and tags...")
        run_command(["git", "push"])
        run_command(["git", "push", "--tags"])
        
        print("Successfully updated, committed, tagged, and pushed changes")
    else:
        print("No changes to commit")

if __name__ == "__main__":
    main()
