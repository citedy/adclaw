---
name: cron
description: Manage scheduled cron jobs via the adclaw CLI — create, list, pause, resume, and delete tasks.
metadata: { "adclaw": { "emoji": "⏰" } }
---

# Scheduled Task Management

Use the `adclaw cron` command to manage scheduled tasks.

## Common Commands

```bash
# List all tasks
adclaw cron list

# View task details
adclaw cron get <job_id>

# View task status
adclaw cron state <job_id>

# Delete a task
adclaw cron delete <job_id>

# Pause / Resume a task
adclaw cron pause <job_id>
adclaw cron resume <job_id>

# Run a task immediately (one-time execution)
adclaw cron run <job_id>
```

## Creating Tasks

Two task types are supported:
- **text**: Send a fixed message to a channel on a schedule
- **agent**: Ask the Agent a question on a schedule and send the reply to a channel

### Quick Create

```bash
# Send a text message every day at 9:00
adclaw cron create \
  --type text \
  --name "Daily Good Morning" \
  --cron "0 9 * * *" \
  --channel imessage \
  --target-user "CHANGEME" \
  --target-session "CHANGEME" \
  --text "Good morning!"

# Ask the Agent a question every 2 hours
adclaw cron create \
  --type agent \
  --name "Check To-Dos" \
  --cron "0 */2 * * *" \
  --channel dingtalk \
  --target-user "CHANGEME" \
  --target-session "CHANGEME" \
  --text "What are my pending to-do items?"
```

### Required Parameters

Creating a task requires:
- `--type`: Task type (text or agent)
- `--name`: Task name
- `--cron`: Cron expression (e.g., `"0 9 * * *"` means every day at 9:00)
- `--channel`: Target channel (imessage / discord / dingtalk / qq / console)
- `--target-user`: User identifier
- `--target-session`: Session identifier
- `--text`: Message content (for text type) or question content (for agent type)

### Create from JSON (Advanced Configuration)

```bash
adclaw cron create -f job_spec.json
```

## Cron Expression Examples

```
0 9 * * *      # Every day at 9:00
0 */2 * * *    # Every 2 hours
30 8 * * 1-5   # Weekdays at 8:30
0 0 * * 0      # Every Sunday at midnight
*/15 * * * *   # Every 15 minutes
```

## Usage Tips

- If required parameters are missing, ask the user to provide them before creating the task
- Before pausing, deleting, or resuming a task, use `adclaw cron list` to find the job_id
- When troubleshooting, use `adclaw cron state <job_id>` to check the task status
- Commands shown to the user should be complete and ready to copy-paste
