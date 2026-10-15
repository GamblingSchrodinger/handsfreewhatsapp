"""
GUI Application: Modern Dark-Mode Control Center for WhatsApp Voice Assistant.
Displays real-time WhatsApp status, chat logs, live transcription, and mic controls.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
from typing import Callable, Optional


class ModernTheme:
    BG_DARK = "#0f172a"        # Deep slate background
    CARD_BG = "#1e293b"        # Card surface
    CARD_BORDER = "#334155"    # Card border
    TEXT_MAIN = "#f8fafc"      # Crisp white text
    TEXT_MUTED = "#94a3b8"     # Secondary text
    ACCENT_GREEN = "#10b981"   # Emerald status / send
    ACCENT_CYAN = "#06b6d4"    # Cyan action buttons
    ACCENT_AMBER = "#f59e0b"   # Warning / listening
    ACCENT_RED = "#ef4444"     # Cancel / error
    FONT_FAMILY = "Segoe UI"


class VoiceAssistantGUI:
    def __init__(
        self,
        on_manual_listen: Optional[Callable[[], None]] = None,
        on_send_override: Optional[Callable[[str], None]] = None,
        on_test_mic: Optional[Callable[[], None]] = None,
        on_test_tts: Optional[Callable[[], None]] = None,
    ):
        self.on_manual_listen = on_manual_listen
        self.on_send_override = on_send_override
        self.on_test_mic = on_test_mic
        self.on_test_tts = on_test_tts

        self.root = tk.Tk()
        self.root.title("WhatsApp Voice Assistant - Keerthana Chemical Engineering")
        self.root.geometry("820x720")
        self.root.minsize(700, 600)
        self.root.configure(bg=ModernTheme.BG_DARK)

        self._pending_send_timer = None
        self._countdown_remaining = 0
        self._build_ui()

    def _build_ui(self):
        # Header banner
        header = tk.Frame(self.root, bg=ModernTheme.CARD_BG, height=70)
        header.pack(fill=tk.X, side=tk.TOP, pady=(0, 15))

        title_box = tk.Frame(header, bg=ModernTheme.CARD_BG)
        title_box.pack(side=tk.LEFT, padx=20, pady=12)

        lbl_title = tk.Label(
            title_box,
            text="WhatsApp Voice Assistant",
            font=(ModernTheme.FONT_FAMILY, 16, "bold"),
            fg=ModernTheme.TEXT_MAIN,
            bg=ModernTheme.CARD_BG,
        )
        lbl_title.pack(anchor="w")

        lbl_sub = tk.Label(
            title_box,
            text="Target Chat: Keerthana Chemical Engineering",
            font=(ModernTheme.FONT_FAMILY, 10),
            fg=ModernTheme.ACCENT_CYAN,
            bg=ModernTheme.CARD_BG,
        )
        lbl_sub.pack(anchor="w")

        # WhatsApp Status Pill
        self.status_pill = tk.Label(
            header,
            text="Initializing...",
            font=(ModernTheme.FONT_FAMILY, 10, "bold"),
            fg="#0f172a",
            bg=ModernTheme.ACCENT_AMBER,
            padx=12,
            pady=4,
        )
        self.status_pill.pack(side=tk.RIGHT, padx=20, pady=18)

        # Main Scrollable / Stack container
        main_frame = tk.Frame(self.root, bg=ModernTheme.BG_DARK)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Card 1: Live Status & Mic State
        self._build_status_card(main_frame)

        # Card 2: Latest Incoming Message & Live Reply
        self._build_message_card(main_frame)

        # Card 3: Activity Feed & Logs
        self._build_log_card(main_frame)

        # Bottom Action Bar
        self._build_action_bar(main_frame)

    def _build_status_card(self, parent):
        card = tk.LabelFrame(
            parent,
            text=" Live Assistant Status ",
            font=(ModernTheme.FONT_FAMILY, 11, "bold"),
            fg=ModernTheme.TEXT_MAIN,
            bg=ModernTheme.CARD_BG,
            bd=1,
            relief=tk.SOLID,
        )
        card.pack(fill=tk.X, pady=(0, 12), ipady=8, padx=2)

        row = tk.Frame(card, bg=ModernTheme.CARD_BG)
        row.pack(fill=tk.X, padx=15, pady=4)

        tk.Label(
            row,
            text="Voice Engine:",
            font=(ModernTheme.FONT_FAMILY, 10, "bold"),
            fg=ModernTheme.TEXT_MUTED,
            bg=ModernTheme.CARD_BG,
        ).pack(side=tk.LEFT)

        self.lbl_mic_status = tk.Label(
            row,
            text="Idle (Waiting for message from Keerthana)",
            font=(ModernTheme.FONT_FAMILY, 10),
            fg=ModernTheme.TEXT_MAIN,
            bg=ModernTheme.CARD_BG,
        )
        self.lbl_mic_status.pack(side=tk.LEFT, padx=10)

    def _build_message_card(self, parent):
        card = tk.LabelFrame(
            parent,
            text=" Active Conversation & Voice Reply ",
            font=(ModernTheme.FONT_FAMILY, 11, "bold"),
            fg=ModernTheme.TEXT_MAIN,
            bg=ModernTheme.CARD_BG,
            bd=1,
            relief=tk.SOLID,
        )
        card.pack(fill=tk.X, pady=(0, 12), ipady=8, padx=2)

        # Incoming message box
        tk.Label(
            card,
            text="Latest Message from Keerthana:",
            font=(ModernTheme.FONT_FAMILY, 10, "bold"),
            fg=ModernTheme.ACCENT_CYAN,
            bg=ModernTheme.CARD_BG,
        ).pack(anchor="w", padx=15, pady=(4, 2))

        self.lbl_incoming_msg = tk.Label(
            card,
            text="[No incoming messages yet]",
            font=(ModernTheme.FONT_FAMILY, 11, "italic"),
            fg=ModernTheme.TEXT_MAIN,
            bg="#111827",
            anchor="w",
            padx=12,
            pady=8,
            relief=tk.FLAT,
        )
        self.lbl_incoming_msg.pack(fill=tk.X, padx=15, pady=(0, 8))

        # Transcribed reply entry
        tk.Label(
            card,
            text="Your Transcribed Voice Reply:",
            font=(ModernTheme.FONT_FAMILY, 10, "bold"),
            fg=ModernTheme.ACCENT_GREEN,
            bg=ModernTheme.CARD_BG,
        ).pack(anchor="w", padx=15, pady=(4, 2))

        self.entry_reply = tk.Entry(
            card,
            font=(ModernTheme.FONT_FAMILY, 11),
            fg=ModernTheme.TEXT_MAIN,
            bg="#111827",
            insertbackground=ModernTheme.TEXT_MAIN,
            relief=tk.FLAT,
        )
        self.entry_reply.pack(fill=tk.X, padx=15, pady=(0, 8), ipady=5)

        # Reply control row
        btn_row = tk.Frame(card, bg=ModernTheme.CARD_BG)
        btn_row.pack(fill=tk.X, padx=15, pady=4)

        self.lbl_countdown = tk.Label(
            btn_row,
            text="",
            font=(ModernTheme.FONT_FAMILY, 10, "bold"),
            fg=ModernTheme.ACCENT_AMBER,
            bg=ModernTheme.CARD_BG,
        )
        self.lbl_countdown.pack(side=tk.LEFT)

        self.btn_cancel_send = tk.Button(
            btn_row,
            text="Cancel Send",
            font=(ModernTheme.FONT_FAMILY, 9, "bold"),
            fg="white",
            bg=ModernTheme.ACCENT_RED,
            activebackground="#dc2626",
            bd=0,
            padx=12,
            pady=4,
            command=self.cancel_pending_send,
            cursor="hand2",
        )

        self.btn_send_now = tk.Button(
            btn_row,
            text="Send Now",
            font=(ModernTheme.FONT_FAMILY, 9, "bold"),
            fg="white",
            bg=ModernTheme.ACCENT_GREEN,
            activebackground="#059669",
            bd=0,
            padx=14,
            pady=4,
            command=self._on_send_now_clicked,
            cursor="hand2",
        )
        self.btn_send_now.pack(side=tk.RIGHT, padx=(6, 0))
        self.btn_cancel_send.pack(side=tk.RIGHT)

    def _build_log_card(self, parent):
        card = tk.LabelFrame(
            parent,
            text=" System Activity Log ",
            font=(ModernTheme.FONT_FAMILY, 11, "bold"),
            fg=ModernTheme.TEXT_MAIN,
            bg=ModernTheme.CARD_BG,
            bd=1,
            relief=tk.SOLID,
        )
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 12), ipady=4, padx=2)

        self.log_text = scrolledtext.ScrolledText(
            card,
            font=("Consolas", 10),
            bg="#090d16",
            fg="#cbd5e1",
            insertbackground="#cbd5e1",
            relief=tk.FLAT,
            bd=0,
            height=8,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

    def _build_action_bar(self, parent):
        action_bar = tk.Frame(parent, bg=ModernTheme.BG_DARK)
        action_bar.pack(fill=tk.X, pady=(0, 5))

        btn_mic = tk.Button(
            action_bar,
            text="🎙️ Manual Voice Reply",
            font=(ModernTheme.FONT_FAMILY, 10, "bold"),
            fg="white",
            bg=ModernTheme.ACCENT_CYAN,
            activebackground="#0891b2",
            bd=0,
            padx=14,
            pady=8,
            command=self._trigger_manual_listen,
            cursor="hand2",
        )
        btn_mic.pack(side=tk.LEFT, padx=(0, 10))

        btn_test_mic = tk.Button(
            action_bar,
            text="Test Mic (3s)",
            font=(ModernTheme.FONT_FAMILY, 10),
            fg=ModernTheme.TEXT_MAIN,
            bg=ModernTheme.CARD_BG,
            activebackground=ModernTheme.CARD_BORDER,
            bd=1,
            relief=tk.SOLID,
            padx=12,
            pady=7,
            command=self._trigger_test_mic,
            cursor="hand2",
        )
        btn_test_mic.pack(side=tk.LEFT, padx=(0, 10))

        btn_test_tts = tk.Button(
            action_bar,
            text="Test Speakers / TTS",
            font=(ModernTheme.FONT_FAMILY, 10),
            fg=ModernTheme.TEXT_MAIN,
            bg=ModernTheme.CARD_BG,
            activebackground=ModernTheme.CARD_BORDER,
            bd=1,
            relief=tk.SOLID,
            padx=12,
            pady=7,
            command=self._trigger_test_tts,
            cursor="hand2",
        )
        btn_test_tts.pack(side=tk.LEFT)

    # UI Update methods (Thread-safe via root.after)
    def set_whatsapp_status(self, text: str, state: str = "normal"):
        color = ModernTheme.ACCENT_GREEN if state == "connected" else \
                ModernTheme.ACCENT_RED if state == "error" else \
                ModernTheme.ACCENT_AMBER
        self.root.after(0, lambda: self.status_pill.configure(text=text, bg=color))

    def set_mic_status(self, text: str):
        self.root.after(0, lambda: self.lbl_mic_status.configure(text=text))

    def set_incoming_message(self, sender: str, text: str):
        display_text = f'"{text}"'
        self.root.after(0, lambda: self.lbl_incoming_msg.configure(
            text=display_text, font=(ModernTheme.FONT_FAMILY, 11, "normal")
        ))
        self.log(f"[INCOMING from {sender}]: {text}")

    def set_transcribed_reply(self, text: str):
        def _update():
            self.entry_reply.delete(0, tk.END)
            self.entry_reply.insert(0, text)
        self.root.after(0, _update)

    def log(self, text: str):
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {text}\n"
        def _append():
            self.log_text.insert(tk.END, line)
            self.log_text.see(tk.END)
        self.root.after(0, _append)

    def start_send_countdown(self, seconds: float, callback: Callable[[str], None]):
        """Starts visual countdown before automatically sending the reply."""
        self.cancel_pending_send()
        self._countdown_remaining = int(seconds)

        def _step():
            if self._countdown_remaining > 0:
                self.lbl_countdown.configure(
                    text=f"Auto-sending in {self._countdown_remaining}s..."
                )
                self._countdown_remaining -= 1
                self._pending_send_timer = self.root.after(1000, _step)
            else:
                self.lbl_countdown.configure(text="")
                reply = self.entry_reply.get().strip()
                if reply:
                    callback(reply)

        _step()

    def cancel_pending_send(self):
        """Cancels an active auto-send countdown."""
        if self._pending_send_timer:
            self.root.after_cancel(self._pending_send_timer)
            self._pending_send_timer = None
        self.lbl_countdown.configure(text="Auto-send cancelled.")
        self.log("Auto-send was cancelled by user.")

    def _on_send_now_clicked(self):
        reply = self.entry_reply.get().strip()
        if reply and self.on_send_override:
            if self._pending_send_timer:
                self.root.after_cancel(self._pending_send_timer)
                self._pending_send_timer = None
            self.lbl_countdown.configure(text="")
            self.on_send_override(reply)

    def _trigger_manual_listen(self):
        if self.on_manual_listen:
            threading.Thread(target=self.on_manual_listen, daemon=True).start()

    def _trigger_test_mic(self):
        if self.on_test_mic:
            threading.Thread(target=self.on_test_mic, daemon=True).start()

    def _trigger_test_tts(self):
        if self.on_test_tts:
            threading.Thread(target=self.on_test_tts, daemon=True).start()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = VoiceAssistantGUI()
    app.log("GUI test launched.")
    app.run()
