#!/usr/bin/env python3
"""
F1re Claude Watchdog - Intelligent service monitoring with Claude Agent SDK
Monitors services and uses Claude as an autonomous agent to diagnose and fix issues
"""

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

from claude_agent_sdk import query, ClaudeAgentOptions, tool, create_sdk_mcp_server

# Configuration - can be overridden via config.json
DEFAULT_CONFIG = {
    "check_interval": 30,  # seconds between health checks
    "max_simple_restarts": 3,  # attempts before invoking AI agent
    "update_check_interval": 14400,  # 4 hours in seconds
    "services": {
        # Example service configuration
        # "my_service": {
        #     "launchd_label": "com.example.my-service",
        #     "port": 8080,
        #     "log_file": "/var/log/my-service.log"
        # }
    },
    "repositories": {
        # Example repository configuration for auto-updates
        # "clawdbot": {
        #     "path": "/Users/username/workspace/clawdbot",
        #     "branch": "main",
        #     "post_update_commands": [
        #         "pnpm install",
        #         "pnpm build"
        #     ],
        #     "restart_services": ["com.clawdbot.gateway"]
        # }
    }
}

# Global state
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
WATCHDOG_LOG = Path.home() / ".claude-watchdog/watchdog.log"
CONFIG = {}


def log(message: str):
    """Log message with timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    print(log_line.strip())
    WATCHDOG_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(WATCHDOG_LOG, "a") as f:
        f.write(log_line)


@tool(
    name="send_telegram",
    description="Send a notification message to Telegram",
    input_schema={"message": str}
)
async def send_telegram_tool(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Send message via Telegram"""
    message = inputs["message"]
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {
            "content": "Telegram not configured (missing token or chat ID)",
            "is_error": True
        }
    
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        response = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        })
        
        if response.ok:
            log(f"📱 Telegram sent: {message[:50]}...")
            return {"content": "Message sent successfully"}
        else:
            return {
                "content": f"Failed to send: {response.text}",
                "is_error": True
            }
    except Exception as e:
        return {
            "content": f"Error sending telegram: {e}",
            "is_error": True
        }


