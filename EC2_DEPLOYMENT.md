# AWS EC2 Deployment

This bot is a long-running polling process. On EC2, run it as a `systemd` service so it restarts automatically and keeps running after SSH disconnects.

## 1. Prepare the server

Install the base tools and Python runtime:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

If your EC2 image does not already provide Python 3.12, install a Python 3.12 build first and use that interpreter for the virtual environment.

## 1.1 Install the database first

If you want the database on the same EC2 instance, install PostgreSQL now before configuring the bot.

```bash
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
sudo systemctl status postgresql
```

Create a database user and database for the bot:

```bash
sudo -u postgres psql
```

Inside the `psql` shell, run:

```sql
CREATE USER qurbot_user WITH PASSWORD 'strong_password_here';
CREATE DATABASE qurbot OWNER qurbot_user;
GRANT ALL PRIVILEGES ON DATABASE qurbot TO qurbot_user;
\q
```

If you use AWS RDS or another external PostgreSQL server, skip the local install and create the database there instead.

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
DATABASE_URL=postgresql+asyncpg://qurbot_user:strong_password_here@127.0.0.1:5432/qurbot
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

### If you see `socket.gaierror: [Errno -3] Temporary failure in name resolution`

This means the database host inside `DATABASE_URL` cannot be resolved from the EC2 instance.

Check these things:

1. Make sure the host part of `DATABASE_URL` is real and not a placeholder like `db-host`.
2. If PostgreSQL runs on the same EC2 instance, use `localhost` or `127.0.0.1`.
3. If you use AWS RDS, copy the exact endpoint from the RDS console.
4. Verify DNS works on the instance:

```bash
getent hosts your-db-hostname
nslookup your-db-hostname
```

5. Make sure the database security group allows connections from the EC2 security group or private IP range.
6. If the host is in a private subnet, confirm the EC2 instance is in the same VPC or has network access to that subnet.

## Notes

- `config.py` accepts both `postgres://` and `postgresql://` URLs and normalizes them for `asyncpg`.
- The bot uses polling, so you do not need nginx, a reverse proxy, or an inbound HTTP port.
