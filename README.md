# Formatter for Slack logs

[hfaran's slack-export-viewer][slack-export-viewer]
is a great tool for browsing complete Slack exports,
but sometimes all you want is a static HTML view of a single channel,
without needing to share the entire workspace export.

This code attempts to fill that gap.
It was written for one very specific channel,
including some manual time zone setting,
so would probably need significant adaptation.

## Requirements

This has been tested with Python 3.12.
Primarily uses pure Python,
with a dependency on `pytz` for time zone management.

## Installation

    git clone https://github.com/homsar/slack-archive-converter
    cd slack-archive-converter
    pip install -r requirements.txt

## Usage

For example, if your current path is in the `general` directory:

    python to_html.py --output_file index.html *.json

[slack-export-viewer]: https://github.com/hfaran/slack-export-viewer
