# Python Quick Reference

## Common Snippets
- Read a file: `open('file.txt').read()`
- List comprehension: `[x*2 for x in range(10)]`
- Lambda: `lambda x: x * 2`
- Type hint: `def greet(name: str) -> str:`

## Useful Libraries
- `requests` — HTTP requests
- `rich` — Beautiful terminal output
- `pyautogui` — Mouse/keyboard automation
- `psutil` — System monitoring
- `PIL/Pillow` — Image processing

## Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