@tool(
    name="check_git_updates",
    description="Check if a git repository has new commits available",
    input_schema={"repo_name": str}
)
async def check_git_updates_tool(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Check if repository has updates"""
    repo_name = inputs["repo_name"]
    repositories = CONFIG.get("repositories", {})
    
    if repo_name not in repositories:
        return {
            "content": f"Unknown repository: {repo_name}. Available: {list(repositories.keys())}",
            "is_error": True
        }
    
    repo = repositories[repo_name]
    repo_path = Path(repo["path"])
    
    if not repo_path.exists():
        return {
            "content": f"Repository path does not exist: {repo_path}",
            "is_error": True
        }
    
    try:
        # Fetch latest
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=repo_path,
            capture_output=True,
            check=True
        )
        
        # Get current branch
        current_branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        current_branch = current_branch_result.stdout.strip()
        
        # Get commit info
        local_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
        
        remote_commit = subprocess.run(
            ["git", "rev-parse", f"origin/{repo.get('branch', 'main')}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
        
        has_updates = local_commit != remote_commit
        
        # Get new commits if available
        new_commits = ""
        if has_updates:
            commits_result = subprocess.run(
                ["git", "log", "--oneline", f"{local_commit}..{remote_commit}"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            new_commits = commits_result.stdout.strip()
        
        return {
            "content": json.dumps({
                "repo_name": repo_name,
                "path": str(repo_path),
                "current_branch": current_branch,
                "has_updates": has_updates,
                "local_commit": local_commit[:7],
                "remote_commit": remote_commit[:7],
                "new_commits": new_commits
            }, indent=2)
        }
    except Exception as e:
        return {
            "content": f"Error checking for updates: {e}",
            "is_error": True
        }


@tool(
    name="get_service_info",
    description="Get detailed service status, logs, and diagnostics for a service",
    input_schema={"service": str}
)
async def get_service_info_tool(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Get service diagnostics"""
    service = inputs["service"]
    services = CONFIG.get("services", {})
    
    if service not in services:
        return {
            "content": f"Unknown service: {service}. Available: {list(services.keys())}",
            "is_error": True
        }
    
    config = services[service]
    diagnostics = {"service": service}
    
    # Get launchd status (macOS)
    if "launchd_label" in config:
        try:
            result = subprocess.run(
                ["launchctl", "list"],
                capture_output=True,
                text=True
            )
            for line in result.stdout.splitlines():
                if config["launchd_label"] in line:
                    parts = line.split()
                    diagnostics["pid"] = parts[0]
                    diagnostics["exit_status"] = parts[1]
                    break
        except Exception as e:
            diagnostics["launchd_error"] = str(e)
    
    # Check systemd status (Linux)
    if "systemd_unit" in config:
        try:
            result = subprocess.run(
                ["systemctl", "status", config["systemd_unit"]],
                capture_output=True,
                text=True
            )
            diagnostics["systemd_status"] = result.stdout[:500]
        except Exception as e:
            diagnostics["systemd_error"] = str(e)
    
    # Check port
    if "port" in config:
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{config['port']}", "-P", "-n"],
                capture_output=True,
                text=True
            )
            diagnostics["port_listening"] = "LISTEN" in result.stdout
        except Exception as e:
            diagnostics["port_error"] = str(e)
    
    # Get recent logs
    if "log_file" in config:
        log_file = Path(config["log_file"])
        if log_file.exists():
            try:
                with open(log_file) as f:
                    lines = f.readlines()
                    diagnostics["recent_errors"] = "".join(lines[-30:])
            except Exception as e:
                diagnostics["log_error"] = str(e)
    
    # Custom health check command
    if "health_check_command" in config:
        try:
            result = subprocess.run(
                config["health_check_command"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            diagnostics["health_check"] = {
                "exit_code": result.returncode,
                "output": result.stdout[:500]
            }
        except Exception as e:
            diagnostics["health_check_error"] = str(e)
    
    return {"content": json.dumps(diagnostics, indent=2)}


def check_service_health(service: str) -> bool:
    """Quick health check for a service"""
    services = CONFIG.get("services", {})
    if service not in services:
        return False
    
    config = services[service]
    
    # Custom health check command takes priority
    if "health_check_command" in config:
        try:
            result = subprocess.run(
                config["health_check_command"],
                shell=True,
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False
    
    # Check launchd status (macOS)
    if "launchd_label" in config:
        try:
            result = subprocess.run(
                ["launchctl", "list"],
                capture_output=True,
                text=True
            )
            for line in result.stdout.splitlines():
                if config["launchd_label"] in line:
                    parts = line.split()
                    if parts[0] == "-" or parts[1] != "0":
                        return False
                    break
            else:
                return False
        except:
            return False
    
    # Check systemd status (Linux)
    if "systemd_unit" in config:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", config["systemd_unit"]],
                capture_output=True,
                text=True
            )
            if result.stdout.strip() != "active":
                return False
        except:
            return False
    
    # Check port
    if "port" in config:
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{config['port']}", "-P", "-n"],
                capture_output=True,
                text=True
            )
            if "LISTEN" not in result.stdout:
                return False
        except:
            return False
    
    return True


def simple_restart(service: str) -> bool:
    """Attempt simple restart via system service manager"""
    services = CONFIG.get("services", {})
    if service not in services:
        return False
    
    config = services[service]
    log(f"🔄 Attempting simple restart of {service}...")
    
    try:
        # macOS launchd
        if "launchd_label" in config:
            subprocess.run(
                ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{config['launchd_label']}"],
                check=True,
                capture_output=True
            )
        # Linux systemd
        elif "systemd_unit" in config:
            subprocess.run(
                ["systemctl", "restart", config["systemd_unit"]],
                check=True,
                capture_output=True
            )
        # Custom restart command
        elif "restart_command" in config:
            subprocess.run(
                config["restart_command"],
                shell=True,
                check=True,
                capture_output=True
            )
        else:
            log(f"❌ No restart method configured for {service}")
            return False
        
        time.sleep(5)
        return check_service_health(service)
    except Exception as e:
        log(f"❌ Simple restart failed: {e}")
        return False


async def invoke_agent(service: str):
    """Invoke Claude Agent to diagnose and fix service issues"""
    log(f"🤖 Invoking Claude Agent for {service}...")
    
    max_restarts = CONFIG.get("max_simple_restarts", 3)
    
    # Prepare the prompt
    prompt = f"""The {service} service has crashed and failed to restart after {max_restarts} simple restart attempts.

Use the available tools to:
1. Get detailed service diagnostics using get_service_info
2. Analyze error logs and identify the root cause
3. Apply fixes using Bash commands (clear caches, update config, fix permissions, etc.)
4. Verify the service is healthy after fixes
5. Send me a Telegram notification with:
   - The service name
   - Root cause summary
   - Actions taken
   - Current status

Be autonomous and thorough. Fix the issue completely."""
    
    # Create MCP server with custom tools
    mcp_server = create_sdk_mcp_server(
        name="watchdog_tools",
        tools=[send_telegram_tool, get_service_info_tool]
    )
    
    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["Bash", "Read", "Edit", "Glob"],
                mcp_servers={"watchdog": mcp_server},
                cwd=str(Path.home()),
            )
        ):
            if hasattr(message, "result"):
                log(f"✅ Agent completed: {message.result}")
            elif hasattr(message, "text"):
                log(f"💭 Agent: {message.text[:100]}...")
    
    except Exception as e:
        log(f"❌ Agent error: {e}")
        # Fallback notification
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            try:
                import requests
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": TELEGRAM_CHAT_ID,
                        "text": f"⚠️ {service} crashed but agent failed to recover: {e}"
                    }
                )
            except:
                pass


