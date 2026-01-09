# F1re Claude Watchdog 🤖🐕

**Intelligent service monitoring powered by Claude Agent SDK**

F1re Claude Watchdog is an autonomous AI-powered watchdog that monitors your services and uses Claude as an intelligent agent to diagnose and fix issues automatically. When simple restarts fail, Claude springs into action—analyzing logs, identifying root causes, applying fixes, and notifying you via Telegram.

## Features

- 🔄 **Automatic service monitoring** with configurable health checks
- 🤖 **AI-powered recovery** using Claude Agent SDK
- 📱 **Telegram notifications** with detailed recovery reports
- 🔧 **Multi-platform support** (macOS launchd, Linux systemd, custom commands)
- 🛠️ **Autonomous troubleshooting** - Claude reads logs, applies fixes, verifies recovery
- 📊 **Detailed diagnostics** - port checks, log analysis, custom health checks

## How It Works

1. **Health Monitoring**: Periodically checks if your services are running (every 30s by default)
2. **Simple Restarts**: Attempts automatic restarts (3 attempts by default)
3. **AI Agent Activation**: If restarts fail, invokes Claude as an autonomous agent
4. **Intelligent Recovery**: Claude:
   - Gathers service diagnostics
   - Analyzes error logs
   - Identifies root cause
   - Applies fixes (clear caches, fix permissions, update config, etc.)
   - Verifies service health
   - Sends detailed Telegram notification
5. **Continuous Monitoring**: Returns to monitoring after recovery

## Installation

### Prerequisites

- Python 3.8+
- [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview)
- Claude Pro/Max subscription (for session auth) OR Anthropic API key

### Install Dependencies

```bash
# Install Claude Agent SDK
pip3 install --break-system-packages claude-agent-sdk requests

# Authenticate with Claude (if using session auth)
brew install claude-code
claude auth
```

### Setup

1. **Clone this repository**:
   ```bash
   cd ~/workspace
   git clone https://github.com/f1rede/F1reClaudeWatchdog.git
   cd F1reClaudeWatchdog
   ```

2. **Create configuration**:
   ```bash
   cp config.example.json config.json
   # Edit config.json with your services and Telegram credentials
   ```

