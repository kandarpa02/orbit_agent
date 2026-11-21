# ORBIT

ORBIT is a tool-using assistant with web research, browser, filesystem, and
command capabilities.

## Python tasks

ORBIT can run focused Python scripts for tasks not covered by dedicated tools.
Each task gets a temporary Python virtual environment. Scripts have the same
host filesystem permissions and network access as the ORBIT process; a virtual
environment isolates packages, not operating-system access. ORBIT environment
variables are not passed to task scripts.

Task outputs are saved in ORBIT's persistent `python_tasks` workspace and are
available to ORBIT's file tools. Python scripts run with `python_tasks` as
their current directory, so use `file.jpg` in a script and
`python_tasks/file.jpg` with ORBIT's file tools. Packages installed during a
task are temporary to that task.

Use ORBIT's `delete_file` tool to remove a workspace file. It accepts a
workspace-relative or absolute path and refuses paths outside the workspace.
For an explicitly requested directory-tree deletion, use `delete_directory`;
it recursively deletes the selected directory but refuses the workspace root.

The existing `execute_command` tool runs on the host and is not an OS sandbox.
Use it only when host command execution is explicitly intended.
