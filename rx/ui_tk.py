"""Tk chrome for Rx. Navigation is fail-closed and never uses the system browser.

Bootstrap does not load the bundled Restore Privacy VPN extension. There is
no VPN button and no VPN relay requirement on this window.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from rx.fence import PRIVATE_VIA_TOR, UNPRIVATE_UNLESS_TOR
from rx.shell import RxShell


def _brand_icon_path(repo_root: Path) -> Optional[Path]:
    for name in ("icon-48.png", "favicon-32.png", "logo-256.png", "favicon.ico"):
        p = repo_root / "assets" / "brand" / name
        if p.is_file():
            return p
    return None


def run_gui(shell: Optional[RxShell] = None) -> None:
    """Launch the Rx window. Page loads go through the Tor session only."""
    import tkinter as tk
    from tkinter import ttk

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

    header = ttk.Frame(main, style="Rx.TFrame")
    header.pack(fill=tk.X, padx=8, pady=(8, 4))
    ttk.Label(
        header,
        text="Rx Privacy Browser",
        style="Rx.TLabel",
        font=("Segoe UI", 12, "bold"),
    ).pack(side=tk.LEFT)
    status_lbl = ttk.Label(header, text=UNPRIVATE_UNLESS_TOR, style="Rx.TLabel")
    status_lbl.pack(side=tk.RIGHT)

    tab_bar = ttk.Frame(main, style="Rx.TFrame")
    tab_bar.pack(fill=tk.X, padx=8, pady=2)

    nav = ttk.Frame(main, style="Rx.TFrame")
    nav.pack(fill=tk.X, padx=8, pady=4)
    url_var = tk.StringVar()
    url_entry = ttk.Entry(nav, textvariable=url_var, font=("Segoe UI", 11))
    url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

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

    ext_bar = ttk.Frame(main, style="Rx.TFrame")
    ext_bar.pack(fill=tk.X, padx=8, pady=(0, 8))
    ttk.Label(
        ext_bar,
        text="Tor circuits only · VPN relay off · telemetry off",
        style="Rx.TLabel",
    ).pack(side=tk.LEFT)

    def paint_status() -> None:
        status_lbl.configure(text=shell.session.status_line())

    def write_body(body: str) -> None:
        content.configure(state=tk.NORMAL)
        content.delete("1.0", tk.END)
        content.insert(tk.END, body)
        content.configure(state=tk.DISABLED)

    def render_content_for_active() -> None:
        tab = shell.tabs.active_tab
        paint_status()
        if not tab:
            return
        url_var.set(tab.url)
        root.title(shell.window_title)
        last = shell.state.last_nav
        if last is not None and last.blocked:
            if last.private and last.status == PRIVATE_VIA_TOR and shell.session.private():
                write_body(
                    f"{PRIVATE_VIA_TOR}\n\nNot fetched: {last.url or tab.url}\n"
                    f"{last.reason}\n"
                )
            else:
                write_body(
                    f"{UNPRIVATE_UNLESS_TOR}\n\nNot fetched: {last.url or tab.url}\n"
                    "No VPN relay.\n"
                )
            return
        if last is not None and last.fetch and last.url == tab.url:
            write_body(
                f"{last.status}\n{last.url}\n{last.title}\n\n{last.text}\n"
            )
            return
        write_body(_newtab_text(shell))

    def refresh_tabs() -> None:
        for w in tab_bar.winfo_children():
            w.destroy()
        for t in shell.tabs.tabs:
            label = (t.title or "Tab")[:28]
            if t.id == shell.tabs.active_id:
                label = f"[{label}]"
            ttk.Button(
                tab_bar,
                text=label,
                style="RxTab.TButton",
                command=lambda tid=t.id: on_switch(tid),
            ).pack(side=tk.LEFT, padx=2)
        ttk.Button(tab_bar, text="+", width=3, command=on_new_tab).pack(side=tk.LEFT, padx=4)
        ttk.Button(tab_bar, text="×", width=3, command=on_close_active).pack(side=tk.LEFT)
        render_content_for_active()

    def on_switch(tid: int) -> None:
        shell.switch_tab(tid)
        shell.state.last_nav = None
        refresh_tabs()

    def on_new_tab() -> None:
        shell.open_tab()
        shell.state.last_nav = None
        refresh_tabs()

    def on_close_active() -> None:
        tid = shell.tabs.active_id
        if tid is not None:
            shell.close_tab(tid)
        shell.state.last_nav = None
        refresh_tabs()

    def on_go(_event=None) -> None:
        shell.navigate(url_var.get())
        refresh_tabs()

    def on_back() -> None:
        shell.go_back()
        refresh_tabs()

    def on_forward() -> None:
        shell.go_forward()
        refresh_tabs()

    def on_reload() -> None:
        shell.reload()
        refresh_tabs()

    ttk.Button(nav, text="Back", command=on_back).pack(side=tk.LEFT, padx=2)
    ttk.Button(nav, text="Forward", command=on_forward).pack(side=tk.LEFT, padx=2)
    ttk.Button(nav, text="Reload", command=on_reload).pack(side=tk.LEFT, padx=2)
    ttk.Button(nav, text="Go", command=on_go).pack(side=tk.LEFT, padx=2)
    url_entry.bind("<Return>", on_go)

    refresh_tabs()
    root.lift()
    root.attributes("-topmost", True)
    root.after(200, lambda: root.attributes("-topmost", False))
    root.mainloop()


def _newtab_text(shell: RxShell) -> str:
    return (
        f"{shell.window_title}\n"
        f"{'=' * 48}\n\n"
        f"{shell.product_banner}\n\n"
        "Private New Tab\n"
        "---------------\n"
        "Start page is private (about:newtab). No third-party home portal.\n"
        f"Tracker blocking: {shell.privacy.tracker_blocking}\n"
        f"Telemetry: {shell.privacy.telemetry_enabled}\n"
        "Relay: tor\n"
        "VPN relay: off\n"
        f"Status: {shell.session.status_line()}\n\n"
        "Clearnet and .onion are fetched only through Tor.\n"
        "If Tor is down the status line is unprivate unless tor and nothing is fetched.\n"
    )


def try_run_gui_brief(timeout_s: float = 2.0) -> str:
    """Open the window briefly. Headless failure is reported, not raised."""
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
            lbl = tk.Label(root, text=shell.session.status_line(), wraplength=360)
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
