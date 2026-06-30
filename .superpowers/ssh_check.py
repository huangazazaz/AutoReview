import subprocess, os, tempfile, sys

password = "hhelibeb123'"
host = "root@39.106.56.174"

pw_script = tempfile.NamedTemporaryFile(delete=False, suffix='.py', mode='w')
pw_script.write('#!/usr/bin/env python\nprint("' + password + '")')
pw_script.close()
os.chmod(pw_script.name, 0o700)

env = os.environ.copy()
env['SSH_ASKPASS'] = pw_script.name
env['DISPLAY'] = ':0'
env['SSH_ASKPASS_REQUIRE'] = 'force'

def ssh(cmd):
    result = subprocess.run(
        ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=10',
         '-o', 'PreferredAuthentications=password',
         host, cmd],
        capture_output=True, text=True, timeout=30, env=env,
        stdin=subprocess.DEVNULL
    )
    return result.stdout, result.stderr, result.returncode

try:
    # Check GitHub SSH
    out, err, rc = ssh('ssh -o StrictHostKeyChecking=no -T git@github.com 2>&1')
    print("=== GitHub SSH ===")
    print(out, err[:300] if err else '')

    # Check if repo exists
    out, err, rc = ssh('ls -la /root/AutoReview 2>&1 || echo "not found"')
    print("=== Repo check ===")
    print(out)

    # Check git config on server
    out, err, rc = ssh('cat ~/.gitconfig 2>/dev/null || echo "no gitconfig"')
    print("=== Git config ===")
    print(out)

finally:
    os.unlink(pw_script.name)