async def invoke_update_agent(repo_name: str, repo_config: Dict[str, Any]):
    """Invoke Claude Agent to update a repository"""
    log(f"🔄 Invoking Claude Agent to update {repo_name}...")
    
    # Prepare the prompt with update instructions
    prompt = f"""The repository '{repo_name}' at {repo_config['path']} has new commits available.

Please perform the following update procedure:

1. Use check_git_updates tool to see what commits are available
2. Navigate to the repository: cd {repo_config['path']}
3. Stash any uncommitted changes: git stash save "auto-update-$(date +%Y%m%d-%H%M%S)"
4. Pull the latest changes: git pull --rebase origin {repo_config.get('branch', 'main')}
5. Check if package.json or pnpm-lock.yaml changed:
   - If changed: Run the update commands to install dependencies
   - If not changed: Skip dependency installation
6. Run post-update commands: {', '.join(repo_config.get('post_update_commands', []))}
7. Restart any required services: {', '.join(repo_config.get('restart_services', []))}
8. Verify services are healthy after restart
9. Send me a Telegram notification with:
   - Repository name
   - New commits that were pulled
   - Whether dependencies were updated
   - Services that were restarted
   - Current status

Be thorough and handle any errors gracefully. If something fails, report it in the Telegram notification."""
    
    # Create MCP server with custom tools
    mcp_server = create_sdk_mcp_server(
        name="update_tools",
        tools=[send_telegram_tool, check_git_updates_tool, get_service_info_tool]
    )
    
    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["Bash", "Read", "Edit", "Glob"],
                mcp_servers={"update": mcp_server},
                cwd=str(Path(repo_config['path'])),
            )
        ):
            if hasattr(message, "result"):
                log(f"✅ Update agent completed: {message.result}")
            elif hasattr(message, "text"):
                log(f"💭 Update agent: {message.text[:100]}...")
    
    except Exception as e:
        # Check if it's the known SDK race condition error
        error_msg = str(e)
        if "ProcessTransport is not ready" in error_msg or "TaskGroup" in error_msg:
            log(f"⚠️ Update agent SDK race condition (known issue, safe to ignore): {error_msg[:100]}")
            # Don't send notification for known SDK bugs
        else:
            log(f"❌ Update agent error: {e}")
            # Fallback notification for real errors
            if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                try:
                    import requests
                    requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": TELEGRAM_CHAT_ID,
                            "text": f"⚠️ Failed to update {repo_name}: {e}"
                        }
                    )
                except:
                    pass


