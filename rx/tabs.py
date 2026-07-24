"""Multi-tab session state for the Rx browser shell (pure, no GUI I/O)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
import itertools


@dataclass
class Tab:
    """A single browser tab."""

    id: int
    title: str
    url: str
    history: List[str] = field(default_factory=list)

    def navigate(self, url: str) -> None:
        url = (url or "").strip()
        if not url:
            raise ValueError("url required")
        if self.url:
            self.history.append(self.url)
        self.url = url
        if not self.title or self.title in ("New Tab", "about:blank"):
            self.title = _title_from_url(url)


def _title_from_url(url: str) -> str:
    u = url.strip()
    if u.startswith("about:"):
        return u
    # Strip scheme for a short tab label
    for prefix in ("https://", "http://"):
        if u.lower().startswith(prefix):
            u = u[len(prefix) :]
            break
    return (u.split("/")[0] or "New Tab")[:64]


class TabManager:
    """Open, switch, and close tabs; track the active tab."""

    def __init__(self, start_url: str = "about:newtab") -> None:
        self._id_seq = itertools.count(1)
        self._tabs: List[Tab] = []
        self._active_id: Optional[int] = None
        self.open_tab(url=start_url, title="New Tab")

    @property
    def tabs(self) -> List[Tab]:
        return list(self._tabs)

    @property
    def active_id(self) -> Optional[int]:
        return self._active_id

    @property
    def active_tab(self) -> Optional[Tab]:
        if self._active_id is None:
            return None
        for t in self._tabs:
            if t.id == self._active_id:
                return t
        return None

    def open_tab(self, url: str = "about:newtab", title: str = "New Tab") -> Tab:
        tid = next(self._id_seq)
        tab = Tab(id=tid, title=title, url=url or "about:newtab")
        self._tabs.append(tab)
        self._active_id = tid
        return tab

    def switch_tab(self, tab_id: int) -> Tab:
        for t in self._tabs:
            if t.id == tab_id:
                self._active_id = tab_id
                return t
        raise KeyError(f"no tab with id {tab_id}")

    def close_tab(self, tab_id: int) -> Optional[Tab]:
        idx = None
        for i, t in enumerate(self._tabs):
            if t.id == tab_id:
                idx = i
                break
        if idx is None:
            raise KeyError(f"no tab with id {tab_id}")
        closed = self._tabs.pop(idx)
        if not self._tabs:
            # Always keep at least one tab (browser usability)
            self._active_id = None
            return self.open_tab()
        if self._active_id == tab_id:
            # Prefer neighbor to the right, else left
            new_idx = min(idx, len(self._tabs) - 1)
            self._active_id = self._tabs[new_idx].id
        return closed

    def navigate_active(self, url: str) -> Tab:
        tab = self.active_tab
        if tab is None:
            tab = self.open_tab(url=url)
        else:
            tab.navigate(url)
        return tab

    def tab_count(self) -> int:
        return len(self._tabs)
