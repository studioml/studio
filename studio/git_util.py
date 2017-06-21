import os
import subprocess


def get_git_info(path='.', abort_dirty=True):

    info = {}
    if not is_git(path):
        return None

    if abort_dirty and not is_git_clean(path):
        return None

    info['url'] = get_git_repo_url(path)
    info['commit'] = get_git_commit(path)


def is_git(path='.'):
    p = subprocess.Popen(['git','status'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    
    p.wait()
    return (p.returncode == 0)

def is_git_clean(path='.'):
    p = subprocess.Popen(['git','status', '-s'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    
    stdout,_ = p.communicate()
    return (stdout.strip() == '')