3. **Configure Telegram**:
   - Create a bot via [@BotFather](https://t.me/BotFather)
   - Get your chat ID from [@userinfobot](https://t.me/userinfobot)
   - Add to `config.json` or set as environment variables

## Configuration

### config.json Structure

```json
{
  "check_interval": 30,
  "max_simple_restarts": 3,
  "telegram_bot_token": "YOUR_BOT_TOKEN",
  "telegram_chat_id": "YOUR_CHAT_ID",
  "services": {
    "my_service": {
      // Service configuration options...
    }
  }
}
```

### Service Configuration Options

#### macOS (launchd)
```json
"my_service": {
  "launchd_label": "com.example.my-service",
  "port": 8080,
  "log_file": "/Users/me/.my-service/error.log"
}
```

#### Linux (systemd)
```json
"my_service": {
  "systemd_unit": "my-service.service",
  "port": 3000,
  "log_file": "/var/log/my-service/error.log"
}
```

#### Custom Commands
```json
"my_service": {
  "health_check_command": "curl -f http://localhost:8080/health",
  "restart_command": "~/scripts/restart-service.sh",
  "log_file": "/var/log/my-service.log"
}
```

### Configuration Fields

| Field | Type | Description |
|-------|------|-------------|
| `check_interval` | int | Seconds between health checks (default: 30) |
| `max_simple_restarts` | int | Restart attempts before invoking AI (default: 3) |
| `telegram_bot_token` | string | Telegram bot token from @BotFather |
| `telegram_chat_id` | string | Your Telegram chat ID |
| `services` | object | Dictionary of services to monitor |

### Service Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `launchd_label` | string | macOS | launchd service label |
| `systemd_unit` | string | Linux | systemd unit name |
| `port` | int | optional | Port to check for listening status |
| `log_file` | string | optional | Path to service log file |
| `health_check_command` | string | optional | Custom health check command |
| `restart_command` | string | optional | Custom restart command |

## Usage

### Run Manually

```bash
cd ~/workspace/F1reClaudeWatchdog
python3 watchdog.py
```

### Run as a Service (macOS)

Create `~/Library/LaunchAgents/com.f1re.claude-watchdog.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.f1re.claude-watchdog</string>
  
  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/python3</string>
    <string>/Users/YOUR_USERNAME/workspace/F1reClaudeWatchdog/watchdog.py</string>
  </array>
  
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>TELEGRAM_BOT_TOKEN</key>
    <string>YOUR_BOT_TOKEN</string>
    <key>TELEGRAM_CHAT_ID</key>
    <string>YOUR_CHAT_ID</string>
  </dict>
  
  <key>WorkingDirectory</key>
  <string>/Users/YOUR_USERNAME/workspace/F1reClaudeWatchdog</string>
  
  <key>RunAtLoad</key>
  <true/>
  
  <key>KeepAlive</key>
  <true/>
  
  <key>StandardOutPath</key>
  <string>/Users/YOUR_USERNAME/.claude-watchdog/watchdog.log</string>
  
  <key>StandardErrorPath</key>
  <string>/Users/YOUR_USERNAME/.claude-watchdog/watchdog.error.log</string>
</dict>
</plist>
```

Load the service:
```bash
launchctl load ~/Library/LaunchAgents/com.f1re.claude-watchdog.plist
```

### Run as a Service (Linux systemd)

Create `/etc/systemd/system/claude-watchdog.service`:

```ini
[Unit]
Description=F1re Claude Watchdog
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/workspace/F1reClaudeWatchdog
ExecStart=/usr/bin/python3 /home/YOUR_USERNAME/workspace/F1reClaudeWatchdog/watchdog.py
Restart=always
RestartSec=10
Environment="TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN"
Environment="TELEGRAM_CHAT_ID=YOUR_CHAT_ID"

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable claude-watchdog
sudo systemctl start claude-watchdog
sudo systemctl status claude-watchdog
```

## Authentication

### Option 1: Session Auth (Recommended for Pro/Max users)

```bash
brew install claude-code
claude auth
```

The watchdog will automatically use your Claude Pro/Max session credentials.

### Option 2: API Key

Set the `ANTHROPIC_API_KEY` environment variable:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

Or add to your LaunchAgent/systemd plist/service file.

## Logs

- **Watchdog logs**: `~/.claude-watchdog/watchdog.log`
- **Error logs**: `~/.claude-watchdog/watchdog.error.log`

## Example Telegram Notification

When Claude recovers a service, you'll receive a message like:

```
🔧 Service Recovery Report

Service: gateway
Status: ✅ Recovered

Root Cause:
Context overflow - session file grew to 2.8MB exceeding 200K token limit

Actions Taken:
- Archived large session files
- Cleared session registry
- Restarted gateway service
- Verified port 18789 is listening

Recovery Time: 45 seconds
```

## Architecture

### Custom Tools

The watchdog provides Claude with two custom tools:

1. **`get_service_info`**: Gathers comprehensive diagnostics
   - Process status (launchd/systemd)
   - Port listening status
   - Recent error logs
   - Custom health check output

2. **`send_telegram`**: Sends notifications to Telegram
   - Markdown formatting support
   - Error handling

### Built-in SDK Tools

Claude also has access to:
- **Bash**: Execute commands to fix issues
- **Read**: Read configuration files
- **Edit**: Modify config files
- **Glob**: Find relevant files

## Extending

### Add Custom Diagnostic Logic

Edit the `get_service_info_tool` function in `watchdog.py` to add service-specific diagnostics.

### Add More Tools

Create new `@tool` decorated functions:

```python
@tool(
    name="my_custom_tool",
    description="Does something useful",
    input_schema={"param": str}
)
async def my_custom_tool(inputs: Dict[str, Any]) -> Dict[str, Any]:
    # Your logic here
    return {"content": "result"}
```

Add to the `custom_tools` list in `invoke_agent()`.

## Troubleshooting

### Watchdog not starting
- Check Python path in LaunchAgent/systemd config
- Verify `claude-agent-sdk` is installed: `pip3 list | grep claude`
- Check error logs: `tail -f ~/.claude-watchdog/watchdog.error.log`

### Telegram notifications not working
- Verify bot token: test with `curl https://api.telegram.org/bot<TOKEN>/getMe`
- Check chat ID is correct (negative for groups)
- Ensure `requests` package is installed

### Claude agent errors
- Check authentication: `claude auth status` (for session auth)
- Verify API key if using API auth
- Check logs for detailed error messages

## Contributing

Contributions welcome! Please open issues or PRs on GitHub.

## License

MIT License - see LICENSE file for details

## Credits

Created by [f1rede](https://github.com/f1rede)

Built with [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview)

---

**Made with 🔥 and 🤖 by F1re**
