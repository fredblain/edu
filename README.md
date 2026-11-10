# edu: teaching hub for fredblain.github.io/edu/

This repo has no content of its own. A GitHub Action reads `catalog.yml`, copies each listed repository into `/edu/<slug>/`, generates the index page, and deploys it all with GitHub Pages.

| File | What it is |
|---|---|
| `catalog.yml` | The list of published material. **The file you normally edit.** |
| `templates/index.html` | The index page layout (same style as the homepage) |
| `templates/404.html` | Shown for any missing page under `/edu/` |
| `build.py` | Fetches the repos and assembles `_site/` |
| `.github/workflows/deploy.yml` | Runs `build.py` and deploys on push, on request, and weekly |
| `examples/notify.yml` | Optional workflow for content repos, to trigger a rebuild when they change |

## Publish something new

1. Put the material in its own repository, with the site in a folder (or at the root).
2. Add an entry to `items:` in `catalog.yml` (the fields are explained at the top of the file).
3. Commit and push. The hub rebuilds and the material appears at `https://fredblain.github.io/edu/<slug>/`.

Use `status: draft` to prepare an entry without publishing it, and `status: archived` to keep a page online but remove it from the index. To release a fixed version (e.g. for a course year), tag the content repo and set `ref:` to that tag.

## Preview locally

```sh
pip install pyyaml
python build.py --local ..        # uses your clones in ../<repo-name>
python -m http.server -d _site    # open http://localhost:8000
```

Fonts and icons load from the live homepage, so the preview needs an internet connection to look right.

## One-time setup

- **Settings → Pages → Build and deployment → Source: GitHub Actions.**
- **Private content repos only:** create a fine-grained token with read-only *Contents* access to them, and save it as the repository secret `CONTENT_READ_TOKEN`.
- **Search engines:** in Search Console, submit `https://fredblain.github.io/edu/sitemap.xml`, or add `Sitemap: https://fredblain.github.io/edu/sitemap.xml` to the homepage's `robots.txt`.

## A research hub

`res` uses the same files. Copy this repo, then change `site:` in `catalog.yml` (`section: res`, `label: Research`, …). Research items can also have `venue`, `authors`, `paper`, `code`, `doi`, `slides` and `video`, which are shown on the index page when present.

## Licence

Code in this repo is MIT-licensed (see `LICENSE`). Each published item keeps the licence of its own repository.
