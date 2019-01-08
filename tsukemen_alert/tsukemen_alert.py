import boto3
import datetime
import fitz as pymupdf
import json
import re
import os
import slackclient
import sys
from typing import List, Dict, Optional
import urllib.request


def make_s3_client(config):
    session = boto3.session.Session(
        aws_access_key_id=config["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=config["S3_SECRET_ACCESS_KEY"],
    )
    return session.resource("s3")


class EphemeralFile:
    def __init__(self, path: str):
        self.path = path

    def __enter__(self) -> str:
        return self.path

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        os.remove(self.path)


def fetch(url: str) -> EphemeralFile:
    path, _ = urllib.request.urlretrieve(url)
    return EphemeralFile(path)


def load_config() -> Dict[str, str]:
    config = {
        "MENU_SRC_URL": "",
        "S3_ACCESS_KEY_ID": "",
        "S3_SECRET_ACCESS_KEY": "",
        "S3_BUCKET": "",
        "SLACK_API_TOKEN": "",
        "SLACK_CHANNEL": "",
    }

    config_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"
    )

    if os.path.exists(config_file):
        with open(config_file) as encoded:
            data = json.load(encoded)
            for k, v in config.items():
                config[k] = data[k]
    else:
        for k, v in config.items():
            config[k] = os.environ[k]

    return config


# Ramen Shop's menus render month names with arbitrary spaces
month_patterns = [
    "j *a *n *u *a *r *y",
    "f *e *b *r *u *a *r *y",
    "m *a *r *c *h",
    "a *p *r *i *l",
    "m *a *y",
    "j *u *n *e",
    "j *u *l *y",
    "a *u *g *u *s *t",
    "s *e *p *t *e *m *b *e *r",
    "o *c *t *o *b *e *r",
    "n *o *v *e *m *b *e *r",
    "d *e *c *e *m *b *e *r",
]


def guess_year(month: int) -> int:
    now = datetime.datetime.now()
    cur = now.month

    if cur == 12 and month == 1:
        return now.year + 1

    if cur == 1 and month == 12:
        return now.year - 1

    return now.year


def parse_date(lines: List[str]) -> Optional[datetime.date]:
    def get_month_and_line():
        for i, line in enumerate(lines):
            for m, pat in enumerate(month_patterns):
                if re.fullmatch(pat, line):
                    return (m + 1, i)  # Return the 1-indexed month

        return (None, None)

    month, monthline = get_month_and_line()
    if monthline is None:
        return None

    # Date line follows the month after a delimeter line
    dateline = monthline + 2
    if dateline >= len(lines):
        return None

    # Ramen Shop has a delimeter between the month and date
    match = re.search(r"(\d+)", lines[dateline])
    if match is None:
        return None
    day = int(match.group(1))

    return datetime.date(guess_year(month), month, day)


def has_substr(lines: List[str], substr: str) -> bool:
    for line in lines:
        if substr in line:
            return True
    return False


def get_pdf_text(pdf) -> List[str]:
    lines = []
    for i in range(pdf.pageCount):
        s = pdf.getPageText(i)
        for line in s.split("\n"):
            line = line.strip().lower()
            if len(line) > 0:
                lines.append(line)
    return lines


def run():
    config = load_config()
    with fetch(config["MENU_SRC_URL"]) as path:
        pdf = pymupdf.open(path)
        lines = get_pdf_text(pdf)
        pdf.close()

        # No need to do anything if the menu doesn't have what we're looking for.
        substr = "tsukemen"
        if not has_substr(lines, substr):
            print("Menu does not contain search pattern: %s" % substr)
            return

        date = parse_date(lines)
        upload_key = date.isoformat() + ".pdf"
        s3 = make_s3_client(config)
        bucket = s3.Bucket(config["S3_BUCKET"])

        # If the menu has already been uploaded, then we're done.
        if any([obj.key == upload_key for obj in bucket.objects.all()]):
            print("Menu already uploaded: %s" % upload_key)
            return

        # Post an alert to Slack.
        sc = slackclient.SlackClient(config["SLACK_API_TOKEN"])
        datef = date.strftime("%A, %b %-d")
        link = "https://s3.amazonaws.com/%s/%s" % (bucket.name, upload_key)
        text = "*Ramen Shop is serving tsukemen* on *%s*\nMenu: %s" % (datef, link)
        sc.api_call("chat.postMessage", channel=config["SLACK_CHANNEL"], text=text)

        # Upload the menu.
        bucket.upload_file(
            path, upload_key, ExtraArgs={"ContentType": "application/pdf"}
        )
        print("Uploaded menu: %s" % upload_key)


def lambda_handler(event, context):
    run()
    return {"message": "ok"}


if sys.argv[0] == __file__:
    run()
