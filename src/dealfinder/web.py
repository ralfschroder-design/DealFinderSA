"""DealFinderSA — local search web UI (FastAPI, server-rendered HTML)."""
from __future__ import annotations

import html
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from dealfinder.db import ListingRepository
from dealfinder.models import Category, Listing


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

_CATEGORY_OPTIONS = [("", "Any category"), ("car", "Car"), ("bike", "Bike"), ("boat", "Boat"), ("jetski", "Jet Ski")]
_SORT_OPTIONS = [("recent", "Newest first"), ("price_asc", "Price: low to high"), ("price_desc", "Price: high to low")]
_VALID_ONLY_OPTIONS = [("1", "Valid only"), ("0", "Show all")]


def _int_or_none(v: str | None) -> int | None:
    """Return int if *v* is a non-empty digit string, else None."""
    v = (v or "").strip()
    return int(v) if v.isdigit() else None


def _clean(v: str | None) -> str | None:
    """Return stripped string if non-empty, else None."""
    v = (v or "").strip()
    return v or None

_PAGE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #f4f5f7; color: #1a1a2e; }
header { background: #1a1a2e; color: #fff; padding: 1rem 1.5rem; }
header h1 { font-size: 1.4rem; letter-spacing: .05em; }
.container { max-width: 1200px; margin: 0 auto; padding: 1rem 1rem 3rem; }
.search-form { background: #fff; border-radius: 8px; padding: 1.2rem 1.5rem; margin-bottom: 1.5rem;
               box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.search-form h2 { font-size: 1rem; color: #555; margin-bottom: .8rem; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: .6rem; }
.form-group label { display: block; font-size: .75rem; color: #666; margin-bottom: .2rem; }
.form-group input, .form-group select { width: 100%; padding: .4rem .55rem; border: 1px solid #ccc;
    border-radius: 5px; font-size: .85rem; }
.btn-search { margin-top: .8rem; padding: .5rem 1.4rem; background: #e63946; color: #fff;
              border: none; border-radius: 5px; cursor: pointer; font-size: .9rem; }
.btn-search:hover { background: #c1121f; }
.result-count { font-size: .85rem; color: #666; margin-bottom: .8rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1rem; }
.card { background: #fff; border-radius: 8px; overflow: hidden;
        box-shadow: 0 1px 4px rgba(0,0,0,.08); display: flex; flex-direction: column; }
.card img, .card .no-img { width: 100%; height: 160px; object-fit: cover; background: #ddd;
                            display: flex; align-items: center; justify-content: center;
                            color: #999; font-size: .75rem; }
.card-body { padding: .75rem; flex: 1; display: flex; flex-direction: column; gap: .3rem; }
.card-title { font-size: .95rem; font-weight: 600; color: #1a1a2e; }
.card-price { font-size: 1.05rem; color: #e63946; font-weight: 700; }
.card-meta { font-size: .78rem; color: #666; }
.badge { display: inline-block; font-size: .65rem; padding: .15rem .4rem; border-radius: 4px;
         font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
.badge-valid { background: #d1fadf; color: #0a5c2c; }
.badge-invalid { background: #ffe0e0; color: #7a0000; }
.card-link { margin-top: auto; padding-top: .5rem; }
.card-link a { color: #e63946; font-size: .82rem; text-decoration: none; font-weight: 600; }
.card-link a:hover { text-decoration: underline; }
.no-results { text-align: center; color: #888; padding: 3rem 1rem; font-size: 1rem; }
"""


def _select(name: str, options: list[tuple[str, str]], current: str) -> str:
    opts = []
    for val, label in options:
        selected = ' selected' if val == current else ''
        opts.append(f'<option value="{html.escape(val)}"{selected}>{html.escape(label)}</option>')
    return f'<select name="{html.escape(name)}">{"".join(opts)}</select>'


def _card_html(listing: Listing) -> str:
    # Thumbnail
    if listing.image_urls:
        img = f'<img src="{html.escape(listing.image_urls[0])}" alt="listing image" loading="lazy">'
    else:
        img = '<div class="no-img">No image</div>'

    # Title line: YEAR MAKE MODEL
    parts = [str(listing.year) if listing.year else "",
             listing.make or "", listing.model or ""]
    title_line = " ".join(p for p in parts if p) or (listing.title or "Unknown")

    # Price
    if listing.price_zar is not None:
        price_str = f"R{listing.price_zar:,}"
    else:
        price_str = "no price"

    town = html.escape(listing.town or "")
    category_val = html.escape(listing.category.value if listing.category else "")
    badge_cls = "badge-valid" if listing.is_valid else "badge-invalid"
    badge_txt = "valid" if listing.is_valid else "invalid"
    url = html.escape(listing.url)

    return f"""
<div class="card">
  {img}
  <div class="card-body">
    <div class="card-title">{html.escape(title_line)}</div>
    <div class="card-price">{html.escape(price_str)}</div>
    <div class="card-meta">{town}{" · " if town else ""}{category_val}</div>
    <div><span class="badge {badge_cls}">{badge_txt}</span></div>
    <div class="card-link"><a href="{url}" target="_blank" rel="noopener">View &rarr;</a></div>
  </div>
</div>"""


def render_page(listings: list[Listing], filters: dict[str, Any]) -> str:
    # Form field values (safe defaults)
    f_category = filters.get("category") or ""
    f_make = html.escape(filters.get("make") or "")
    f_q = html.escape(filters.get("q") or "")
    f_min_price = filters.get("min_price") or ""
    f_max_price = filters.get("max_price") or ""
    f_town = html.escape(filters.get("town") or "")
    f_valid_only = filters.get("valid_only", True)
    f_sort = filters.get("sort") or "recent"

    f_valid_only_str = "1" if f_valid_only else "0"

    category_select = _select("category", _CATEGORY_OPTIONS, f_category)
    sort_select = _select("sort", _SORT_OPTIONS, f_sort)
    valid_only_select = _select("valid_only", _VALID_ONLY_OPTIONS, f_valid_only_str)

    count = len(listings)
    result_count_txt = f"{count} listing{'s' if count != 1 else ''} found"

    cards_html = "".join(_card_html(l) for l in listings)
    grid_or_empty = (
        f'<div class="grid">{cards_html}</div>'
        if listings
        else '<div class="no-results">No listings match your search.</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DealFinderSA — Search</title>
  <style>{_PAGE_CSS}</style>
</head>
<body>
<header><h1>DealFinderSA</h1></header>
<div class="container">
  <div class="search-form">
    <h2>Search listings</h2>
    <form method="get" action="/">
      <div class="form-grid">
        <div class="form-group">
          <label for="f-category">Category</label>
          {category_select}
        </div>
        <div class="form-group">
          <label for="f-make">Make</label>
          <input type="text" name="make" id="f-make" value="{f_make}" placeholder="e.g. BMW">
        </div>
        <div class="form-group">
          <label for="f-q">Search title</label>
          <input type="text" name="q" id="f-q" value="{f_q}" placeholder="keyword">
        </div>
        <div class="form-group">
          <label for="f-min">Min price (R)</label>
          <input type="number" name="min_price" id="f-min" value="{f_min_price}" min="0" placeholder="0">
        </div>
        <div class="form-group">
          <label for="f-max">Max price (R)</label>
          <input type="number" name="max_price" id="f-max" value="{f_max_price}" min="0" placeholder="any">
        </div>
        <div class="form-group">
          <label for="f-town">Town</label>
          <input type="text" name="town" id="f-town" value="{f_town}" placeholder="e.g. Pretoria">
        </div>
        <div class="form-group">
          <label for="f-sort">Sort by</label>
          {sort_select}
        </div>
        <div class="form-group">
          <label for="f-valid">Listing status</label>
          {valid_only_select}
        </div>
      </div>
      <button type="submit" class="btn-search">Search</button>
    </form>
  </div>
  <div class="result-count">{result_count_txt}</div>
  {grid_or_empty}
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(repo: ListingRepository) -> FastAPI:
    app = FastAPI(title="DealFinderSA")

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    @app.get("/", response_class=HTMLResponse)
    async def search(
        request: Request,
        category: str | None = None,
        make: str | None = None,
        q: str | None = None,
        min_price: str | None = None,
        max_price: str | None = None,
        town: str | None = None,
        valid_only: str | None = None,
        sort: str = "recent",
    ):
        # Normalise text fields — blank string → None
        make = _clean(make)
        q = _clean(q)
        town = _clean(town)

        # Normalise numeric fields — blank/non-digit → None
        min_price_int = _int_or_none(min_price)
        max_price_int = _int_or_none(max_price)

        # valid_only: False only for explicit opt-out values; default (absent) → True
        _falsy = {"0", "false", "no", "off"}
        valid_only_bool: bool = (valid_only or "").strip().lower() not in _falsy

        # Parse category string → Category enum (ignore invalid values)
        cat_enum: Category | None = None
        if _clean(category):
            try:
                cat_enum = Category(category.strip())
            except ValueError:
                cat_enum = None

        listings = repo.search_listings(
            category=cat_enum,
            make=make,
            q=q,
            min_price=min_price_int,
            max_price=max_price_int,
            town=town,
            valid_only=valid_only_bool,
            sort=sort,
            limit=200,
        )

        filters = {
            "category": cat_enum.value if cat_enum else "",
            "make": make or "",
            "q": q or "",
            "min_price": min_price_int,
            "max_price": max_price_int,
            "town": town or "",
            "valid_only": valid_only_bool,
            "sort": sort,
        }

        return HTMLResponse(content=render_page(listings, filters))

    return app
