"""
WhatsApp Automation Engine: Playwright-powered controller with persistent login session.
Monitors the target chat 'Keerthana Chemical Engineering' for incoming messages and sends replies.
Uses an in-browser JavaScript evaluation engine for instant, bulletproof message detection.
Uses a thread-safe command dispatch queue to ensure all Playwright operations run on the owning thread.
"""
import time
import queue
import threading
import concurrent.futures
from typing import Callable, Optional
from playwright.sync_api import sync_playwright, Page, BrowserContext
import config


# In-Browser JavaScript Evaluators for Maximum Speed & Resilience against DOM Changes
JS_CHECK_CHAT_OPEN = """
() => {
    // 1. Check any header on the page for contact name
    const headers = document.querySelectorAll('header, div[role="main"] header, #main header');
    for (const h of headers) {
        const text = (h.innerText || '').toLowerCase();
        if (text.includes('keerthana')) return true;
        for (const el of h.querySelectorAll('[title]')) {
            if ((el.getAttribute('title') || '').toLowerCase().includes('keerthana')) return true;
        }
    }
    // 2. Check main conversation panel
    const mainPane = document.querySelector('#main, div[id="main"], div[role="main"], div[data-testid*="conversation"]');
    if (mainPane) {
        const text = (mainPane.innerText || '').toLowerCase();
        if (text.slice(0, 350).includes('keerthana')) return true;
    }
    return false;
}
"""

JS_EXTRACT_INCOMING_MESSAGES = """
() => {
    const results = [];
    const seenKeys = new Set();
    
    // Main conversation container
    const mainPane = document.querySelector('#main, div[id="main"], div[role="main"], div[data-testid*="conversation"]') || document;
    
    // Select all potential message nodes
    const candidates = mainPane.querySelectorAll('[data-id], .message-in, [class*="message-in"], [data-pre-plain-text]');
    
    for (const el of candidates) {
        // 1. Determine outgoing vs incoming
        let did = el.getAttribute('data-id') || '';
        if (!did) {
            const parent = el.closest('[data-id]');
            if (parent) did = parent.getAttribute('data-id') || '';
        }

        const isExplicitOutgoing = (did && did.startsWith('true_')) || 
                                   el.classList.contains('message-out') || 
                                   (el.className && typeof el.className === 'string' && el.className.includes('message-out'));
        if (isExplicitOutgoing) continue;

        // Check data-pre-plain-text (e.g. "[8:15 pm, 3/9/2026] Keerthana Chemical Engineering: ")
        let preText = el.getAttribute('data-pre-plain-text') || '';
        if (!preText) {
            const preChild = el.querySelector('[data-pre-plain-text]');
            if (preChild) preText = preChild.getAttribute('data-pre-plain-text') || '';
        }

        // If preText contains "You:", it's our own outgoing message
        if (preText && (preText.includes('You:') || preText.includes('You :'))) continue;

        // 2. Extract message text cleanly
        let text = '';
        const textEl = el.querySelector('.selectable-text, .copyable-text, span[dir="ltr"], span[dir="auto"], p.selectable-text');
        if (textEl) {
            text = (textEl.innerText || textEl.textContent || '').trim();
        } else if (el.classList.contains('selectable-text') || el.classList.contains('copyable-text')) {
            text = (el.innerText || el.textContent || '').trim();
        } else {
            // Fallback to body text minus timestamp
            const fullText = (el.innerText || '').trim();
            const lines = fullText.split('\\n').map(l => l.trim()).filter(Boolean);
            const bodyLines = lines.filter(l => !(/^(0?[1-9]|1[0-2]):[0-5][0-9]\\s*(am|pm)$/i.test(l)));
            if (bodyLines.length > 0) {
                text = bodyLines.join(' ');
            }
        }

        if (text) {
            // Unique key to prevent duplicates
            const key = did ? did : (preText ? (preText + '_' + text) : text);
            if (!seenKeys.has(key)) {
                seenKeys.add(key);
                results.push({
                    key: key,
                    id: did,
                    text: text,
                    preText: preText
                });
            }
        }
    }
    return results;
}
"""

