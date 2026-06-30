import subprocess, os, tempfile, sys

password = sys.argv[1] if len(sys.argv) > 1 else "hhelibeb123'"
host = sys.argv[2] if len(sys.argv) > 2 else "root@39.106.56.174"

# Write password script
pw_script = tempfile.NamedTemporaryFile(delete=False, suffix='.py', mode='w')
pw_script.write('#!/usr/bin/env python\nprint("' + password + '")')
pw_script.close()
os.chmod(pw_script.name, 0o700)

env = os.environ.copy()
env['SSH_ASKPASS'] = pw_script.name
env['DISPLAY'] = ':0'
env['SSH_ASKPASS_REQUIRE'] = 'force'

try:
    result = subprocess.run(
        ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=10',
         '-o', 'PreferredAuthentications=password',
         host, 'echo CONNECTED && hostname && git --version'],
        capture_output=True, text=True, timeout=20, env=env,
        stdin=subprocess.DEVNULL
    )
    print('STDOUT:', result.stdout)
    print('STDERR:', result.stderr[:500] if result.stderr else '')
    print('RC:', result.returncode)
finally:
    os.unlink(pw_script.name)
