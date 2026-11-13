#!/usr/bin/env python3
"""Discover RSS/Atom feed and update the blog section in the profile README.

Uses only Python's standard library. Does not modify README when the site/feed is
unavailable, so transient errors cannot overwrite existing posts.
"""
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import re
import sys
import xml.etree.ElementTree as ET

BASE = "https://blog.rgb-schnitzel.de/"
README = Path("README.md")
START = "<!-- BLOG-POST-LIST:START -->"
END = "<!-- BLOG-POST-LIST:END -->"
AGENT = "Maxsander123-GitHub-Profile/1.0 (RSS feed reader)"
ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT_NS = "{http://purl.org/rss/1.0/}"
CANDIDATES = (
    "feed.xml", "rss.xml", "atom.xml", "index.xml", "feed", "feed/",
    "rss", "rss/", "index.php/feed", "?feed=rss2", "posts/index.xml",
)

class FeedLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() != "link":
            return
        a = dict(attrs)
        if "alternate" in a.get("rel", "").lower().split() and any(
            v in a.get("type", "").lower()
            for v in ("rss+xml", "atom+xml", "xml")
        ):
            if a.get("href"):
                self.links.append(urljoin(BASE, a["href"]))

def get(url):
    req = Request(url, headers={"User-Agent": AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html"})
    with urlopen(req, timeout=15) as response:
        return response.read(2_000_000)

def text(node, path):
    child = node.find(path)
    return (child.text or "").strip() if child is not None else ""

def parse_feed(data):
    root = ET.fromstring(data)
    posts = []
    if root.tag == "rss" or root.tag.endswith("}RDF"):
        for item in root.findall(".//item")[:5]:
            title = text(item, "title")
            link = text(item, "link")
            if not link:
                link = text(item, "{http://purl.org/rss/1.0/}link")
            if title and link:
                posts.append((title, link))
    elif root.tag == ATOM + "feed":
        for item in root.findall(ATOM + "entry")[:5]:
            title = text(item, ATOM + "title")
            links = item.findall(ATOM + "link")
            link = next((node.attrib.get("href", "") for node in links if node.attrib.get("rel", "alternate") == "alternate" and node.attrib.get("href")), "")
            if title and link:
                posts.append((title, urljoin(BASE, link)))
    return posts

def main():
    current = README.read_text(encoding="utf-8")
    if START not in current or END not in current:
        sys.exit("README markers missing; no changes made")

    candidates = []
    try:
        page = get(BASE).decode("utf-8", errors="replace")
        parser = FeedLinks()
        parser.feed(page)
        candidates.extend(parser.links)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print(f"Could not discover feed from homepage: {exc}")

    candidates.extend(urljoin(BASE, item) for item in CANDIDATES)
    seen = set()
    posts = []
    for feed_url in candidates:
        if feed_url in seen:
            continue
        seen.add(feed_url)
        try:
            posts = parse_feed(get(feed_url))
            if posts:
                print(f"Using feed: {feed_url}")
                break
        except (HTTPError, URLError, TimeoutError, ValueError, ET.ParseError) as exc:
            print(f"Skipping {feed_url}: {exc}")

    if not posts:
        print("No usable RSS/Atom feed found; keeping README unchanged.")
        return

    lines = []
    for title, link in posts:
        safe_title = escape(re.sub(r"\s+", " ", title), quote=False).replace("[", "&#91;").replace("]", "&#93;")
        safe_link = link.replace(" ", "%20").replace("(", "%28").replace(")", "%29")
        if not safe_link.startswith(("https://", "http://")):
            continue
        lines.append(f"- [{safe_title}]({safe_link})")
    if not lines:
        print("No valid posts; keeping README unchanged.")
        return

    updated = current.split(START, 1)[0] + START + "\n" + "\n".join(lines) + "\n" + END + current.split(END, 1)[1]
    if updated != current:
        README.write_text(updated, encoding="utf-8")
        print(f"Updated README with {len(lines)} posts.")
    else:
        print("Blog posts already up to date.")

if __name__ == "__main__":
    main()