async def monitor_loop():
    """Main monitoring loop"""
    log("🐕 F1re Claude Watchdog started")
    
    services = CONFIG.get("services", {})
    repositories = CONFIG.get("repositories", {})
    
    if not services and not repositories:
        log("⚠️ No services or repositories configured. Add to config.json")
        return
    
    if services:
        log(f"📋 Monitoring {len(services)} service(s): {', '.join(services.keys())}")
    
    # Send startup notification to Telegram
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            import requests
            
            # Build startup message
            parts = ["🐕 *F1re Claude Watchdog Started*", ""]
            
            if services:
                parts.append(f"📋 Monitoring {len(services)} service(s):")
                parts.extend([f'  • {svc}' for svc in services.keys()])
                parts.append("")
                parts.append(f"⏱ Check interval: {CONFIG.get('check_interval', 30)}s")
                parts.append(f"🔄 Max restarts: {CONFIG.get('max_simple_restarts', 3)}")
            
            if repositories:
                if services:
                    parts.append("")
                parts.append(f"📦 Auto-updating {len(repositories)} repository(s):")
                parts.extend([f'  • {repo}' for repo in repositories.keys()])
                parts.append("")
                parts.append(f"🔍 Update check: every {CONFIG.get('update_check_interval', 14400)/3600:.1f}h")
            
            parts.append("")
            parts.append("✅ Ready!")
            
            startup_message = chr(10).join(parts)
            
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": startup_message,
                    "parse_mode": "Markdown"
                },
                timeout=5
            )
            log("📱 Sent startup notification to Telegram")
        except Exception as e:
            log(f"⚠️ Failed to send startup notification: {e}")
    
    restart_counts = {service: 0 for service in services}
    check_interval = CONFIG.get("check_interval", 30)
    max_simple_restarts = CONFIG.get("max_simple_restarts", 3)
    
    # Repository update checking
    repositories = CONFIG.get("repositories", {})
    update_check_interval = CONFIG.get("update_check_interval", 14400)  # 4 hours default
    last_update_check = 0
    
    if repositories:
        log(f"🔄 Will check {len(repositories)} repositories for updates every {update_check_interval/3600:.1f} hours")
    
    loop_count = 0
    while True:
        # Service health monitoring
        for service in services:
            if check_service_health(service):
                # Service is healthy
                if restart_counts[service] > 0:
                    log(f"✅ {service} recovered after {restart_counts[service]} restart(s)")
                    restart_counts[service] = 0
            else:
                # Service is down
                restart_counts[service] += 1
                log(f"⚠️ {service} health check failed (attempt {restart_counts[service]}/{max_simple_restarts})")
                
                if restart_counts[service] <= max_simple_restarts:
                    if simple_restart(service):
                        log(f"✅ {service} restarted successfully")
                        restart_counts[service] = 0
                    else:
                        log(f"❌ Simple restart {restart_counts[service]} failed")
                else:
                    # Max restarts exceeded, invoke agent
                    log(f"🚨 Max restart attempts exceeded for {service}, invoking AI agent")
                    await invoke_agent(service)
                    restart_counts[service] = 0
                    await asyncio.sleep(300)  # Wait 5 minutes before trying again
        
        # Check for repository updates periodically
        current_time = time.time()
        if repositories and (current_time - last_update_check) >= update_check_interval:
            log("🔍 Checking repositories for updates...")
            last_update_check = current_time
            
            for repo_name, repo_config in repositories.items():
                try:
                    # Quick check if updates are available
                    repo_path = Path(repo_config['path'])
                    if not repo_path.exists():
                        log(f"⚠️ Repository {repo_name} path does not exist: {repo_path}")
                        continue
                    
                    # Fetch to check for updates
                    result = subprocess.run(
                        ["git", "fetch", "origin"],
                        cwd=repo_path,
                        capture_output=True,
                        timeout=30
                    )
                    
                    # Check if local is behind remote
                    local_commit = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=repo_path,
                        capture_output=True,
                        text=True
                    ).stdout.strip()
                    
                    remote_commit = subprocess.run(
                        ["git", "rev-parse", f"origin/{repo_config.get('branch', 'main')}"],
                        cwd=repo_path,
                        capture_output=True,
                        text=True
                    ).stdout.strip()
                    
                    if local_commit != remote_commit:
                        log(f"🆕 Updates available for {repo_name}, invoking AI agent...")
                        await invoke_update_agent(repo_name, repo_config)
                    else:
                        log(f"✅ {repo_name} is up to date")
                        
                except Exception as e:
                    log(f"❌ Error checking {repo_name} for updates: {e}")
        
        loop_count += 1
        await asyncio.sleep(check_interval)


def load_config():
    """Load configuration from config.json"""
    global CONFIG, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    
    config_file = Path(__file__).parent / "config.json"
    
    if config_file.exists():
        try:
            with open(config_file) as f:
                CONFIG = json.load(f)
            log(f"✅ Loaded config from {config_file}")
        except Exception as e:
            log(f"⚠️ Failed to load config.json: {e}")
            CONFIG = DEFAULT_CONFIG.copy()
    else:
        log(f"⚠️ No config.json found, using defaults")
        CONFIG = DEFAULT_CONFIG.copy()
    
    # Load from environment (takes priority)
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", CONFIG.get("telegram_bot_token", ""))
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", CONFIG.get("telegram_chat_id", ""))
    
    if not TELEGRAM_BOT_TOKEN:
        log("⚠️ TELEGRAM_BOT_TOKEN not set, notifications will be disabled")
    if not TELEGRAM_CHAT_ID:
        log("⚠️ TELEGRAM_CHAT_ID not set, notifications will be disabled")


def main():
    """Entry point"""
    load_config()
    
    try:
        asyncio.run(monitor_loop())
    except KeyboardInterrupt:
        log("🛑 Watchdog stopped by user")
    except Exception as e:
        log(f"❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
