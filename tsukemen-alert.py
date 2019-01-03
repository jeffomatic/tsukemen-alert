import datetime
import fitz as pymupdf  # PyMuPDF
import json
import re
import os
import slackclient
from typing import List, Dict, Optional
import urllib.request


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
    path = os.path.join(os.path.dirname(__file__), 'config.json')
    config = {'SLACK_API_TOKEN': ''}
    if os.path.exists(path):
        with open(path) as encoded:
            data = json.load(encoded)
            for k, v in config.items():
                config[k] = data[k]
    else:
        for k, v in config.items():
            config[k] = os.environ[k]

    return config


# Ramen Shop's menus render month names with arbitrary spaces
month_patterns = [
    'j *a *n *u *a *r *y', 'f *e *b *r *u *a *r *y', 'm *a *r *c *h',
    'a *p *r *i *l', 'm *a *y', 'j *u *n *e', 'j *u *l *y', 'a *u *g *u *s *t',
    's *e *p *t *e *m *b *e *r', 'o *c *t *o *b *e *r',
    'n *o *v *e *m *b *e *r', 'd *e *c *e *m *b *e *r'
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
    year = guess_year(month)
    return datetime.date(year, month, day)


def has_substr(lines: List[str], substr: str) -> bool:
    for line in lines:
        if line in substr:
            return True
    return False


def perform_fetch(url: str) -> None:
    lines = []
    with fetch(url) as path:
        pdf = pymupdf.open(path)
        for i in range(pdf.pageCount):
            s = pdf.getPageText(i)
            for line in s.split('\n'):
                line = line.strip().lower()
                if len(line) > 0:
                    lines.append(line)
        pdf.close()

    msg = 'No tsukemen...'
    if has_substr(lines, 'tsukemen'):
        msg = 'Has tsukemen!'

    date = parse_date(lines)
    print("%s: %s" % (date, msg))


menu_url = 'https://s3.amazonaws.com/ramenshop/dinner.pdf'
url_no_tsukemen = 'https://www.dropbox.com/s/a01gksgh7nle94g/sample-no-tsukemen.pdf?dl=1'
url_with_tsukemen = 'https://www.dropbox.com/s/c85wln91upjn8ma/sample-with-tsukemen.pdf?dl=1'
perform_fetch(url_with_tsukemen)

config = load_config()
sc = slackclient.SlackClient(config['SLACK_API_TOKEN'])
channels = list(
    filter(lambda c: c['is_member'],
           sc.api_call('conversations.list')['channels']))

c = None
if len(channels) > 0:
    c = channels[0]

if c is not None:
    print("%s (%s)" % (c['name'], c['id']))
