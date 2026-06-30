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
        capture_output=True, text=True, timeout=60, env=env,
        stdin=subprocess.DEVNULL
    )
    return result.stdout, result.stderr, result.returncode

try:
    # Push from server to GitHub
    out, err, rc = ssh(
        'cd /root/repos/AutoReview.git && '
        'git remote add github git@github.com:huangazazaz/AutoReview.git 2>/dev/null; '
        'git push github dev/autotrade-mvp'
    )
    print("STDOUT:", out)
    print("STDERR:", err[:1000] if err else '')
    print("RC:", rc)
finally:
    os.unlink(pw_script.name)
