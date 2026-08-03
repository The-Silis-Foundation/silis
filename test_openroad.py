import subprocess
p = subprocess.Popen("openroad -no_init", shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
p.stdin.write("puts hello\nputs world\nexit\n")
p.stdin.flush()
print(p.stdout.read())
