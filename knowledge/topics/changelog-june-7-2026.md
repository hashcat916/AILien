# AILIEN Changelog

_2026-06-07 19:25_


---

## Update — 2026-06-07 19:25


## Gaming System (6 tools, 163 total)

### New Gaming Tools
- detect_gaming_setup, list_games, launch_game, configure_gaming, check_gaming_setup, install_gaming_tool
- brain/gaming.py + tools/gaming_tools.py — Platform detection (Steam/Lutris/Heroic), game discovery, launching with GameMode/Gamescope/MangoHud/GPU offload

### Reasoning System (7 tools)
- think, create_plan, complete_step, list_plans, self_review, run_command, suggest_next_steps
- tools/reasoning_tools.py — Cognitive tools for structured thinking

### Agent Browser (4 tools)
- search_capabilities, install_capability, list_available_capabilities, find_missing_capability
- brain/agent_browser.py, tools/agent_browser_tools.py — Discover and install new capabilities from the web

### Course Builder (5 tools)
- build_course, generate_book, list_courses, read_lesson, find_tutorials
- brain/course_builder.py, tools/course_tools.py — Build offline learning courses from web tutorials

### Conversation Auto-Learner
- brain/conversation_learner.py — Auto-detects tech topics in conversations and saves to knowledge base

### Documentation
- README.md, ailien_startup.txt, changelog updated


**Current status**: 157 tools, 32 categories

---
_2026-06-07 19:24_


---

## Update — 2026-06-07 19:24


## Gaming System (6 tools, 163 total)

### New Gaming Tools
- detect_gaming_setup, list_games, launch_game, configure_gaming, check_gaming_setup, install_gaming_tool
- brain/gaming.py + tools/gaming_tools.py — Platform detection (Steam/Lutris/Heroic), game discovery, launching with GameMode/Gamescope/MangoHud/GPU offload

### Reasoning System (7 tools)
- think, create_plan, complete_step, list_plans, self_review, run_command, suggest_next_steps
- tools/reasoning_tools.py — Cognitive tools for structured thinking

### Agent Browser (4 tools)
- search_capabilities, install_capability, list_available_capabilities, find_missing_capability
- brain/agent_browser.py, tools/agent_browser_tools.py — Discover and install new capabilities from the web

### Course Builder (5 tools)
- build_course, generate_book, list_courses, read_lesson, find_tutorials
- brain/course_builder.py, tools/course_tools.py — Build offline learning courses from web tutorials

### Conversation Auto-Learner
- brain/conversation_learner.py — Auto-detects tech topics in conversations and saves to knowledge base

### OTHER CHANGES
- brain/learner.py, brain/toolmaker.py, tools/code_tools.py, tools/create_tool.py, tools/learn_tools.py — Added during development
- tools/lifestyle_tools.py, tools/utility_tools.py, tools/project_tools.py, tools/documentation_tools.py, tools/website_tools.py — Added
- tools/email_tool.py, tools/reminder_tools.py, tools/automation_tools.py, tools/feature_toggle.py — Added
- tools/media_tools.py, tools/torrent_tools.py, tools/display_tools.py, tools/browser_extras.py — Added
- tools/notes.py, tools/productivity.py, tools/server_tools.py, tools/domain_tools.py — Added
- skills/__init__.py — Fixed bug
- main.py — Updated imports and SYSTEM_PROMPT with all new sections
- README.md, ailien_startup.txt updated


**Current status**: 2 tools, 32 categories

---
_2026-06-07 19:22_


---

## Update — 2026-06-07 19:22


## New: Gaming System (6 new tools, 163+ total)

### Gaming Tools (tools/gaming_tools.py + brain/gaming.py)
- **detect_gaming_setup** — Scan system for Steam, Lutris, Heroic, Bottles, GameMode, MangoHud, Gamescope
- **list_games** — List installed games from Steam/Lutris/Heroic
- **launch_game** — Launch any game by name with GameMode/Gamescope/MangoHud/GPU offload
- **configure_gaming** — GameMode daemon, GPU power profiles, hybrid graphics switching
- **check_gaming_setup** — Comprehensive gaming health check with recommendations
- **install_gaming_tool** — Installation instructions for 8 gaming tools

### New files
- brain/gaming.py — Gaming engine: platform detection, game discovery, launching
- tools/gaming_tools.py — 6 tool wrappers

### Reasoning system (7 new tools)
- **think, create_plan, complete_step, list_plans, self_review, run_command, suggest_next_steps**
- tools/reasoning_tools.py — Cognitive tools for structured thinking

### Agent browser (4 new tools)
- **search_capabilities, install_capability, list_available_capabilities, find_missing_capability**
- brain/agent_browser.py, tools/agent_browser_tools.py

### Course builder (5 new tools)
- **build_course, generate_book, list_courses, read_lesson, find_tutorials**
- brain/course_builder.py, tools/course_tools.py

### Conversation auto-learner
- brain/conversation_learner.py — Auto-detects tech topics in chat and saves to knowledge base

### Documentation
- README.md, ailien_startup.txt updated with all new tools
- changelog updated with this entry


**Current status**: 2 tools, 32 categories

---
## New Tool Categories (20+ new tools, 87 total)

### System Fixes (The Big One)
- **`skills/__init__.py`** — Fixed the root cause of AILIEN not being able to control the computer. `execute_skill_tool()` returned `"Skill tool not found: {name}"` (a string) instead of `None`, blocking ALL built-in tools from ever executing. Changed to `return None` so built-in tools work.
- All 40+ tools (launch_app, open_url, take_screenshot, system_info, etc.) were blocked by this bug.

