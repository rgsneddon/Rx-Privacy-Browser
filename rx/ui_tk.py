"""Original Tkinter chrome for Rx: tab strip, address bar, content + extension panel."""

from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional

from rx.shell import RxShell


def _brand_icon_path(repo_root: Path) -> Optional[Path]:
    for name in ("icon-48.png", "favicon-32.png", "logo-256.png", "favicon.ico"):
        p = repo_root / "assets" / "brand" / name
        if p.is_file():
            return p
    return None


def run_gui(shell: Optional[RxShell] = None) -> None:
    """Launch the Rx window. Requires a display / Tk."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    shell = shell or RxShell()
    shell.bootstrap()
    root = tk.Tk()
    root.title(shell.window_title)
    root.geometry("1100x720")
    root.minsize(720, 480)
    root.configure(bg="#0b1c2c")

    icon = _brand_icon_path(shell.repo_root)
    if icon is not None:
        try:
            if icon.suffix.lower() == ".ico":
                root.iconbitmap(default=str(icon))
            else:
                img = tk.PhotoImage(file=str(icon))
                root.iconphoto(True, img)
                root._rx_icon = img  # prevent GC
        except Exception:
            pass

    # --- styles (Restore Privacy navy palette) ---
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("Rx.TFrame", background="#0b1c2c")
    style.configure("Rx.TLabel", background="#0b1c2c", foreground="#e8f1f8")
    style.configure("Rx.TButton", padding=4)
    style.configure("RxTab.TButton", padding=(10, 4))

    main = ttk.Frame(root, style="Rx.TFrame")
    main.pack(fill=tk.BOTH, expand=True)

    # Brand header
    header = ttk.Frame(main, style="Rx.TFrame")
    header.pack(fill=tk.X, padx=8, pady=(8, 4))
    brand_lbl = ttk.Label(
        header,
        text="Rx  |  Restore Privacy Browser",
        style="Rx.TLabel",
        font=("Segoe UI", 12, "bold"),
    )
    brand_lbl.pack(side=tk.LEFT)
    vpn_status = ttk.Label(
        header,
        text="",
        style="Rx.TLabel",
        font=("Segoe UI", 9),
    )
    vpn_status.pack(side=tk.RIGHT)

    # Tab strip
    tab_bar = ttk.Frame(main, style="Rx.TFrame")
    tab_bar.pack(fill=tk.X, padx=8, pady=2)

    # Nav bar
    nav = ttk.Frame(main, style="Rx.TFrame")
    nav.pack(fill=tk.X, padx=8, pady=4)
    url_var = tk.StringVar()
    url_entry = ttk.Entry(nav, textvariable=url_var, font=("Segoe UI", 11))
    url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

    # Content area (HTML-ish text + optional external open)
    content_frame = ttk.Frame(main, style="Rx.TFrame")
    content_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
    content = tk.Text(
        content_frame,
        wrap=tk.WORD,
        bg="#12283a",
        fg="#e8f1f8",
        insertbackground="#e8f1f8",
        font=("Segoe UI", 11),
        relief=tk.FLAT,
        padx=16,
        pady=16,
    )
    content.pack(fill=tk.BOTH, expand=True)
    content.configure(state=tk.DISABLED)

    # Extension dock
    ext_bar = ttk.Frame(main, style="Rx.TFrame")
    ext_bar.pack(fill=tk.X, padx=8, pady=(0, 8))

    tab_buttons: dict[int, ttk.Button] = {}

    def render_content_for_active() -> None:
        tab = shell.tabs.active_tab
        if not tab:
            return
        url_var.set(tab.url)
        root.title(shell.window_title)
        body = _newtab_html(shell) if tab.url.startswith("about:") else _page_stub(tab.url, shell)
        content.configure(state=tk.NORMAL)
        content.delete("1.0", tk.END)
        content.insert(tk.END, body)
        content.configure(state=tk.DISABLED)

    def refresh_tabs() -> None:
        for w in tab_bar.winfo_children():
            w.destroy()
        tab_buttons.clear()
        for t in shell.tabs.tabs:
            label = (t.title or "Tab")[:28]
            if t.id == shell.tabs.active_id:
                label = f"[{label}]"
            btn = ttk.Button(
                tab_bar,
                text=label,
                style="RxTab.TButton",
                command=lambda tid=t.id: on_switch(tid),
            )
            btn.pack(side=tk.LEFT, padx=2)
            tab_buttons[t.id] = btn
        ttk.Button(tab_bar, text="+", width=3, command=on_new_tab).pack(side=tk.LEFT, padx=4)
        ttk.Button(tab_bar, text="×", width=3, command=on_close_active).pack(side=tk.LEFT)
        render_content_for_active()

    def on_switch(tid: int) -> None:
        shell.switch_tab(tid)
        refresh_tabs()

    def on_new_tab() -> None:
        shell.open_tab()
        refresh_tabs()

    def on_close_active() -> None:
        tid = shell.tabs.active_id
        if tid is not None:
            shell.close_tab(tid)
        refresh_tabs()

    def on_go(_event=None) -> None:
        raw = url_var.get()
        shell.navigate(raw)
        active = shell.tabs.active_tab
        if active and active.url.startswith("http"):
            # Open external content in system browser surface while shell tracks tabs
            # (keeps shell original; avoids embedding a third-party browser engine fork)
            try:
                webbrowser.open(active.url)
            except Exception as exc:
                messagebox.showerror("Rx", f"Navigation failed: {exc}")
        refresh_tabs()

    def on_vpn_popup() -> None:
        vpn = shell.state.bundled_vpn
        if not vpn:
            messagebox.showinfo("Rx Extensions", "VPN extension not loaded")
            return
        popup = vpn.path / "popup.html"
        if popup.is_file():
            webbrowser.open(popup.resolve().as_uri())
        messagebox.showinfo(
            "Restore Privacy VPN",
            f"{vpn.name} v{vpn.version}\n"
            f"Path: {vpn.path}\n"
            f"Enabled: {vpn.enabled}\n\n"
            "Browser-scoped extension package is bundled and permitted.\n"
            "Load unpacked path is ready for Chromium-compatible hosts.",
        )

    def refresh_vpn_label() -> None:
        vpn = shell.state.bundled_vpn
        if vpn:
            vpn_status.configure(
                text=f"VPN ext {vpn.version} · {'ON' if vpn.enabled else 'off'}"
            )
        else:
            vpn_status.configure(text="VPN not loaded")

    ttk.Button(nav, text="Go", command=on_go).pack(side=tk.LEFT, padx=2)
    ttk.Button(nav, text="New Tab", command=on_new_tab).pack(side=tk.LEFT, padx=2)
    url_entry.bind("<Return>", on_go)

    ttk.Button(
        ext_bar,
        text="Extensions: Restore Privacy VPN 3.3.3",
        command=on_vpn_popup,
    ).pack(side=tk.LEFT)
    ttk.Label(
        ext_bar,
        text="Extensions permitted · no telemetry",
        style="Rx.TLabel",
    ).pack(side=tk.RIGHT)

    refresh_vpn_label()
    refresh_tabs()
    # Raise window
    root.lift()
    root.attributes("-topmost", True)
    root.after(200, lambda: root.attributes("-topmost", False))
    root.mainloop()


def _newtab_html(shell: RxShell) -> str:
    vpn = shell.state.bundled_vpn
    vpn_line = (
        f"Bundled: {vpn.name} v{vpn.version}\nPath: {vpn.path}"
        if vpn
        else "VPN extension not loaded"
    )
    return (
        f"{shell.window_title}\n"
        f"{'=' * 48}\n\n"
        f"{shell.product_banner}\n\n"
        "Private New Tab\n"
        "---------------\n"
        "Start page is private (about:newtab). No third-party home portal.\n"
        f"Tracker blocking: {shell.privacy.tracker_blocking}\n"
        f"Telemetry: {shell.privacy.telemetry_enabled}\n"
        f"Do Not Track: {shell.privacy.send_do_not_track}\n\n"
        f"{vpn_line}\n\n"
        "Type a URL in the address bar and press Go.\n"
        "Use + to open tabs, × to close, and the tab strip to switch.\n"
    )


def _page_stub(url: str, shell: RxShell) -> str:
    return (
        f"{shell.window_title}\n"
        f"{'=' * 48}\n\n"
        f"Navigated: {url}\n\n"
        "Tab session is tracked inside Rx. HTTP(S) pages open via the system\n"
        "web surface while privacy defaults and the VPN extension stay under\n"
        "Restore Privacy branding in this shell.\n"
    )


def try_run_gui_brief(timeout_s: float = 2.0) -> str:
    """
    Attempt to open the GUI briefly for launch verification.
    Returns a status string. Does not raise on headless failure.
    """
    shell = RxShell()
    report = shell.smoke_report()
    try:
        import tkinter as tk
    except Exception as e:
        return report + f"\ngui_unavailable: {e}"

    result = {"ok": False, "err": None}

    def _run():
        try:
            root = tk.Tk()
            root.title(shell.window_title)
            root.geometry("400x200")
            lbl = tk.Label(root, text=shell.product_banner, wraplength=360)
            lbl.pack(padx=12, pady=12)
            root.after(int(timeout_s * 1000), root.destroy)
            root.mainloop()
            result["ok"] = True
        except Exception as exc:
            result["err"] = str(exc)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout_s + 3.0)
    if result["ok"]:
        return report + "\ngui_brief_ok"
    if result["err"]:
        return report + f"\ngui_error: {result['err']}"
    return report + "\ngui_timeout_or_headless"
