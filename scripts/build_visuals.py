#!/usr/bin/env python3
"""Build the guide's fork diagram as light and dark SVGs.

The diagram is defined once here, labels and alt text included, and written
in two themes so the light and dark files never drift apart. The README shows
the right one with a <picture> element. Edit this script, never the SVGs.

Usage:
    python3 scripts/build_visuals.py          # write the SVGs to assets/
    python3 scripts/build_visuals.py --check  # write them, then check them

--check fails if a label does not fit, if the smallest text would be under
11 CSS px on a phone, or if the README alt text differs from FORK_ALT. The
fit check needs Pillow and the DejaVu fonts (Sans, Sans Bold and Sans Mono),
or Arial and Menlo on a Mac. Without them it is skipped on your computer and
fails in CI.

House style: no em or en dashes, and ASCII only in every label.
"""

from __future__ import annotations

import os
import pathlib
import re
import sys
from html.parser import HTMLParser
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
README = ROOT / "README.md"

# GitHub's own font stacks. Monospace is only for real commands.
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"

# GitHub Primer functional colors. Dark accent_bg is bgColor-accent-muted
# (#388bfd1a) flattened over bgColor-default (#0d1117), because an SVG in an
# <img> cannot rely on the page behind it. Body text contrast, worst pair:
# light 4.56:1 (accent on accent_bg), dark 5.47:1 (accent on accent_bg).
THEMES = {
    "light": {
        "card": "#f6f8fa",       # bgColor-muted
        "surface": "#ffffff",    # bgColor-default
        "border": "#d1d9e0",     # borderColor-default
        "text": "#1f2328",       # fgColor-default
        "muted": "#59636e",      # fgColor-muted
        "accent": "#0969da",     # fgColor-accent
        "accent_bg": "#ddf4ff",  # bgColor-accent-muted
    },
    "dark": {
        "card": "#151b23",
        "surface": "#0d1117",
        "border": "#3d444d",
        "text": "#f0f6fc",
        "muted": "#9198a1",
        "accent": "#4493f8",
        "accent_bg": "#111d2e",
    },
}

DASHES = (chr(0x2013), chr(0x2014))  # en and em dash, banned by house style

# GitHub shows a full-width README image about 343 CSS px wide on a phone.
PHONE_PX = 343
MIN_CSS_PX = 11

# Text-fit constraints collected while building: (text, font_px, kind, max_width)
# where kind is "sans", "bold" or "mono".
FIT: list[tuple[str, float, str, float]] = []


def text(x, y, s, size, fill, weight=400, anchor="start", max_width=None, mono=False):
    kind = "mono" if mono else ("bold" if weight >= 600 else "sans")
    if max_width is not None:
        FIT.append((s, size, kind, max_width))
    cls = ' class="cmd"' if mono else ""
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}"{cls}>{escape(s)}</text>'
    )


def doc(w, h, title, desc, body, t):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-labelledby="t d">\n'
        f'<title id="t">{escape(title)}</title>\n'
        f'<desc id="d">{escape(desc)}</desc>\n'
        f'<style>text {{ font-family: {FONT}; }} .cmd {{ font-family: {MONO}; }}</style>\n'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="16" '
        f'fill="{t["card"]}" stroke="{t["border"]}"/>\n'
        f"{body}\n</svg>\n"
    )


# ------------------------------------------------------- text measurement

# Advance widths of printable ASCII (space to tilde) in DejaVu Sans, Sans Bold
# and Sans Mono, per 1000 units of font size. Layout uses only these tables,
# so the SVGs come out byte for byte the same on every machine. DejaVu is wider
# than the fonts GitHub renders with, so text that fits here fits there.
WIDTHS = {
    "sans": [
        318, 401, 460, 838, 636, 950, 780, 275, 390, 390, 500, 838, 318, 361, 318, 337,
        636, 636, 636, 636, 636, 636, 636, 636, 636, 636, 337, 337, 838, 838, 838, 531,
        1000, 684, 686, 698, 770, 632, 575, 775, 752, 295, 295, 656, 557, 863, 748, 787,
        603, 787, 695, 635, 611, 732, 684, 989, 685, 611, 685, 390, 337, 390, 838, 500,
        500, 613, 635, 550, 635, 615, 352, 635, 634, 278, 278, 579, 278, 974, 634, 612,
        635, 635, 411, 521, 392, 634, 592, 818, 592, 592, 525, 636, 337, 636, 838,
    ],
    "bold": [
        348, 456, 521, 838, 696, 1002, 872, 306, 457, 457, 523, 838, 380, 415, 380, 365,
        696, 696, 696, 696, 696, 696, 696, 696, 696, 696, 400, 400, 838, 838, 838, 580,
        1000, 774, 762, 734, 830, 683, 683, 821, 837, 372, 372, 775, 637, 995, 837, 850,
        733, 850, 770, 720, 682, 812, 774, 1103, 771, 724, 725, 457, 365, 457, 838, 500,
        500, 675, 716, 593, 716, 678, 435, 716, 712, 343, 343, 665, 343, 1042, 712, 687,
        716, 716, 493, 595, 478, 712, 652, 924, 645, 652, 582, 712, 365, 712, 838,
    ],
    "mono": [602] * 95,
}


