"""gem_loader — parse poe2db's gem-page HTML into a GemCatalog.

Unlike the mod pages (which embed `new ModsView({...});` JSON inline), gem
pages render their data as HTML tables. Each gem entry is a
`<tr data-filters="...">` row carrying:

  - `data-filters` attribute: space-separated tags + the gem display name
    appended at the end (poe2db uses this for client-side filter UI)
  - two `<a>` tags inside the row: first is the icon, second is the name link
  - both `<a>` tags carry a `gem_red` / `gem_green` / `gem_blue` class —
    that's the gem's color (Str / Dex / Int requirement)
  - the link `href` is `/us/<Slug>`, which is the canonical id
  - the display name is the second link's text, followed by `(N)` where
    N is a level marker — the level the gem starts at when cut

The page also contains supporting tables (gemcutting-tier ladder, etc.)
whose rows don't carry `data-filters`; those are skipped.
"""

from __future__ import annotations

import re
from typing import Optional

from catalog.gem import Gem, GemCatalog


# One gem-bearing row. The body is greedy up to the next `<tr` to avoid
# tripping over malformed inner HTML.
_ROW_RE = re.compile(
    r'<tr\s+data-filters="(?P<filters>[^"]*)">(?P<body>.*?)(?=<tr\s+data-filters=|</tbody>|</table>|\Z)',
    re.DOTALL,
)

# A gem link: `<a class="gem_COLOR ..." ... href="/us/SLUG" ...>NAME</a>`.
# The class attribute may carry multiple tokens (e.g. `gem_red icon`) so we
# match the color token with word boundaries instead of requiring it to be
# the entire value.
_GEM_LINK_RE = re.compile(
    r'<a\s+class="[^"]*\b(?P<color>gem_red|gem_green|gem_blue)\b[^"]*"[^>]*'
    r'href="/[a-z]+/(?P<slug>[^"]+)"[^>]*>(?P<text>[^<]*)</a>'
)

# Trailing `(N)` after a gem-name link — the level marker.
_LEVEL_RE = re.compile(r'</a>\s*\((\d+)\)')

# poe2db CDN icon URL for the gem.
_ICON_RE = re.compile(r'<img[^>]+src="(https://cdn\.poe2db\.tw/[^"]+)"')


def catalog_from_page(gem_class: str, html: str) -> GemCatalog:
    """Parse a poe2db gem page (Skill_Gems / Support_Gems / Spirit_Gems) into a GemCatalog.

    Rows without a recognisable name link are skipped silently. Duplicates
    (same slug + level) across the page's multiple tables are deduplicated.
    """
    gems: list[Gem] = []
    seen: set[tuple[str, int]] = set()
    for m in _ROW_RE.finditer(html):
        gem = _row_to_gem(gem_class, m.group("filters"), m.group("body"))
        if gem is None:
            continue
        key = (gem.slug, gem.level)
        if key in seen:
            continue
        seen.add(key)
        gems.append(gem)
    return GemCatalog(gem_class=gem_class, gems=gems)


def _row_to_gem(gem_class: str, filters: str, body: str) -> Optional[Gem]:
    """Convert one `<tr data-filters=...>` row body to a Gem. None if malformed."""
    # Two gem links per row: the first wraps the icon, the second wraps the name.
    # We use the second one for the name text; either gives us the slug + color.
    matches = list(_GEM_LINK_RE.finditer(body))
    if not matches:
        return None
    # Prefer the link whose text content is non-empty (i.e. the name link, not
    # the icon-only link). Fall back to the first match if none have text.
    name_link = next(
        (m for m in matches if m.group("text").strip()),
        matches[0],
    )
    color = name_link.group("color").removeprefix("gem_")
    slug = name_link.group("slug")
    name = name_link.group("text").strip()
    if not name or not slug:
        return None

    level_match = _LEVEL_RE.search(body)
    level = int(level_match.group(1)) if level_match else 1

    tags = _parse_tags(filters, name)

    icon_match = _ICON_RE.search(body)
    icon_url = icon_match.group(1) if icon_match else None

    return Gem(
        name=name,
        slug=slug,
        gem_class=gem_class,
        color=color,
        level=level,
        tags=frozenset(tags),
        icon_url=icon_url,
    )


def _parse_tags(filters: str, name: str) -> list[str]:
    """Extract tag tokens from a `data-filters` attribute value.

    poe2db's filter string ends with the gem display name appended (so the
    client-side filter can match on name OR tag). Strip the trailing name
    only when it sits at a token boundary — `endswith(name)` alone would
    chop a legitimate tag whose suffix coincidentally equals the gem name.
    """
    filters = filters.strip()
    if name:
        if filters == name:
            filters = ""
        elif filters.endswith(" " + name):
            filters = filters[: -len(name) - 1].rstrip()
    return filters.split()
