import subprocess
import tomllib

with open("pyproject.toml", "rb") as f:
    config = tomllib.load(f)

exit(subprocess.run(config["tool"]["esbonio"]["sphinx"]["buildCommand"]).returncode)
