# AWS EC2 Deployment

This bot is a long-running polling process. On EC2, run it as a `systemd` service so it restarts automatically and keeps running after SSH disconnects.

## 1. Prepare the server

Install the base tools and Python runtime:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

If your EC2 image does not already provide Python 3.12, install a Python 3.12 build first and use that interpreter for the virtual environment.

## 2. Clone the project

```bash
sudo mkdir -p /opt/qurbot
sudo chown "$USER":"$USER" /opt/qurbot
cd /opt/qurbot
git clone <your-repo-url> bot
cd bot
```

## 3. Create the environment

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configure `.env`

Create a `.env` file in the project root with at least these values:

```env
BOT_TOKEN=123456:your-token
DATABASE_URL=postgresql+asyncpg://user:password@db-host:5432/dbname
MANAGER_IDS=123456789,987654321
ADMIN_IDS=1504360843
PERMANENT_MANAGER_IDS=1504360843
TIMEZONE=Asia/Tashkent
LOG_LEVEL=INFO
LOG_FILE=/opt/qurbot/bot/bot.log
```

SQLite works for local testing, but PostgreSQL is the better choice for EC2 because the database survives restarts and instance replacement.

## 5. Initialize the database

Run the initialization or migration scripts against the target database before starting the bot:

```bash
. .venv/bin/activate
python main.py
```

If you need to run a one-off migration script, execute it directly from the same environment, for example:

```bash
python scripts/add_receipt_message_id_migration.py
```

## 6. Run with systemd

Create `/etc/systemd/system/qurbot.service`:

```ini
[Unit]
Description=Qurbot Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/qurbot/bot
EnvironmentFile=/opt/qurbot/bot/.env
ExecStart=/opt/qurbot/bot/.venv/bin/python /opt/qurbot/bot/main.py
Restart=always
RestartSec=5
User=ubuntu

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now qurbot
sudo systemctl status qurbot
```

## 7. Logs and troubleshooting

View live logs with:

```bash
journalctl -u qurbot -f
```

The app also writes to `LOG_FILE` when the path is writable.

## Notes

- `config.py` accepts both `postgres://` and `postgresql://` URLs and normalizes them for `asyncpg`.
- The bot uses polling, so you do not need nginx, a reverse proxy, or an inbound HTTP port.
