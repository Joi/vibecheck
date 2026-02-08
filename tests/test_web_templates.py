"""Tests for template rendering - verifying block inheritance works."""
import pytest
from jinja2 import Environment, FileSystemLoader
from pathlib import Path


@pytest.fixture
def jinja_env():
    """Create a Jinja2 environment pointing at the templates directory."""
    templates_dir = Path(__file__).parent.parent / "src" / "vibecheck" / "templates"
    return Environment(loader=FileSystemLoader(str(templates_dir)))


class TestTemplateBlockInheritance:
    """Verify that child templates' style blocks are actually rendered."""

    def test_discover_styles_present_in_rendered_html(self, jinja_env):
        template = jinja_env.get_template("discover.html")
        html = template.render(request=None, active_page="discover", items=[], mode="mixed")
        assert ".discover-container" in html
        assert ".swipe-card" in html

    def test_bookmarks_styles_present_in_rendered_html(self, jinja_env):
        template = jinja_env.get_template("bookmarks.html")
        html = template.render(request=None, active_page="bookmarks")
        assert ".bookmark-card" in html


class TestAccessibility:
    """Verify accessibility requirements are met in templates."""

    def test_base_template_has_reduced_motion_css(self, jinja_env):
        """base.html must include a prefers-reduced-motion media query."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "prefers-reduced-motion" in html, (
            "base.html must include @media (prefers-reduced-motion: reduce) "
            "to respect user motion preferences (WCAG 2.1 AA)."
        )

    def test_discover_js_checks_reduced_motion(self, jinja_env):
        """Discover page JS must check prefers-reduced-motion for gesture animations."""
        template = jinja_env.get_template("discover.html")
        html = template.render(request=None, active_page="discover", items=[], mode="mixed")
        assert "prefers-reduced-motion" in html, (
            "Discover page JS must check prefers-reduced-motion to disable "
            "spring animations and fly-off effects."
        )


class TestResponsiveCSS:
    """Verify responsive CSS patterns in templates."""

    def test_card_grid_is_mobile_first(self, jinja_env):
        """Card grid must use 1fr default (not minmax(350px)) to prevent phone overflow."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "minmax(350px" not in html, (
            "Card grid still uses minmax(350px, 1fr) as default. "
            "This overflows on phones < 400px wide. Use 1fr default."
        )


class TestMobileNavigation:
    """Verify mobile navigation elements exist."""

    def test_hamburger_button_exists(self, jinja_env):
        """base.html must have a hamburger menu button for mobile."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "nav-toggle" in html, (
            "base.html must include a hamburger menu button (class=nav-toggle) "
            "for mobile viewports."
        )

    def test_hamburger_has_aria_attributes(self, jinja_env):
        """Hamburger button must have proper ARIA attributes."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert 'aria-expanded' in html, "Hamburger button must have aria-expanded attribute."
        assert 'aria-label' in html, "Hamburger button must have aria-label attribute."


class TestNavigation:
    """Verify navigation completeness."""

    def test_bookmarks_link_in_nav(self, jinja_env):
        """Navigation must include a link to the bookmarks page."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert '/bookmarks' in html, (
            "Navigation must include a link to /bookmarks. "
            "The route exists (web.py) and Discover saves bookmarks, "
            "but users can't find them."
        )

    def test_bookmarks_link_active_state(self, jinja_env):
        """Bookmarks nav link must have active class when on bookmarks page."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="bookmarks")
        import re
        bookmarks_link = re.search(r'<a[^>]*href="/bookmarks"[^>]*>', html)
        assert bookmarks_link is not None, "Bookmarks link not found in nav"
        assert 'active' in bookmarks_link.group(), (
            "Bookmarks link should have 'active' class when active_page='bookmarks'"
        )
