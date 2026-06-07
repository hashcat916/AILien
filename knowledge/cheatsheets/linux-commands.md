# Linux Command Cheatsheet

## File Operations
- `ls -la` — List all files with details
- `find . -name "*.py"` — Find files by name
- `grep -r "pattern" .` — Search text in files
- `du -sh *` — Show directory sizes
- `df -h` — Show disk usage

## Process Management
- `ps aux` — List all processes
- `top` / `htop` — Interactive process viewer
- `kill -9 PID` — Force kill a process
- `killall name` — Kill all processes by name

## Network
- `ip a` — Show network interfaces
- `ping host` — Test connectivity
- `ss -tuln` — Show listening ports
- `curl ifconfig.me` — Get public IP
