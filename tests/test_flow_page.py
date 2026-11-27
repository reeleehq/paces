"""The flow page in a real browser: the states a viewer moves through.

Skipped when playwright or a chromium build is not installed (CI has neither);
the player's logic is covered under node in ``test_render_flow.py`` and the
folder it writes in the rest of that file.
"""

from __future__ import annotations

import functools
import http.server
import json
import threading

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

from paces.model import Measure, Step, StepDocument  # noqa: E402
from paces.render_flow import render_flow  # noqa: E402


def _circuit() -> StepDocument:
    leaf = lambda i, n, v, u, **k: Step(id=i, name=n, duration=Measure(value=v, unit=u), **k)
    return StepDocument(
        id="circuit",
        title="Bodyweight circuit",
        steps=[
            leaf("warm", "Warm-up", "30", "second"),
            Step(
                id="round",
                name="Round",
                duration=Measure(value="30", unit="rep"),
                repeat=3,
                steps=[leaf("squat", "Squat", "10", "rep"), leaf("push", "Push-up", "10", "rep")],
            ),
        ],
    )


@pytest.fixture(scope="module")
def page_url(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    doc = _circuit()
    doc.steps[1].steps.append(
        Step(
            id="rest",
            name="Rest",
            duration=Measure(value="0", unit="second"),
            tags=["learner-led", "between-passes"],
        )
    )
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        render_flow(doc, out)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()


@pytest.fixture()
def browser_page():
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:  # no browser build installed
            pytest.skip(f"chromium is not available: {error}")
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        yield page, errors
        browser.close()
    assert not errors, errors


def test_overview_then_step_through_then_the_sheet(page_url, browser_page):
    page, errors = browser_page
    page.goto(page_url)
    page.wait_for_selector(".overview")
    assert "Start" in page.inner_text(".overview")
    assert page.locator(".bar").is_hidden()  # no step controls on the overview
    page.click("text=Step through")
    page.wait_for_selector(".bigcount")
    assert page.inner_text(".head h2").lower() == "warm-up"
    page.keyboard.press("ArrowRight")
    assert page.evaluate("player.state.i") == 1
    page.click(".stripbtn")
    page.wait_for_selector(".sheet")
    page.click(".sheet .ol >> nth=0")
    assert page.evaluate("player.state.i") == 0 and page.locator(".sheet").count() == 0


def test_a_link_with_a_position_skips_the_overview(page_url, browser_page):
    page, _ = browser_page
    page.goto(page_url + "#s=2")
    page.wait_for_selector(".bigcount")
    assert page.evaluate("player.state.i") == 2


def test_timed_mode_counts_in_runs_waits_on_a_learner_led_step_and_finishes(page_url, browser_page):
    page, _ = browser_page
    page.goto(page_url)
    page.wait_for_selector(".overview")
    page.evaluate("player.state.settings.secondsPerRep = 0.05; player.state.settings.secondsPerStep = 0.1")
    page.click(".bigbtn.primary")  # Start: timed, with a get-ready count-in
    page.wait_for_selector(".bigcount.getready")
    page.evaluate("player.state.countIn = 0.01")
    # the 30 s warm-up is a step in seconds: jump past it to the repetition steps
    page.evaluate("player.go(1)")
    page.wait_for_function("player.state.waiting === true", timeout=8000)  # reached the learner-led rest
    assert page.inner_text(".play").strip() == "" and "ready" in page.inner_text(".playwrap").lower()
    page.click(".play")  # Ready
    page.wait_for_function("player.state.i === 4 || player.state.waiting", timeout=8000)
    assert page.evaluate("player.state.i") >= 4


def test_the_routine_ends_on_a_done_card_with_restart(page_url, browser_page):
    page, _ = browser_page
    page.goto(page_url + "#s=0")
    page.wait_for_selector(".bigcount")
    last = page.evaluate("player.stops.length - 1")
    assert page.evaluate("player.stops[player.stops.length - 1].step.id") != "rest"  # not ending on a rest
    page.evaluate(f"player.go({last})")
    page.evaluate("player.state.settings.secondsPerRep = 0.02")
    page.click(".modes .chip >> nth=0")  # timed
    page.click(".play")
    page.wait_for_selector(".overview.done", timeout=8000)
    assert "Restart" in page.inner_text(".overview")
    page.click("text=Restart")
    page.wait_for_selector(".bigcount")
