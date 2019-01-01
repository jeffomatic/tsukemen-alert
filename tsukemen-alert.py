import calendar
import datetime
import PyPDF2
import re
import os
import slackclient
import urllib.request


class EphemeralFile:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return self.path

    def __exit__(self, exc_type, exc_value, traceback):
        os.remove(self.path)


def fetch(url):
    path, _ = urllib.request.urlretrieve(url)
    return EphemeralFile(path)


# calendar.month_name is 1-indexed
months = [calendar.month_name[i].lower() for i in range(0, 13)]


def guess_year(month):
    now = datetime.datetime.now()
    cur = now.month

    if cur == 12 and month == 1:
        return now.year + 1

    if cur == 1 and month == 12:
        return now.year - 1

    return now.year


def get_date(lines):
    n = None
    month = None
    for i, line in enumerate(lines):
        if line in months:
            n = i
            month = months.index(line)
            break

    # Date line follows the month
    if n is None or n >= len(lines) - 1:
        return None

    match = re.search(r"(\d+)", lines[n + 1])
    if match is None:
        return None

    day = int(match.group(1))
    year = guess_year(month)
    return datetime.date(year, month, day)


def has_substr(lines, substr):
    for line in lines:
        if line in substr:
            return True
    return False


def perform_fetch():
    with fetch('https://s3.amazonaws.com/ramenshop/dinner.pdf') as path:
        fr = PyPDF2.PdfFileReader(open(path, 'rb'))
        lines = []
        for i in range(0, fr.getNumPages() - 1):
            p = fr.getPage(i)
            s = p.extractText()
            for line in s.split('\n'):
                line = line.strip().lower()
                if len(line) > 0:
                    lines.append(line)

        msg = 'No tsukemen...'
        if has_substr(lines, 'tsukemen'):
            msg = 'Has tsukemen!'

        date = get_date(lines)
    print("%s: %s" % (date, msg))


token = ''
sc = slackclient.SlackClient(token)
channels = list(
    filter(lambda c: c['is_member'],
           sc.api_call('conversations.list')['channels']))

c = None
if len(channels) > 0:
    c = channels[0]

if c is not None:
    print("%s (%s)" % (c['name'], c['id']))
