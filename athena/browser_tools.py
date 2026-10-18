import asyncio
from urllib.parse import urlparse
import ipaddress
import socket
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser, Playwright, BrowserContext

_playwright: Optional[Playwright] = None
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None
_page: Optional[Page] = None
_cleanup_task: Optional[asyncio.Task] = None

def _is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
            
        hostname = parsed.hostname
        if not hostname:
            return False
            
        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False
            
        try:
            ip_obj = ipaddress.ip_address(hostname)
            if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_reserved:
                return False
        except ValueError:
            pass
            
        return True
    except Exception:
        return False

async def _get_or_create_page() -> Page:
    global _playwright, _browser, _context, _page
    if not _playwright:
        _playwright = await async_playwright().start()
    if not _browser:
        _browser = await _playwright.chromium.launch(headless=False)
    if not _context:
        _context = await _browser.new_context()
    if not _page:
        _page = await _context.new_page()
    return _page

async def browser_open(url: str) -> dict:
    """Open a URL in the visible browser.
    
    Args:
        url: The complete HTTP or HTTPS URL to open.
    """
    if not _is_safe_url(url):
        return {"status": "error", "message": "Unsafe or invalid URL. Only public HTTP/HTTPS URLs are allowed."}
    
    try:
        page = await _get_or_create_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        title = await page.title()
        return {"status": "success", "message": f"Opened {url}", "title": title}
    except Exception as e:
        return {"status": "error", "message": f"Failed to open URL: {str(e)}"}

async def browser_inspect() -> dict:
    """Inspect the current visible page content and interactive elements.
    Use this to read the page text or find elements before clicking/typing.
    """
    try:
        if not _page:
            return {"status": "error", "message": "No browser page is currently open."}
        
        title = await _page.title()
        url = _page.url
        
        # Read text, limiting length
        text_content = await _page.evaluate("document.body.innerText.substring(0, 3000)")
        
        # Get clickable elements
        elements = await _page.evaluate('''() => {
            const items = [];
            document.querySelectorAll('a, button, input').forEach(el => {
                if (items.length < 50 && el.offsetParent !== null) {
                    let text = el.innerText || el.value || el.name || el.placeholder || el.id;
                    if (text && text.trim().length > 0) {
                        items.push({tag: el.tagName.toLowerCase(), text: text.trim().substring(0, 50)});
                    }
                }
            });
            return items;
        }''')
        
        return {
            "status": "success", 
            "title": title, 
            "url": url, 
            "text_preview": text_content,
            "interactive_elements": elements
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to inspect page: {str(e)}"}

async def browser_search(query: str) -> dict:
    """Search the web using Google Search.
    
    Args:
        query: The search query string.
    """
    return await browser_open(f"https://www.google.com/search?q={query}")

async def browser_click(element_name: str) -> dict:
    """Click a visible element on the page by its text content or name.
    
    Args:
        element_name: The visible text or name of the button/link to click.
    """
    try:
        if not _page:
            return {"status": "error", "message": "No browser page is open."}
            
        locators = [
            _page.get_by_role("button", name=element_name),
            _page.get_by_role("link", name=element_name),
            _page.get_by_text(element_name, exact=True),
            _page.get_by_text(element_name, exact=False)
        ]
        
        for locator in locators:
            if await locator.count() > 0:
                await locator.first.click(timeout=5000)
                await _page.wait_for_load_state("domcontentloaded", timeout=10000)
                return {"status": "success", "message": f"Clicked '{element_name}'"}
                
        return {"status": "error", "message": f"Element '{element_name}' not found or not clickable."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to click element: {str(e)}"}

async def browser_type(element_name: str, text: str) -> dict:
    """Type text into a form field.
    
    Args:
        element_name: The visible text, label, or placeholder of the input field.
        text: The text to type.
    """
    try:
        if not _page:
            return {"status": "error", "message": "No browser page is open."}
            
        locators = [
            _page.get_by_role("textbox", name=element_name),
            _page.get_by_placeholder(element_name),
            _page.locator(f"input[name='{element_name}']")
        ]
        
        for locator in locators:
            if await locator.count() > 0:
                await locator.first.fill(text, timeout=5000)
                return {"status": "success", "message": f"Typed text into '{element_name}'"}
                
        return {"status": "error", "message": f"Input field '{element_name}' not found."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to type text: {str(e)}"}

async def browser_scroll(direction: str) -> dict:
    """Scroll the page up or down.
    
    Args:
        direction: 'up' or 'down'.
    """
    try:
        if not _page:
            return {"status": "error", "message": "No browser page is open."}
            
        if direction.lower() == 'down':
            await _page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
        elif direction.lower() == 'up':
            await _page.evaluate("window.scrollBy(0, -window.innerHeight * 0.8)")
        else:
            return {"status": "error", "message": "Direction must be 'up' or 'down'."}
            
        return {"status": "success", "message": f"Scrolled {direction}"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to scroll: {str(e)}"}

async def browser_close() -> dict:
    """Close the visible browser session."""
    global _playwright, _browser, _context, _page
    try:
        if _browser:
            await _browser.close()
        if _playwright:
            await _playwright.stop()
            
        _playwright = None
        _browser = None
        _context = None
        _page = None
        return {"status": "success", "message": "Browser closed"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to close browser: {str(e)}"}
