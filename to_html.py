#!/usr/bin/env python

from argparse import ArgumentParser, FileType
from collections import defaultdict
from datetime import datetime, timezone
from glob import glob
from html import escape
import json
from re import finditer

import pytz

parser = ArgumentParser()
parser.add_argument(
    "--output_file", default=open("index.html", "w"), type=FileType("w")
)
parser.add_argument("input_json", nargs="+")
args = parser.parse_args()

takeoff_time = datetime(2024, 3, 17, 20, 00).astimezone()
land_time = datetime(2024, 4, 2, 18, 37).astimezone()

with open("wget.sh", "w") as f:
    print("mv avatars avatars_old", file=f)
    print("mv images images_old", file=f)
    print("mv files files_old", file=f)

    print("set -eux", file=f)
    print("mkdir images files avatars", file=f)

messages = []

for filename in args.input_json:
    with open(filename, "r") as f:
        messages.extend(json.loads(f.read()))

messageblock_template = """
<div class="messageblock">
  <div class="avatarpanel">
    <img class="avatar" src="{avatar}">
  </div>
  <div class="messagepanel">
    <div class="messageheader">
      <span class="username">{username}</span>
      <span class="timestamp">{timestamp}</span>
    </div>
    {messages}
  </div>
</div>
"""

message_template = """
    <div class="message">
      <div class="message-timestamp">{timestamp}</div>
      <div class="message-body">{message}</div>
    </div>
"""

imagemessage_template = """
    <div class="message">
      <div class="message-timestamp">{timestamp}</div>
      <div class="message-body image-container"><a href="{target}">{notes}<img class="inlineimage" src="{image}" alt="{alt}"></a></div>
    </div>
"""

date_template = """
<div class="dateheader">{date}</div>
"""

page_template = """
<!DOCTYPE html>
<html>
<head>
  <title>Slack archive for #japan-2024</title>
  <link rel="stylesheet" href="styles.css">
  <link href="https://fonts.googleapis.com/css?family=Exo+2:300,400,700" rel="stylesheet" type="text/css">  <meta charset="utf-8">
</head>
<body>
<h1>Slack archive for #japan-2024</h1>
{content}
</body></html>
"""


def get_datetime(timestamp):
    dt = datetime.fromtimestamp(float(timestamp)).astimezone(timezone.utc)
    if takeoff_time < dt < land_time:
        return dt.astimezone(pytz.timezone("Asia/Tokyo"))
    else:
        return dt.astimezone()


user_details = defaultdict(dict)
files = defaultdict(dict)

user_details["USLACKBOT"] = {"name": "Slackbot", "avatar": "avatars/slackbot.png"}


def add_wget(source, dest, f=None):
    to_close = False
    if not f:
        to_close = True
        f = open("wget.sh", "a")

    print(f"wget '{source}' -O '{dest}'", file=f)

    if to_close:
        f.close()


def get_deets(user, profile):
    filename = f"{profile['avatar_hash']}.jpg"
    path = f"avatars/{filename}"
    if user not in user_details:
        add_wget(profile["image_72"], path)
    detail = user_details[user]
    detail["avatar"] = path
    detail["name"] = profile["name"]


def get_file(message_file):
    detail = files[message_file["id"]]
    filename = f"{message_file['id']}.{message_file['filetype']}"
    with open("wget.sh", "a") as f:
        if message_file["mimetype"].startswith("image"):
            path = f"images/{filename}"
        else:
            path = f"files/{filename}"
            thumb_filename = f"{message_file['id']}.jpg"
            thumb_path = f"images/{thumb_filename}"
            detail["thumb_path"] = thumb_path
            if "thumb_960" in message_file:
                thumb_source = message_file["thumb_960"]
            elif "thumb_video" in message_file:
                thumb_source = message_file["thumb_video"]
            else:
                breakpoint()
            add_wget(thumb_source, thumb_path, f=f)

        detail["path"] = path
        add_wget(message_file["url_private_download"], path, f)


def complete_block(content, current_user_content, current_user, current_dt):
    if current_user_content:
        content.append(
            messageblock_template.format(
                avatar=user_details[current_user]["avatar"],
                username=user_details[current_user]["name"],
                timestamp=current_dt.strftime("%H:%M:%S %Z"),
                messages="\n".join(current_user_content),
            )
        )


def format_message(message_text):
    for userid, user_detail in user_details.items():
        message_text = message_text.replace(userid, user_detail["name"])

    start = 0
    components = []
    for token in finditer("<[^<>]*>", message_text):
        components.append(escape(message_text[start : token.start()]))
        match len(split_token := token.group().strip("<>").split("|")):
            case 0:
                components.append(escape("<>"))
            case 1:
                (target,) = split_token
                if target.startswith("@"):
                    components.append(f'<span class="username">{target}</span>')
                elif target.startswith("http"):
                    components.append(f'<a href="{target}">{escape(target)}</a>')
                else:
                    components.append(escape(token.group()))
            case 2:
                description, target = split_token
                if target.startswith("http"):
                    components.append(f'<a href="{target}">{escape(description)}</a>')
            case _:
                components.append(escape(token.group()))
        start = token.end()
    else:
        components.append(message_text[start:])

    return "".join(components)


current_dt = None
current_user_dt = None
current_user = None

current_user_content = []
content = []

for message in messages:
    if "user_profile" in message:
        get_deets(message["user"], message["user_profile"])

for message in messages:
    dt = get_datetime(message["ts"])
    if current_dt is None or dt.date() != current_dt.date():
        complete_block(content, current_user_content, current_user, current_user_dt)
        current_dt = dt
        current_user = None
        current_user_content = []
        content.append(date_template.format(date=dt.date()))

    if message["user"] != current_user:
        complete_block(content, current_user_content, current_user, current_user_dt)
        current_user = message["user"]
        current_user_dt = dt
        current_user_content = []

    if message["text"]:
        message_text = format_message(message["text"])
        current_user_content.append(
            message_template.format(
                message=message_text, timestamp=dt.strftime("%H:%M %Z")
            )
        )

    for message_file in message.get("files", []):
        get_file(message_file)
        file_details = files[message_file["id"]]
        if message_file["mimetype"].startswith("image"):
            current_user_content.append(
                imagemessage_template.format(
                    target=file_details["path"],
                    image=file_details["path"],
                    alt=message_file["title"],
                    timestamp=dt.strftime("%H:%M %Z"),
                    notes="",
                )
            )
        else:
            current_user_content.append(
                imagemessage_template.format(
                    target=file_details["path"],
                    image=file_details["thumb_path"],
                    alt=message_file["title"],
                    timestamp=dt.strftime("%H:%M %Z"),
                    notes=f"<i>{message_file['title']} &ndash; {message_file['filetype'].upper()} attachment:</i> ",
                )
            )
else:
    complete_block(content, current_user_content, current_user, current_dt)

print(page_template.format(content="\n".join(content)), file=args.output_file)
