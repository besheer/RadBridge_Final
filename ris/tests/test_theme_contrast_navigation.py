from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static" / "app.css").read_text(encoding="utf-8")
BASE = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")


def _relative_luminance(color):
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    channels = [
        value / 12.92 if value <= 0.04045
        else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(foreground, background):
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_accessible_theme_contract_markers_exist():
    assert "RB_PHASE25_ACCESSIBLE_THEME_CONTRAST_V1" in CSS
    assert 'id="rb-nav-v4-style"' in BASE
    assert ".sidebar .rb-nav-group>summary::after" in CSS
    assert ".btn:focus-visible" in CSS
    assert "input::placeholder" in CSS


def test_navigation_and_secondary_text_colors_meet_wcag_aa():
    combinations = (
        ("#b8c5d6", "#0b1220"),  # dark secondary copy
        ("#b7c6d9", "#07111f"),  # sidebar group labels
        ("#e5eef9", "#07111f"),  # sidebar links
        ("#94a3b8", "#0f192a"),  # dark input placeholder
        ("#52627a", "#f4f7fb"),  # light secondary copy
        ("#ffffff", "#2563eb"),  # primary button label
    )
    for foreground, background in combinations:
        assert _contrast(foreground, background) >= 4.5


def test_dashboard_uses_semantic_theme_colors_not_faded_fixed_copy():
    assert "var(--rb-text-muted,var(--muted))" in DASHBOARD
    assert "var(--rb-card,var(--panel))" in DASHBOARD
    assert "var(--rb-info-bg" in DASHBOARD
    assert "color:#91a8bc" not in DASHBOARD
    assert "background:#193650" not in DASHBOARD


def test_sidebar_group_controls_are_not_dimmed():
    assert 'opacity:.55' not in BASE
    for declaration in (
        "color:#b7c6d9",
        "font-size:11px",
        "opacity:1",
        "color:#9fc2ee",
    ):
        assert declaration in CSS


def test_mixed_light_dark_surfaces_keep_text_visible():
    assert "RB_PHASE25B_MIXED_SURFACE_CONTRAST_V1" in CSS
    assert "body.theme-dark .app-header" in CSS
    assert "body.theme-dark .lang-btn" in CSS
    assert "body.theme-dark .studio-card" in CSS
    assert ".sidebar .pacs-mini.online small" in CSS
    assert _contrast("#b8c5d6", "#111b2e") >= 4.5
    assert _contrast("#f3f7fc", "#162238") >= 4.5


def test_global_theme_compatibility_covers_authenticated_legacy_surfaces():
    marker = "RB_PHASE25C_GLOBAL_THEME_COMPATIBILITY_V1"
    assert marker in CSS
    compatibility = CSS.split(marker, 1)[1]
    legacy_surfaces = (
        ".management-kpis>div",
        ".exec-kpis>div",
        ".ops-kpis>div",
        ".ops-health-strip>div",
        ".metric-card",
        ".studio-shortcut-row",
        ".studio-launcher-item",
        ".si-card",
        ".status-card",
        ".ocr-card",
        ".confirm-dialog",
    )
    for selector in legacy_surfaces:
        assert compatibility.count(selector) >= 2


def test_management_kpis_follow_theme_instead_of_fixed_white_surface():
    compatibility = CSS.split("RB_PHASE25C_GLOBAL_THEME_COMPATIBILITY_V1", 1)[1]
    assert ".management-kpis>div" in compatibility
    assert "background:var(--rb-card,var(--panel))" in compatibility
    assert ") :is(h1,h2,h3,h4,b,strong){color:var(--rb-text-main" in compatibility
    assert ") :is(p,span,small,label){color:var(--rb-text-muted" in compatibility
    assert _contrast("#f3f7fc", "#111b2e") >= 4.5
