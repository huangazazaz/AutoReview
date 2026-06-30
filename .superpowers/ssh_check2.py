import subprocess, os, tempfile

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
    out, err, rc = ssh('ls -la ~/.ssh/ 2>/dev/null && echo "---" && cat ~/.ssh/id_*.pub 2>/dev/null || echo "no ssh keys"')
    print("=== SSH Keys ===")
    print(out)
    
    # Also check if git credential helper is configured
    out, err, rc = ssh('git config --global credential.helper 2>/dev/null || echo "no credential helper"')
    print("=== Credential helper ===")
    print(out)
finally:
    os.unlink(pw_script.name)
