"""DailyValue palette and type: a nutrition facts label (black ink on white, heavy and thin rules, condensed bold type)
on a pale kitchen counter, with a turmeric highlighter for what was cited."""

COUNTER = "#efede8"
LABEL = "#ffffff"
INK = "#141414"
MUTED = "#4a4a4a"
FAINT = "#6b6b6b"
RULE = "#141414"
SOFT_RULE = "#d6d3cc"
ACCENT = "#8f5d00"        # turmeric, dark enough for text and the focus ring
HIGHLIGHT = "#ffe7a3"     # highlighter on cited text
HIGHLIGHT_SOFT = "#fff4d1"

ORG_COLOR = {"MedlinePlus": "#1f5f8b", "NHLBI": "#a3332b", "NIDDK": "#2f6b3a"}

SAFETY = {   # label -> (heading, icon, colour)
    "crisis": ("Please reach out for support", "favorite", "#a3332b"),
    "emergency": ("This needs urgent care", "emergency", "#a3332b"),
    "harmful": ("Not something I can help with", "block", "#8f5d00"),
    "manipulation": ("Nutrition questions only", "shield", "#4a4a4a"),
}

HEAD = "'Archivo', 'Arial Narrow', sans-serif"
BODY = "'Archivo', 'Segoe UI', sans-serif"
MONO = "'Spline Sans Mono', Consolas, monospace"
