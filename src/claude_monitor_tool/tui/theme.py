"""Claude-native color theme for the Textual TUI.

Follows Claude Code's visual language:
- Purple/violet primary accent
- Warm orange secondary
- Slate grays for structure
- Minimal, restrained palette
"""

# ── Brand Colors ──────────────────────────────────────────────
PURPLE = "#A78BFA"          # Primary accent (Claude violet)
PURPLE_DIM = "#7C3AED"      # Darker purple for borders
PURPLE_BRIGHT = "#C4B5FD"   # Light purple for highlights
ORANGE = "#F59E0B"           # Secondary accent (Claude warm)
ORANGE_DIM = "#D97706"       # Darker orange

# ── Semantic Colors ───────────────────────────────────────────
GREEN = "#10B981"            # Success / healthy / low usage
YELLOW = "#F59E0B"           # Warning / medium usage
RED = "#EF4444"              # Error / critical / high usage
CYAN = "#06B6D4"             # Info / links

# ── Neutral Palette ───────────────────────────────────────────
BG_DARK = "#0F172A"          # Deep background
BG_SURFACE = "#1E293B"       # Card / panel surface
BG_ELEVATED = "#334155"      # Elevated surface (hover)
BORDER = "#475569"           # Default border
TEXT_PRIMARY = "#F8FAFC"     # Primary text
TEXT_SECONDARY = "#CBD5E1"   # Secondary text
TEXT_MUTED = "#64748B"       # Muted / dim text
TEXT_DIM = "#475569"         # Very dim text

# ── Progress Bar Colors ───────────────────────────────────────
BAR_LOW = "#10B981"          # 0-49%: green
BAR_MED = "#F59E0B"          # 50-79%: amber
BAR_HIGH = "#F97316"         # 80-89%: orange
BAR_CRIT = "#EF4444"         # 90-100%: red
BAR_EMPTY = "#334155"        # Empty track

# ── Model Colors ──────────────────────────────────────────────
MODEL_OPUS = "#A78BFA"       # Purple for Opus
MODEL_SONNET = "#06B6D4"     # Cyan for Sonnet
MODEL_HAIKU = "#10B981"      # Green for Haiku


def bar_color(pct: float) -> str:
    """Return color hex for a percentage value."""
    if pct >= 90:
        return BAR_CRIT
    if pct >= 80:
        return BAR_HIGH
    if pct >= 50:
        return BAR_MED
    return BAR_LOW


def model_color(name: str) -> str:
    """Return color hex for a model name."""
    n = name.lower()
    if "opus" in n:
        return MODEL_OPUS
    if "sonnet" in n:
        return MODEL_SONNET
    if "haiku" in n:
        return MODEL_HAIKU
    return TEXT_MUTED


THEME_CSS = """
Screen {
    background: #0F172A;
    color: #F8FAFC;
}

Footer {
    background: #1E293B;
    color: #64748B;
    dock: bottom;
    height: 1;
}

Footer > .footer--key {
    color: #A78BFA;
    text-style: bold;
    background: #334155;
}

Footer > .footer--description {
    color: #CBD5E1;
}

/* ── Data Table ───────────────────────────────────────────── */

DataTable {
    background: #1E293B;
    height: 1fr;
}

DataTable > .datatable--header {
    background: #334155;
    color: #A78BFA;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #334155;
    color: #F8FAFC;
}

DataTable > .datatable--even-row {
    background: #1E293B;
}

DataTable > .datatable--odd-row {
    background: #0F172A;
}

/* ── Scrollbar ────────────────────────────────────────────── */

Scrollbar {
    background: #1E293B;
    color: #475569;
}

/* ── Tab Pane ─────────────────────────────────────────────── */

TabbedContent {
    height: 1fr;
}

ContentSwitcher {
    height: 1fr;
}

TabPane {
    padding: 0;
    height: 1fr;
}

Tabs {
    background: #1E293B;
    height: 2;
}

Tab {
    color: #64748B;
    background: #1E293B;
}

Tab.-active {
    color: #A78BFA;
    text-style: bold;
}

Tab:hover {
    color: #C4B5FD;
}

Underline {
    color: #A78BFA;
}
"""