def measure(s, size, kind="sans"):
    """Width of s in px, with 2 percent to spare for kerning differences."""
    bad = [c for c in s if not 32 <= ord(c) <= 126]
    assert not bad, f"non-ASCII in label {s!r}: {bad}"
    return sum(WIDTHS[kind][ord(c) - 32] for c in s) * size / 1000 * 1.02


def wrap(s, size, kind, max_w):
    """Split s into lines no wider than max_w."""
    lines, line = [], ""
    for word in s.split():
        trial = f"{line} {word}".strip()
        if line and measure(trial, size, kind) > max_w:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


def arrow_v(x, y1, y2, color, width=3, head=12):
    """Flat vertical arrow from y1 to y2, head at y2."""
    d = 1 if y2 > y1 else -1
    end = y2 - d * head
    return (
        f'<line x1="{x}" y1="{y1:.1f}" x2="{x}" y2="{end:.1f}" stroke="{color}" stroke-width="{width}"/>'
        f'<path d="M{x - head * 0.75:.1f} {end:.1f} L{x + head * 0.75:.1f} {end:.1f} L{x} {y2:.1f} Z" fill="{color}"/>'
    )


# ----------------------------------------------------------- fork diagram

FORK_TITLE = "One project, three repositories"
FORK_SUBTITLE = "How code moves when you contribute through a fork"
SITE_LABEL = "On GitHub, GitLab or Codeberg"
LOCAL_LABEL = "On your computer"
# (name, tag or None, body)
CARD_PROJECT = ("The project", "upstream", "The original repository. Its maintainers review and merge pull requests.")
CARD_FORK = ("Your fork", "origin", "Your copy on the website, made once with the Fork button. You can push to it.")
CARD_CLONE = ("Your clone", None, "Made once by cloning your fork. You edit, commit and run tests here.")
PR_LABEL = ("Pull request", "asks the maintainers to merge your branch", "GitLab calls it a merge request")
FETCH_LABEL = ("git fetch upstream", "copies new project commits to your clone")
PUSH_LABEL = ("git push -u origin my-fix", "sends your branch to your fork")
FORK_FOOTER = "Cloning names your fork origin. Name the project upstream yourself, once:"
FORK_FOOTER_CMD = "git remote add upstream PROJECT-URL"
# Also the SVG <desc>. The README <img> alt must match it exactly (--check).
FORK_ALT = (
    "Diagram of the pull request route. On the website: the project (upstream) and your fork (origin). "
    "On your computer: your clone of your fork. git fetch upstream copies project commits to your clone; "
    "git push -u origin my-fix sends your branch to your fork; a pull request (GitLab: merge request) "
    "asks the maintainers to merge it. You add upstream yourself, once."
)