JS_CHECK_AND_CLICK_SIDEBAR_UNREAD = """
() => {
    const sidebar = document.querySelector('#pane-side, div[role="grid"], div[aria-label*="Chat"]') || document;
    const rows = sidebar.querySelectorAll('[role="row"], [role="listitem"], div[data-testid*="cell-frame"]');
    
    for (const row of rows) {
        const text = (row.innerText || '').toLowerCase();
        if (text.includes('keerthana')) {
            // Check for unread badge
            const unreadEl = row.querySelector('[aria-label*="unread" i], [class*="unread" i], span[data-icon="unread"]');
            const hasUnread = Boolean(unreadEl) || Array.from(row.querySelectorAll('span')).some(s => /^\\d+$/.test(s.innerText.trim()) && s.offsetHeight > 0);
            
            if (hasUnread) {
                const clickable = row.querySelector('div[role="button"]') || row;
                clickable.click();
                return { hasUnread: true, clicked: true };
            }
            return { hasUnread: false, clicked: false };
        }
    }
    return { hasUnread: false, clicked: false };
}
"""

JS_CLICK_KEERTHANA_SIDEBAR = """
() => {
    const sidebar = document.querySelector('#pane-side, div[role="grid"], div[aria-label*="Chat"]') || document;
    const elements = sidebar.querySelectorAll('[title], span');
    for (const el of elements) {
        const title = (el.getAttribute('title') || '').toLowerCase();
        const text = (el.innerText || '').toLowerCase();
        if (title.includes('keerthana') || text.includes('keerthana')) {
            const clickable = el.closest('div[role="listitem"], div[role="row"], div[data-testid*="cell-frame"]') || el;
            clickable.click();
            return true;
        }
    }
    return false;
}
"""


