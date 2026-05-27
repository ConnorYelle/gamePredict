#!/usr/bin/env python3
"""Install a git post-commit hook that updates README metrics on each commit.

Run this once to install the hook: `python scripts/install_git_hook.py`
"""
import os
import stat
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
HOOK_PATH = os.path.join(ROOT, '.git', 'hooks', 'post-commit')
HOOK_CONTENT = r'''#!/usr/bin/env python3
import sys, os, subprocess
ROOT = os.path.dirname(os.path.dirname(__file__))
script = os.path.join(ROOT, 'scripts', 'update_readme_metrics.py')
try:
    subprocess.run([sys.executable, script], check=True)
except Exception:
    # don't block commit on failure
    pass
'''


def install():
    git_hooks_dir = os.path.dirname(HOOK_PATH)
    if not os.path.exists(os.path.join(ROOT, '.git')):
        print('No .git directory found at repo root; cannot install hook.')
        sys.exit(1)

    with open(HOOK_PATH, 'w', encoding='utf-8') as f:
        f.write(HOOK_CONTENT)

    # make executable
    try:
        st = os.stat(HOOK_PATH)
        os.chmod(HOOK_PATH, st.st_mode | stat.S_IEXEC)
    except Exception:
        pass

    print('Installed git post-commit hook at', HOOK_PATH)


if __name__ == '__main__':
    install()