def card(x, y, w, name, tag, body, t, b):
    """Draw a card with an optional remote-name tag; return its height."""
    name_px, body_px, tag_px = 24, 22, 22
    pad_l, pad_r = 20, 16
    tag_w = measure(tag, tag_px, "bold") + 26 if tag else 0
    name_w = w - pad_l - pad_r - tag_w - 12
    names = wrap(name, name_px, "bold", name_w)
    bodies = wrap(body, body_px, "sans", w - pad_l - pad_r)
    h = 22 + len(names) * name_px * 1.25 + 6 + len(bodies) * body_px * 1.35 + 12
    b.append(f'<rect x="{x + 0.5}" y="{y:.1f}" width="{w - 1}" height="{h:.1f}" rx="12" '
             f'fill="{t["surface"]}" stroke="{t["border"]}"/>')
    ly = y + 18 + name_px
    if tag:
        tr = x + w - pad_r
        b.append(f'<rect x="{tr - tag_w:.1f}" y="{ly - name_px * 0.35 - 17:.1f}" width="{tag_w:.1f}" '
                 f'height="34" rx="17" fill="{t["accent_bg"]}"/>')
        b.append(text(round(tr - tag_w / 2, 1), round(ly - name_px * 0.35 + tag_px * 0.36, 1), tag, tag_px,
                      t["accent"], 700, "middle", max_width=tag_w - 12))
    for s in names:
        b.append(text(x + pad_l, round(ly, 1), s, name_px, t["text"], 700, max_width=name_w))
        ly += name_px * 1.25
    ly += 6 - name_px * 1.25 + body_px * 1.35
    for s in bodies:
        b.append(text(x + pad_l, round(ly, 1), s, body_px, t["muted"], max_width=w - pad_l - pad_r))
        ly += body_px * 1.35
    return h


def fork_diagram(t):
    # 22 px text in a 680 wide viewBox renders at 11.1 CSS px on a phone.
    w, m = 680, 16               # canvas width, outer margin
    title_px, body_px = 28, 22
    fx = 36                      # x of the fetch arrow, in the left gutter
    px = w - 48                  # x of the push and pull request arrows
    full = w - 48                # width of full-width text
    b = []
    y = 52
    for line in wrap(FORK_TITLE, title_px, "bold", full):
        b.append(text(24, round(y, 1), line, title_px, t["text"], 700, max_width=full))
        y += title_px * 1.25
    y += 2
    for line in wrap(FORK_SUBTITLE, body_px, "sans", full):
        b.append(text(24, round(y, 1), line, body_px, t["muted"], max_width=full))
        y += body_px * 1.35
    y += 14
    b.append(text(24, round(y, 1), SITE_LABEL, body_px, t["muted"], 700, max_width=full))
    y += 16

    # The project, full width.
    ya = y
    ha = card(m, ya, w - 2 * m, *CARD_PROJECT, t, b)
    y = ya + ha

    # Pull request label, right-aligned beside its up arrow.
    gap_top = y
    y += 14
    lab_r = px - 18
    lab_w = lab_r - fx - 24
    b.append(text(lab_r, round(y + 24, 1), PR_LABEL[0], 24, t["text"], 700, "end", max_width=lab_w))
    y += 24 + 6
    for s in [line for part in PR_LABEL[1:] for line in wrap(part, body_px, "sans", lab_w)]:
        y += body_px * 1.35
        b.append(text(lab_r, round(y, 1), s, body_px, t["muted"], 400, "end", max_width=lab_w))
    y += 18

    # Your fork, indented so the fetch arrow passes it by.
    yb = y
    bx = fx + 28
    hb = card(bx, yb, w - m - bx, *CARD_FORK, t, b)
    b.append(arrow_v(px, yb, gap_top, t["accent"]))  # fork to project: pull request
    y = yb + hb

    # Fetch label, then push label, on separate rows so commands never share one.
    gap2_top = y
    lab_w = px - fx - 36
    y += 14 + body_px
    b.append(text(fx + 16, round(y, 1), FETCH_LABEL[0], body_px, t["text"], 400, max_width=lab_w, mono=True))
    y += body_px * 1.35
    b.append(text(fx + 16, round(y, 1), FETCH_LABEL[1], body_px, t["muted"], max_width=lab_w))
    y += 16 + body_px
    b.append(text(lab_r, round(y, 1), PUSH_LABEL[0], body_px, t["text"], 400, "end", max_width=lab_w, mono=True))
    y += body_px * 1.35
    b.append(text(lab_r, round(y, 1), PUSH_LABEL[1], body_px, t["muted"], 400, "end", max_width=lab_w))
    y += 20

    # The line between the website and your computer. Fetch and push cross it;
    # the pull request does not.
    b.append(f'<line x1="{m}" y1="{y:.1f}" x2="{w - m}" y2="{y:.1f}" stroke="{t["muted"]}" '
             f'stroke-width="2" stroke-dasharray="7 7"/>')
    y += 12 + body_px
    b.append(text(fx + 16, round(y, 1), LOCAL_LABEL, body_px, t["muted"], 700, max_width=lab_w))
    y += 14

    # Your clone, full width.
    yc = y
    hc = card(m, yc, w - 2 * m, *CARD_CLONE, t, b)
    b.append(arrow_v(fx, ya + ha, yc, t["accent"]))   # project to clone: fetch
    b.append(arrow_v(px, yc, gap2_top, t["accent"]))  # clone to fork: push
    y = yc + hc + 34

    for line in wrap(FORK_FOOTER, body_px, "sans", full):
        b.append(text(24, round(y + body_px * 0.2, 1), line, body_px, t["text"], max_width=full))
        y += body_px * 1.35
    y += 4
    b.append(text(24, round(y + body_px * 0.2, 1), FORK_FOOTER_CMD, body_px, t["text"], 400, max_width=full, mono=True))
    h = round(y + 40)
    return doc(w, h, FORK_TITLE, FORK_ALT, "\n".join(b), t)


