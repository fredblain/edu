#!/usr/bin/env python3
"""Assemble the hub site into _site/ from catalog.yml.

For each item that isn't a draft: fetch its repository at `ref`, run its
optional `build` command, and copy its `path` folder to _site/<slug>/.
Then render index.html and 404.html from templates/ and write sitemap.xml.

Usage
  python build.py                 # fetch every repo from GitHub (what CI does)
  python build.py --local ..      # use existing clones in ../<repo-name> instead
                                  # (their current checkout, `ref` is ignored)

Private repositories: set CONTENT_TOKEN to a token that can read them.
Requires PyYAML (pip install pyyaml).
"""

import argparse
import base64
import datetime as dt
import html
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_site"
WORK = ROOT / "_work"
STATUSES = ("published", "archived", "draft")
ALWAYS_EXCLUDED = (".git", ".github")


def fail(msg):
    sys.exit(f"build.py: {msg}")


def load_catalog():
    data = yaml.safe_load((ROOT / "catalog.yml").read_text(encoding="utf-8")) or {}
    site = data.get("site") or {}
    for key in ("section", "label", "title", "home"):
        if not site.get(key):
            fail(f"catalog.yml: site.{key} is missing")
    site["home"] = str(site["home"]).rstrip("/")
    site["base"] = f"{site['home']}/{site['section']}/"

    defaults = data.get("defaults") or {}
    items, seen = [], set()
    for raw in data.get("items") or []:
        item = {**defaults, **raw}
        for key in ("slug", "repo", "title"):
            if not item.get(key):
                fail(f"catalog.yml: an item has no '{key}': {raw}")
        slug = item["slug"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            fail(f"catalog.yml: slug '{slug}' must be lowercase letters, digits and hyphens")
        if slug in seen:
            fail(f"catalog.yml: slug '{slug}' is used twice")
        seen.add(slug)
        if item.get("status") not in STATUSES:
            fail(f"catalog.yml: '{slug}' has status '{item.get('status')}', expected one of {STATUSES}")
        items.append(item)
    return site, items


def git_auth_args():
    """Pass the token as an HTTP header so it never appears in URLs or logs."""
    token = os.environ.get("CONTENT_TOKEN")
    if not token:
        return []
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return ["-c", f"http.https://github.com/.extraheader=Authorization: Basic {basic}"]


def fetch(item, local_root):
    repo_name = item["repo"].split("/")[-1]
    if local_root:
        src = Path(local_root).expanduser().resolve() / repo_name
        if not src.is_dir():
            fail(f"--local: no clone of {item['repo']} at {src}")
        return src
    dest = WORK / item["slug"]
    shutil.rmtree(dest, ignore_errors=True)
    print(f"  fetching {item['repo']}@{item['ref']}", flush=True)
    subprocess.run(
        ["git", *git_auth_args(), "clone", "--quiet", "--depth", "1",
         "--branch", str(item["ref"]), f"https://github.com/{item['repo']}.git", str(dest)],
        check=True,
    )
    return dest


def run_build(item, src):
    cmd = item.get("build")
    if not cmd:
        return
    print(f"  building: {cmd}", flush=True)
    env = {k: v for k, v in os.environ.items() if k != "CONTENT_TOKEN"}  # builds never see the token
    subprocess.run(cmd, shell=True, cwd=src, env=env, check=True)


def copy_site(item, src):
    site_dir = (src / item["path"]).resolve()
    if not site_dir.is_dir():
        fail(f"'{item['slug']}': folder '{item['path']}' not found in {item['repo']}")
    if not (site_dir / "index.html").is_file():
        print(f"  warning: '{item['slug']}' has no index.html in '{item['path']}'")
    patterns = [*ALWAYS_EXCLUDED, *(item.get("exclude") or [])]
    shutil.copytree(site_dir, OUT / item["slug"], ignore=shutil.ignore_patterns(*patterns))


# ---------- rendering ----------

def esc(value):
    return html.escape(str(value), quote=True)


def as_date(value):
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def render_item(item):
    when = as_date(item.get("date"))
    kicker = [f"{when:%b %Y}"] if when else []
    if item.get("venue"):
        kicker.append(esc(item["venue"]))

    parts = ['<li class="card">']
    if kicker:
        parts.append(f'  <p class="kicker">{" · ".join(kicker)}</p>')
    parts.append(f'  <h2><a href="{esc(item["slug"])}/">{esc(item["title"])}</a></h2>')
    if item.get("authors"):
        parts.append(f'  <p class="authors">{esc(", ".join(item["authors"]))}</p>')
    if item.get("summary"):
        parts.append(f'  <p class="sum">{esc(item["summary"])}</p>')
    if item.get("tags"):
        pills = "".join(f"<li>{esc(t)}</li>" for t in item["tags"])
        parts.append(f'  <ul class="tags" aria-label="Topics">{pills}</ul>')

    links = [("Open", f'{item["slug"]}/', "fa-solid fa-arrow-right")]
    for key, label, icon in (("paper", "Paper", "fa-solid fa-file-lines"),
                             ("code", "Code", "fa-brands fa-github"),
                             ("slides", "Slides", "fa-solid fa-person-chalkboard"),
                             ("video", "Video", "fa-solid fa-play")):
        if item.get(key):
            links.append((label, item[key], icon))
    if item.get("doi"):
        links.append(("DOI", f'https://doi.org/{item["doi"]}', "fa-solid fa-link"))
    chips = "".join(
        f'<a class="chip" href="{esc(url)}"><i class="{icon}" aria-hidden="true"></i>{esc(label)}</a>'
        for label, url, icon in links
    )
    parts.append(f'  <p class="acts">{chips}</p>')
    parts.append("</li>")
    return "\n".join(parts)


def render_page(template_name, site, items_html=""):
    text = (ROOT / "templates" / template_name).read_text(encoding="utf-8")
    values = {
        "title": esc(site["title"]),
        "label": esc(site["label"]),
        "section": esc(site["section"]),
        "description": esc(site.get("description", "")),
        "author": esc(site.get("author", "")),
        "home": esc(site["home"]),
        "base": esc(site["base"]),
        "year": str(dt.date.today().year),
        "items": items_html,
    }
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    leftover = re.findall(r"\{\{\w+\}\}", text)
    if leftover:
        fail(f"templates/{template_name}: unknown placeholders {sorted(set(leftover))}")
    return text


def write_sitemap(site, listed):
    urls = [site["base"]] + [f'{site["base"]}{i["slug"]}/' for i in listed]
    body = "\n".join(f"  <url><loc>{esc(u)}</loc></url>" for u in urls)
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--local", metavar="DIR", help="use existing clones in DIR/<repo-name> instead of fetching")
    args = parser.parse_args()

    site, items = load_catalog()
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir()

    online = [i for i in items if i["status"] != "draft"]
    for item in online:
        print(f"{item['slug']} ({item['status']})", flush=True)
        src = fetch(item, args.local)
        run_build(item, src)
        copy_site(item, src)

    listed = [i for i in online if i["status"] == "published"]
    listed.sort(key=lambda i: as_date(i.get("date")) or dt.date.min, reverse=True)
    cards = "\n".join(render_item(i) for i in listed) or '<li class="empty">Nothing here yet.</li>'

    (OUT / "index.html").write_text(render_page("index.html", site, cards), encoding="utf-8")
    (OUT / "404.html").write_text(render_page("404.html", site), encoding="utf-8")
    write_sitemap(site, listed)
    shutil.rmtree(WORK, ignore_errors=True)
    print(f"done: {len(online)} item(s) online, {len(listed)} listed → {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
