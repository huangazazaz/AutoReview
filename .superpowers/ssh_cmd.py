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
        capture_output=True, text=True, timeout=60, env=env,
        stdin=subprocess.DEVNULL
    )
    return result.stdout, result.stderr, result.returncode

cmd = sys.argv[1] if len(sys.argv) > 1 else 'echo "no command"'
try:
    out, err, rc = ssh(cmd)
    print(out)
    if err:
        print("STDERR:", err[:2000])
    print("RC:", rc)
finally:
    os.unlink(pw_script.name)
