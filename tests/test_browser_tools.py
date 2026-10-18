import pytest
import asyncio
from athena.browser_tools import (
    browser_open, browser_inspect, browser_search, 
    browser_click, browser_type, browser_scroll, browser_close,
    _is_safe_url
)

def test_safe_urls():
    assert _is_safe_url("https://example.com") == True
    assert _is_safe_url("http://google.com/search?q=test") == True
    assert _is_safe_url("http://localhost:8000") == False
    assert _is_safe_url("http://127.0.0.1") == False
    assert _is_safe_url("file:///etc/passwd") == False

@pytest.mark.asyncio
async def test_browser_flow():
    # Test opening a public page
    res = await browser_open("https://example.com")
    assert res["status"] == "success"
    assert "Example Domain" in res["title"]
    
    # Test reading content
    res = await browser_inspect()
    assert res["status"] == "success"
    assert "Example Domain" in res["title"]
    assert "Learn more" in res["text_preview"] or "More information" in res["text_preview"]
    assert len(res["interactive_elements"]) > 0
    
    # Test clicking an element
    res = await browser_click("Learn more")
    if res["status"] != "success":
        res = await browser_click("More information...")
    assert res["status"] == "success"
    
    # Test scrolling
    res = await browser_scroll("down")
    assert res["status"] == "success"
    
    # Test invalid URLs
    res = await browser_open("http://127.0.0.1:8080")
    assert res["status"] == "error"
    
    # Test session cleanup
    res = await browser_close()
    assert res["status"] == "success"
    
    # Duplicate close should be fine
    res = await browser_close()
    assert res["status"] == "success"
