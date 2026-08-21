import os
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple


def get_git_repos(directory: str) -> List[Path]:
    """
    Find all git repositories in a directory.
    
    :param directory: Root directory to search
    :return: List of paths to git repositories
    """
    repos = []
    for root, dirs, files in os.walk(directory):
        if '.git' in dirs:
            repos.append(Path(root))
            dirs[:] = []
        else:
            dirs[:] = [d for d in dirs if not d.startswith('.')]
    return repos


def get_local_branches(repo_path: Path) -> Set[str]:
    """
    Get all local branches in a repository.
    
    :param repo_path: Path to the git repository
    :return: Set of local branch names
    """
    try:
        result = subprocess.run(
            ['git', 'branch', '-a'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return set()
        
        branches = set()
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                branch = line.strip()
                if branch.startswith('* '):
                    branch = branch[2:]
                if not branch.startswith('remotes/'):
                    branches.add(branch)
        return branches
    except Exception as e:
        print(f"Error getting local branches for {repo_path}: {e}")
        return set()


def get_remote_branches(repo_path: Path) -> Set[str]:
    """
    Get all remote branches in a repository.
    
    :param repo_path: Path to the git repository
    :return: Set of remote branch names (without remote prefix)
    """
    try:
        result = subprocess.run(
            ['git', 'branch', '-r'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return set()
        
        branches = set()
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                branch = line.strip()
                if branch.startswith('* '):
                    branch = branch[2:]
                if '->' not in branch:
                    parts = branch.split('/')
                    if len(parts) > 1:
                        branch_name = '/'.join(parts[1:])
                        branches.add(branch_name)
        return branches
    except Exception as e:
        print(f"Error getting remote branches for {repo_path}: {e}")
        return set()


def assess_branches(directory: str) -> Dict[str, Dict]:
    """
    Assess all branches across repositories in a directory.
    
    :param directory: Root directory containing git repositories
    :return: Dictionary with repo paths as keys and branch info as values
    """
    repos = get_git_repos(directory)
    results = {}
    
    for repo_path in sorted(repos):
        local_branches = get_local_branches(repo_path)
        remote_branches = get_remote_branches(repo_path)
        
        only_local = local_branches - remote_branches
        only_remote = remote_branches - local_branches
        
        results[str(repo_path)] = {
            'local_branches': sorted(local_branches),
            'remote_branches': sorted(remote_branches),
            'only_local': sorted(only_local),
            'only_remote': sorted(only_remote),
        }
    
    return results


def print_branch_report(directory: str) -> None:
    """
    Print a formatted report of branches across repositories.
    
    :param directory: Root directory containing git repositories
    """
    results = assess_branches(directory)
    
    if not results:
        print(f"No git repositories found in {directory}")
        return
    
    print(f"\n{'='*80}")
    print(f"Branch Assessment Report for: {directory}")
    print(f"{'='*80}\n")
    
    for repo_path, info in results.items():
        print(f"Repository: {repo_path}")
        print(f"  Local branches ({len(info['local_branches'])}): {', '.join(info['local_branches']) if info['local_branches'] else 'None'}")
        print(f"  Remote branches ({len(info['remote_branches'])}): {', '.join(info['remote_branches']) if info['remote_branches'] else 'None'}")
        
        if info['only_local']:
            print(f"  ⚠️  Only local (not on remote): {', '.join(info['only_local'])}")
        
        if info['only_remote']:
            print(f"  ℹ️  Only remote (not local): {', '.join(info['only_remote'])}")
        
        print()
