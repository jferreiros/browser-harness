"""Agent-editable browser helpers.

Add task-specific browser primitives here. Core helpers from browser_harness.helpers
load this file when BH_AGENT_WORKSPACE points at this directory, or when this
repo's default agent-workspace exists.
"""


def _norm(url):
    """Normalise a URL for comparison: drop the fragment, and for file:// URLs
    compare the decoded path so /a/b.html and file:///a/b.html%20 match."""
    from urllib.parse import urlsplit, unquote
    if not url:
        return ""
    u = url.strip()
    if u.startswith("/"):
        u = "file://" + u
    p = urlsplit(u)
    path = unquote(p.path).rstrip("/")
    if p.scheme == "file":
        return "file://" + path
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return f"{p.scheme}://{host}{path}"


def find_tab(url):
    """Return the first open tab matching url, or None. Ignores fragments and
    trailing slashes; for file:// URLs it compares the decoded path."""
    from browser_harness.helpers import list_tabs
    want = _norm(url)
    if not want:
        return None
    for t in list_tabs(include_chrome=False):
        if _norm(t.get("url", "")) == want:
            return t
    return None


def open_or_focus(url, reload=True):
    """Open url, or focus the tab that already has it.

    This is the default way an agent should put something in front of Joaquín.
    Opening the same report twice must not leave two tabs behind.

    Upstream switch_tab()/new_tab() no longer bring a tab to the front, so this
    helper calls activate_tab() explicitly: its purpose is to show the page.

    Returns a dict: {"targetId", "url", "title", "action": "focused"|"opened"}.
    """
    from browser_harness.helpers import (
        switch_tab, activate_tab, goto_url, wait_for_load, current_tab, new_tab,
    )
    hit = find_tab(url)
    if hit:
        switch_tab(hit["targetId"])
        if reload:
            goto_url(url)
            wait_for_load()
        activate_tab(hit["targetId"])
        info = current_tab()
        info["action"] = "focused"
        return info
    tid = new_tab(url)
    wait_for_load()
    activate_tab(tid)
    info = current_tab()
    info["action"] = "opened"
    return info


def close_duplicate_tabs(url=None):
    """Close duplicate tabs, keeping the first of each URL. With url given, only
    dedupes that URL. Returns how many tabs were closed."""
    from browser_harness.helpers import list_tabs, cdp
    seen, closed = {}, 0
    for t in list_tabs(include_chrome=False):       
        key = _norm(t.get("url", ""))
        if not key or (url and key != _norm(url)):
            continue
        if key in seen:
            try:
                cdp("Target.closeTarget", targetId=t["targetId"])
                closed += 1
            except Exception:
                pass
        else:
            seen[key] = t["targetId"]
    return closed


def show_report(path, reload=True):
    """Put a locally generated HTML report in front of Joaquín, reusing its tab.

    Accepts a filesystem path or a file:// URL. Use this instead of new_tab()
    for every report, plan, deck or mockup you generate.
    """
    import os
    p = path[7:] if str(path).startswith("file://") else str(path)
    p = os.path.abspath(os.path.expanduser(p))
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    return open_or_focus("file://" + p, reload=reload)


def attach_quiet(target):
    """Drive a tab without bringing it to the front.

    Kept for older instructions. Upstream switch_tab() now attaches without
    activating, so this is a thin wrapper around it. Returns the session id.
    """
    from browser_harness.helpers import switch_tab
    return switch_tab(target)


def new_background_tab(url, browser_context_id=None):
    """Open url in a background tab and attach to it without stealing focus.

    Without browser_context_id this is the same as upstream new_tab(url), except
    that it always creates a fresh tab. With browser_context_id the tab opens in
    that Chrome browser context. Returns the targetId.
    """
    from browser_harness.helpers import cdp, switch_tab, goto_url
    params = {"url": "about:blank", "background": True}
    if browser_context_id:
        params["browserContextId"] = browser_context_id
    tid = cdp("Target.createTarget", **params)["targetId"]
    switch_tab(tid)
    if url != "about:blank":
        goto_url(url)
    return tid