### Browser Tools (Firefox-targeted)
- All browser/media tools now use `xdotool` to send keystrokes **directly to Firefox** instead of the focused window
- **New**: `browser_search`, `browser_get_info`, `browser_click_link`, `browser_scroll`, `browser_fill_form`
- `browser_navigate`, `browser_find` rewritten to target Firefox directly

### Local Media Playback
- **New**: `play_media` — search for and play local movies/music by name
- **New**: `list_media` — browse media in ~/Music, ~/Videos, ~/Movies, ~/Downloads
- Auto-detects available player (celluloid > vlc > mpv > ffplay > xdg-open)
- Supports .mp3, .flac, .wav, .mp4, .mkv, .avi, .mov, .webm + 15+ formats

### Display Brightness
- **New**: `set_brightness`, `brightness_up`, `brightness_down`, `get_brightness`
- Uses `intel_backlight` sysfs for hardware brightness, falls back to `xrandr`

### Torrent Downloads
- **New**: `add_torrent`, `torrent_status`, `torrent_pause`, `torrent_resume`
- Uses `transmission-remote` to control the Transmission daemon
- Requires: `sudo apt-get install transmission-cli transmission-daemon`

### Productivity
- **New**: `calculate` (safe AST-based math), `translate` (free via LibreTranslate), `weather` (free via wttr.in)

### Notes (Knowledge Base)
- **New**: `take_note`, `list_notes`, `read_note`, `search_notes`, `delete_note`
- Notes saved to `knowledge/notes/` — persistent across sessions

### Email
- **New**: `compose_email` — opens email client with pre-filled fields

### Code Tools
- **New**: `check_python_syntax`, `run_project_tests`, `format_python`, `self_verify`
- `self_verify` checks syntax + runs pytest in one step

## Reminders, Timers & Automation

### Unified Reminder/Timer System
- **New**: `set_reminder`, `set_timer`, `list_reminders`, `cancel_reminder` tools
- Now delegates to `brain/reminders.py` ReminderManager (persistent, background thread)
- **Removed** the old standalone timer from `tools/productivity.py` (duplicate)
- Timers and reminders now persist in `.cache/reminders.json` across restarts

### Automation Engine (`brain/automation.py`)
- **New**: Schedule tools to run automatically on three schedule types:
  - `interval` — every N seconds (min 30)
  - `daily` — at a specific time each day
  - `hourly` — at a specific minute past each hour
- Uses background thread checking every 15 seconds
- Persists automations to `.cache/automations.json`
- **Tools**: `add_automation`, `list_automations`, `remove_automation`, `pause_automation`, `resume_automation`, `pause_all_automations`, `resume_all_automations`
- **Safety**: Automations cannot run dangerous tools (blocks anything requiring confirmation)

### Feature Toggles
- **New**: `toggle_proactive_monitoring` — turn battery/CPU alerts on/off at runtime
- **New**: `toggle_automation` — pause/resume all automations at once
- **New**: `get_feature_status` — check what background features are running

## Noise Reduction
- Console logger now only shows WARNING+ (no startup spam, no "conversation saved" noise)
- File logger still writes full INFO logs to `.cache/agent.log` for debugging
- Desktop `notify()` popups only in `--daemon` mode (not in terminal modes)
- Tray icon only in `--daemon` mode (was causing GLib-CRITICAL errors)
- Wake word detector disabled in text/freebuff modes (saves CPU)

## Documentation Updated
- **README.md** — Full rewrite with all 87 tools, correct project structure, xAI as primary API, all config vars, feature descriptions
- **START_HERE.md** — Updated with all modes, example commands, automation/reminders/toggles
- **ailien_startup.txt** — Complete reference with tool categories, voice commands, all launch modes
- **setup.sh** — Updated for xAI (not Groq), installs transmission-cli, current desktop shortcuts

## Files Modified (summary)
- `skills/__init__.py` — THE BUG FIX
- `main.py` — 4 tool imports, `_init_automation()`, SYSTEM_PROMPT with 4 new sections, shutdown hooks
- `tools/system.py` — `_send_key_to_window()` helper, media keys target Firefox
- `tools/browser.py` — All browser tools use xdotool to target Firefox
- `tools/productivity.py` — Removed duplicate standalone timer
- `README.md`, `START_HERE.md`, `ailien_startup.txt`, `setup.sh` — Full documentation rewrite
- `utils/helpers.py` — Console logging at WARNING, file logging at INFO

## New Files Created
- `tools/browser_extras.py` — browser_click_link, browser_search, browser_scroll, browser_get_info, browser_fill_form
- `tools/display_tools.py` — set_brightness, brightness_up/down, get_brightness
- `tools/media_tools.py` — play_media, list_media
- `tools/torrent_tools.py` — add_torrent, torrent_status/pause/resume
- `tools/productivity.py` — calculate, translate, weather, clipboard_history
- `tools/notes.py` — take_note, list_notes, read_note, search_notes, delete_note
- `tools/email_tool.py` — compose_email
- `tools/code_tools.py` — check_python_syntax, run_project_tests, format_python, self_verify
- `tools/reminder_tools.py` — set_reminder, set_timer, list_reminders, cancel_reminder
- `tools/automation_tools.py` — add/list/remove/pause/resume automations
- `tools/feature_toggle.py` — toggle_proactive_monitoring, toggle_automation, get_feature_status
- `brain/automation.py` — AutomationEngine with interval/daily/hourly scheduling