class WhatsAppBot:
    def __init__(
        self,
        on_message: Optional[Callable[[str, str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ):
        self.on_message = on_message
        self.on_status = on_status
        self.running = False
        self.logged_in = False
        self.chat_opened = False
        self.initial_snapshot_done = False
        self.seen_message_ids = set()
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._thread: Optional[threading.Thread] = None
        self._command_queue: queue.Queue = queue.Queue()

    def update_status(self, status: str):
        print(f"[WhatsApp] {status}")
        if self.on_status:
            self.on_status(status)

    def start(self):
        """Starts WhatsApp bot in a dedicated background worker thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the WhatsApp bot and closes browser session."""
        self.running = False
        try:
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            print(f"[WhatsApp] Close notice: {e}")
        self.update_status("Stopped.")

    def _run_loop(self):
        """
        Dedicated worker thread that owns Playwright.
        All Playwright page and browser interactions happen ONLY on this thread.
        """
        try:
            self.update_status("Starting browser...")
            self.playwright = sync_playwright().start()

            launch_kwargs = {
                "user_data_dir": str(config.SESSION_DIR),
                "headless": config.HEADLESS,
                "viewport": {"width": 1280, "height": 850},
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            }
            channel = getattr(config, "BROWSER_CHANNEL", "msedge")
            try:
                if channel:
                    self.context = self.playwright.chromium.launch_persistent_context(
                        **launch_kwargs, channel=channel
                    )
                else:
                    self.context = self.playwright.chromium.launch_persistent_context(
                        **launch_kwargs
                    )
            except Exception as launch_err:
                print(f"[WhatsApp] Notice with channel '{channel}': {launch_err}. Falling back to default browser...")
                self.context = self.playwright.chromium.launch_persistent_context(
                    **launch_kwargs
                )

            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.update_status("Navigating to WhatsApp Web...")
            self.page.goto(config.WHATSAPP_WEB_URL, wait_until="load", timeout=60000)

            # Wait for login or QR code
            self._wait_for_login()

            # Open target chat
            if self.running:
                self._do_open_target_chat(config.TARGET_CHAT)

            # Main Event & Command Loop
            while self.running:
                # 1. Process queued commands from other threads (e.g. GUI, audio callbacks)
                while not self._command_queue.empty():
                    try:
                        action, args, future = self._command_queue.get_nowait()
                        try:
                            res = action(*args)
                            if not future.done():
                                future.set_result(res)
                        except Exception as ex:
                            if not future.done():
                                future.set_exception(ex)
                    except queue.Empty:
                        break

                # 2. Check for incoming messages
                try:
                    self._check_for_new_messages()
                except Exception:
                    pass

                time.sleep(0.5)

        except Exception as e:
            self.update_status(f"Error: {e}")
            print(f"[WhatsApp Fatal Error] {e}")

    def _wait_for_login(self):
        """Waits for user to be logged into WhatsApp Web."""
        self.update_status("Checking login status...")

        while self.running:
            try:
                # Check for QR code
                qr_canvas = self.page.query_selector('canvas[aria-label="Scan me!"]') or \
                            self.page.query_selector('[data-ref]') or \
                            self.page.query_selector('div[data-testid="qrcode"]')

                # Check for chat list or search bar (indicates logged in)
                chat_list = self.page.query_selector('div[data-testid="chat-list"]') or \
                            self.page.query_selector('div[contenteditable="true"][data-tab="3"]') or \
                            self.page.query_selector('div[id="pane-side"]') or \
                            self.page.query_selector('header')

                if qr_canvas and not self.logged_in:
                    self.update_status("Waiting for QR code scan... Please scan with your phone.")
                elif chat_list:
                    self.logged_in = True
                    self.update_status("WhatsApp Web connected successfully!")
                    time.sleep(2.0)
                    return

            except Exception:
                pass
            time.sleep(1.5)

    def _is_target_chat_open(self) -> bool:
        """Checks if Keerthana's chat is currently active in the chat pane."""
        try:
            return bool(self.page.evaluate(JS_CHECK_CHAT_OPEN))
        except Exception:
            return False

    def _do_open_target_chat(self, chat_name: str):
        """Finds and opens the target chat ('Keerthana Chemical Engineering')."""
        self.update_status(f"Locating chat '{chat_name}'...")
        try:
            # 1. Check if already active
            if self._is_target_chat_open():
                self.chat_opened = True
                self.update_status(f"Chat '{chat_name}' is already active.")
                self._snapshot_existing_messages()
                return

            # 2. Try clicking directly from sidebar via JavaScript
            clicked = self.page.evaluate(JS_CLICK_KEERTHANA_SIDEBAR)
            if clicked:
                self.update_status(f"Clicked '{chat_name}' in sidebar...")
                time.sleep(1.5)
                if self._is_target_chat_open():
                    self.chat_opened = True
                    self.update_status(f"Opened chat: {chat_name}")
                    self._snapshot_existing_messages()
                    return

            # 3. Fallback: Search bar typing
            self.update_status("Searching for chat...")
            search_box = self.page.locator('div#side div[contenteditable="true"], div[data-tab="3"]').first
            if search_box.is_visible(timeout=2000):
                search_box.click(timeout=1000)
                time.sleep(0.2)
                self.page.keyboard.press("Control+A")
                self.page.keyboard.press("Backspace")
                self.page.keyboard.insert_text(chat_name)
                time.sleep(1.2)
                self.page.keyboard.press("Enter")
                time.sleep(1.0)

            self.chat_opened = True
            self.update_status(f"Chat monitored: '{chat_name}'")
            self._snapshot_existing_messages()

        except Exception as e:
            self.update_status(f"Notice locating chat '{chat_name}': {e}")
            self.chat_opened = True
            self._snapshot_existing_messages()

    def _snapshot_existing_messages(self):
        """
        Records existing messages strictly ONCE on startup.
        Ensures past conversation history is never re-triggered as 'new'.
        """
        if self.initial_snapshot_done:
            return

        try:
            messages = self.page.evaluate(JS_EXTRACT_INCOMING_MESSAGES) or []
            for msg in messages:
                key = msg.get("key")
                if key:
                    self.seen_message_ids.add(key)

            self.initial_snapshot_done = True
            print(f"[WhatsApp] Recorded {len(self.seen_message_ids)} historical messages in initial snapshot.")
            self.update_status(f"Monitoring incoming messages from '{config.TARGET_CHAT}' ({len(self.seen_message_ids)} historical)")
        except Exception as e:
            print(f"[WhatsApp] Snapshot notice: {e}")
            self.initial_snapshot_done = True

    def _check_for_new_messages(self):
        """
        Polls for new incoming messages from Keerthana.
        Uses in-browser JavaScript extraction for ultra-fast, zero-delay response.
        """
        # 1. If chat is not open, check if sidebar has an unread badge or click to focus
        if not self._is_target_chat_open():
            try:
                unread_info = self.page.evaluate(JS_CHECK_AND_CLICK_SIDEBAR_UNREAD)
                if unread_info and unread_info.get("clicked"):
                    time.sleep(1.0)
                else:
                    self.page.evaluate(JS_CLICK_KEERTHANA_SIDEBAR)
                    time.sleep(0.8)
            except Exception:
                pass

            if not self._is_target_chat_open():
                return

        # 2. If chat is open and initial snapshot was never taken, take it now
        if not self.initial_snapshot_done:
            self._snapshot_existing_messages()
            return

        # 3. Extract all incoming messages currently in the conversation pane
        incoming = self.page.evaluate(JS_EXTRACT_INCOMING_MESSAGES) or []

        for msg in incoming:
            key = msg.get("key")
            text = (msg.get("text") or "").strip()

            if not key or not text:
                continue

            # Skip if already processed
            if key in self.seen_message_ids:
                continue

            # Mark as processed immediately
            self.seen_message_ids.add(key)

            # Announce incoming message
            print(f"\n[WhatsApp Incoming] New message from {config.TARGET_CHAT}: '{text}'")
            self.update_status(f"New incoming message from Keerthana: '{text}'")
            if self.on_message:
                self.on_message(config.TARGET_CHAT, text)

    def _do_send_message(self, text: str) -> bool:
        """Internal method executed strictly on Playwright's owning worker thread."""
        if not text or not text.strip():
            return False

        try:
            self.update_status(f"Sending message: '{text}'...")

            # Ensure chat is open
            if not self._is_target_chat_open():
                self._do_open_target_chat(config.TARGET_CHAT)

            # Target footer input box
            input_box = self.page.locator(
                'footer div[contenteditable="true"], '
                'footer [contenteditable="true"], '
                'div[contenteditable="true"][data-tab="10"], '
                'div[data-testid="conversation-compose-box-input"], '
                'footer p.selectable-text'
            ).first

            input_box.wait_for(state="visible", timeout=8000)
            input_box.click(timeout=3000)
            time.sleep(0.2)

            # Insert text safely via simulated typing
            self.page.keyboard.insert_text(text)
            time.sleep(0.3)
            self.page.keyboard.press("Enter")
            time.sleep(0.5)

            self.update_status("Message sent successfully!")
            return True

        except Exception as e:
            self.update_status(f"Error sending message: {e}")
            return False

    def send_message(self, text: str) -> bool:
        """
        Thread-safe external API.
        Can be called safely from ANY thread (GUI thread, audio thread, timer).
        Enqueues the send action and returns the result from the Playwright worker thread.
        """
        if not self.running:
            return False

        future = concurrent.futures.Future()
        self._command_queue.put((self._do_send_message, (text,), future))
        try:
            return future.result(timeout=20.0)
        except Exception as e:
            self.update_status(f"Send request failed: {e}")
            return False


if __name__ == "__main__":
    bot = WhatsAppBot(
        on_message=lambda sender, msg: print(f"[TEST CALLBACK] {sender}: {msg}"),
        on_status=lambda st: print(f"[TEST STATUS] {st}"),
    )
    bot.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bot.stop()
