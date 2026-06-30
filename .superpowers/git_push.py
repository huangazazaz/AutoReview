import subprocess, os, tempfile, sys

password = "hhelibeb123'"
host = "root@39.106.56.174"

# Write the password provider
pw_script = tempfile.NamedTemporaryFile(delete=False, suffix='.py', mode='w')
pw_script.write('#!/usr/bin/env python\nprint("' + password + '")')
pw_script.close()
os.chmod(pw_script.name, 0o700)

env = os.environ.copy()
env['SSH_ASKPASS'] = pw_script.name
env['DISPLAY'] = ':0'
env['SSH_ASKPASS_REQUIRE'] = 'force'
env['GIT_SSH_COMMAND'] = 'ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password'

try:
    # Add remote
    subprocess.run(['git', 'remote', 'add', 'server', f'ssh://{host}/root/repos/AutoReview.git'],
                   capture_output=True, timeout=10)
    
    # Push to server
    result = subprocess.run(
        ['git', 'push', '-u', 'server', 'dev/autotrade-mvp'],
        capture_output=True, text=True, timeout=60, env=env,
        stdin=subprocess.DEVNULL
    )
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr[:1000] if result.stderr else '')
    print("RC:", result.returncode)
finally:
    os.unlink(pw_script.name)
