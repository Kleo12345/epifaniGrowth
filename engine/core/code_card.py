"""
Render a short code snippet into a clean, branded "code window" PNG — a visual
insert for journey videos ("the function I built today was…" → show the code).

Uses Pygments for syntax highlighting, then wraps it in a rounded dark card with
a mac-style title bar. Keep snippets SHORT (≈4–8 lines) and the font big so it
stays legible on a phone.
"""
import textwrap
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.styles import get_style_by_name

# Brand-ish dark card colours
CARD_BG   = (13, 18, 28)      # near-navy, matches #0a0e17 family
TITLE_BG  = (22, 28, 40)
CYAN      = (0, 242, 255)
DOTS      = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]   # red / yellow / green
# Bundled in-repo so rendering is identical on Linux, macOS, and Windows —
# don't rely on the system DejaVu font path (Linux-only).
MONO_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "DejaVuSansMono.ttf"


class _BrandStyle(get_style_by_name("monokai")):
    background_color = "#0d121c"
    highlight_color  = "#173a44"


def _title_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(MONO_FONT), size)
    except OSError:
        return ImageFont.load_default()


def render_code_card(code: str, out_path: str | Path, lang: str = "python",
                     title: str | None = None, font_size: int = 30,
                     radius: int = 20) -> Path:
    """Render `code` to a branded code-window PNG at `out_path`. Returns the path."""
    code = textwrap.dedent(code).strip("\n")

    try:
        lexer = get_lexer_by_name(lang)
    except Exception:
        try:
            lexer = guess_lexer(code)
        except Exception:
            lexer = get_lexer_by_name("text")

    fmt = ImageFormatter(
        style=_BrandStyle, font_name="DejaVu Sans Mono", font_size=font_size,
        line_numbers=False, image_pad=26, line_pad=8,
    )
    code_img = Image.open(BytesIO(highlight(code, lexer, fmt))).convert("RGBA")

    bar_h = int(font_size * 1.7)
    w, h = code_img.width, code_img.height + bar_h
    card = Image.new("RGBA", (w, h), CARD_BG)
    d = ImageDraw.Draw(card)

    # title bar
    d.rectangle([0, 0, w, bar_h], fill=TITLE_BG)
    dot_r = max(5, bar_h // 7)
    cy = bar_h // 2
    for i, col in enumerate(DOTS):
        cx = 24 + i * (dot_r * 2 + 12)
        d.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=col)
    if title:
        tf = _title_font(int(bar_h * 0.42))
        tw = d.textlength(title, font=tf)
        d.text(((w - tw) / 2, cy - bar_h * 0.24), title, font=tf, fill=(170, 185, 200))

    card.paste(code_img, (0, bar_h), code_img)

    # round the corners + cyan border
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(card, (0, 0), mask)
    ImageDraw.Draw(out).rounded_rectangle([1, 1, w - 2, h - 2], radius=radius,
                                          outline=CYAN, width=3)

    out_path = Path(out_path)
    out.save(out_path)
    return out_path