# ------------------------------------------------------------------- main

# name: (builder, alt text the README must use)
VISUALS = {
    "fork-and-pull-request": (fork_diagram, FORK_ALT),
}

FONT_CANDIDATES = {
    "sans": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf", "Arial.ttf"],
    "bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"],
    "mono": ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "DejaVuSansMono.ttf", "Menlo.ttc"],
}


def skip(reason) -> int:
    """Skip the text-fit check locally, but fail in CI so it cannot pass silently."""
    if os.environ.get("CI"):
        print(f"{reason}; the text-fit check cannot run in CI.")
        return 1
    print(f"{reason}; skipping the text-fit check.")
    return 0


def check_fit() -> int:
    try:
        from PIL import ImageFont
    except ImportError:
        return skip("Pillow not installed")
    fonts = {}
    for kind, paths in FONT_CANDIDATES.items():
        for p in paths:
            try:
                ImageFont.truetype(p, 12)
            except OSError:
                continue
            fonts[kind] = p
            break
    missing = sorted(set(FONT_CANDIDATES) - set(fonts))
    if missing:
        return skip(f"No reference font for {', '.join(missing)}")
    bad = 0
    for s, size, kind, max_w in sorted(set(FIT)):
        width = ImageFont.truetype(fonts[kind], round(size * 4)).getlength(s) / 4
        if width > max_w:
            bad += 1
            print(f"TOO WIDE ({width:.0f}px > {max_w:.0f}px): {s!r}")
    names = ", ".join(pathlib.Path(p).name for p in fonts.values())
    print(f"Text-fit check: {len(set(FIT))} labels, {bad} too wide (measured with {names}).")
    return bad


def check_size(name, svg) -> int:
    width = float(re.search(r'viewBox="0 0 ([\d.]+)', svg).group(1))
    smallest = min(float(s) for s in re.findall(r'font-size="([\d.]+)"', svg))
    css = smallest * PHONE_PX / width
    if css < MIN_CSS_PX:
        print(f"TOO SMALL: {name} has {smallest:g}px text, {css:.1f} CSS px on a phone (minimum {MIN_CSS_PX}).")
        return 1
    return 0


class ImgAlts(HTMLParser):
    """Collect src and alt of every <img> in the README."""

    def __init__(self):
        super().__init__()
        self.imgs = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            a = dict(attrs)
            self.imgs.append((a.get("src", ""), a.get("alt")))


def check_alt() -> int:
    parser = ImgAlts()
    parser.feed(README.read_text(encoding="utf-8"))
    bad = 0
    for name, (_, alt) in VISUALS.items():
        src = f"assets/{name}-light.svg"
        found = [a for s, a in parser.imgs if s == src]
        if not found:
            msg = f"README.md does not show {src}."
            if os.environ.get("CI"):
                print(msg)
                bad += 1
            else:
                print(f"note: {msg}")
        for a in found:
            if a != alt:
                print(f"ALT TEXT DIFFERS for {src}. Use exactly:\n{alt}")
                bad += 1
    return bad


def main() -> int:
    ASSETS.mkdir(exist_ok=True)
    bad = 0
    for name, (build, _) in VISUALS.items():
        for theme, t in THEMES.items():
            out = ASSETS / f"{name}-{theme}.svg"
            svg = build(t)
            assert not any(d in svg for d in DASHES), f"long dash in {out.name}"
            out.write_text(svg, encoding="utf-8")
            print(f"wrote {out.relative_to(ROOT)}")
            bad += check_size(out.name, svg)
    if "--check" in sys.argv:
        bad += check_fit() + check_alt()
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
