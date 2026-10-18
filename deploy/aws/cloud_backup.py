"""Private daily SQLite backup to the project's same-Region S3 bucket."""

import os

import boto3
from backup import backup
from botocore.config import Config


def main():
    region = os.environ.get("AWS_REGION", "us-east-2")
    if region != "us-east-2":
        raise RuntimeError("Backups are restricted to us-east-2.")
    bucket = os.environ["CLAN_BACKUP_BUCKET"]
    path = backup("/opt/guild-bot/guild.db", "/opt/guild-bot/backups")
    client = boto3.client(
        "s3",
        region_name=region,
        config=Config(
            connect_timeout=10,
            read_timeout=30,
            retries={"mode": "standard", "total_max_attempts": 3},
        ),
    )
    key = "backups/" + path.name
    client.upload_file(str(path), bucket, key, ExtraArgs={"ServerSideEncryption": "AES256"})
    print("Private database backup uploaded:", key)


if __name__ == "__main__":
    main()
