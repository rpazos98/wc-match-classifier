"""
classifier/tui.py — Textual TUI for Tu tiempo, tu Mundial 2026.

Launch:  python main.py --ui
         python main.py --ui --profile miperfil.json
         python main.py --ui --seed 42
"""
from __future__ import annotations

import random
from zoneinfo import ZoneInfo

from textual import on, work
from textual.app import App, ComposeResult, ScreenResultCallbackType
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Checkbox, Footer, Header, Input,
    Label, ListItem, ListView,
    Static, TabbedContent, TabPane,
)

from .classification import (
    Classification, EMOJI,
    LABEL_IMPERDIBLE, LABEL_VALE, LABEL_RESUMEN,
)
from .models import Stage, UserProfile
from . import classify_matches, load_all_matches

# ── Constants ──────────────────────────────────────────────────────────────────

_STAGE_SHORT: dict[Stage, str] = {
    Stage.GROUP: "Grupos   ",
    Stage.R32:   "R32      ",
    Stage.R16:   "Octavos  ",
    Stage.QF:    "Cuartos  ",
    Stage.SF:    "Semifinal",
    Stage.THIRD: "3er Lugar",
    Stage.FINAL: "FINAL    ",
}

_SCORER_LABELS: dict[str, str] = {
    "Favorite Team":     "Equipo fav.",
    "Time Availability": "Disponibil.",
    "Match Stage":       "Fase",
    "Form":              "Forma",
    "Favorite Player":   "Jugador fav.",
    "Dark Horse":        "Sorpresa",
    "Team Strength":     "Calidad",
    "Rivalry":           "Rivalidad",
    "Confederation":     "Confederac.",
}

_DAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


# ── CSS ────────────────────────────────────────────────────────────────────────

APP_CSS = """
Screen {
    layout: vertical;
}

#body {
    layout: horizontal;
    height: 1fr;
    width: 100%;
}

#sidebar {
    width: 22;
    height: 100%;
    border-right: solid $primary-darken-3;
    padding: 1 1;
    overflow-y: auto;
    background: $surface-darken-1;
}

#main {
    width: 1fr;
    height: 100%;
}

#detail-container {
    width: 44;
    height: 100%;
    border-left: solid $primary-darken-3;
    padding: 0 1;
    overflow-y: auto;
    background: $surface-darken-1;
}

TabbedContent {
    height: 1fr;
}

TabbedContent > ContentSwitcher {
    height: 1fr;
}

TabPane {
    height: 1fr;
    padding: 0;
}

ListView {
    height: 1fr;
    overflow-y: auto;
}

MatchItem {
    height: 1;
    padding: 0 1;
}

SectionHeader {
    height: 1;
    padding: 0 1;
    background: $primary-darken-3;
    color: $text;
}

.mi-emoji { width: 3; }
.mi-score { width: 6; color: $text-muted; }
.mi-teams { width: 22; }
.mi-stage { width: 10; color: $text-muted; }
.mi-date  { width: 11; color: $text-muted; }

.imperdible { color: red; }
.vale       { color: yellow; }
.resumen    { color: $text-muted; }

#detail-placeholder {
    padding: 4 2;
    color: $text-muted;
}
"""


# ── List widgets ───────────────────────────────────────────────────────────────

class SectionHeader(ListItem):
    """Non-selectable group header inside a ListView."""
    can_focus = False

    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(Label(text), classes="section-header", **kwargs)
        self.disabled = True


class MatchItem(ListItem):
    """One match row."""

    def __init__(self, c: Classification, profile: UserProfile, **kwargs) -> None:
        super().__init__(**kwargs)
        self.classification = c
        self._profile = profile

    def compose(self) -> ComposeResult:
        m     = self.classification.result.match
        score = self.classification.result.total_score
        emoji = self.classification.emoji
        tz    = (self._profile.time_windows[0].timezone
                 if self._profile.time_windows else ZoneInfo("UTC"))
        local    = m.kickoff_utc.astimezone(tz)
        date_str = local.strftime("%d/%m %H:%M")
        stage    = _STAGE_SHORT.get(m.stage, m.stage.value)
        lbl_cls  = {
            LABEL_IMPERDIBLE: "imperdible",
            LABEL_VALE:       "vale",
            LABEL_RESUMEN:    "resumen",
        }[self.classification.label]

        yield Horizontal(
            Label(emoji,                     classes=f"mi-emoji {lbl_cls}"),
            Label(f"{score:5.1f}",           classes="mi-score"),
            Label(f"{m.home} vs {m.away}",  classes="mi-teams"),
            Label(stage,                     classes="mi-stage"),
            Label(date_str,                  classes="mi-date"),
        )


# ── Sidebar ────────────────────────────────────────────────────────────────────

class ProfilePanel(Static):
    def __init__(self, profile: UserProfile, **kwargs) -> None:
        super().__init__(**kwargs)
        self._profile = profile

    def update_profile(self, profile: UserProfile) -> None:
        self._profile = profile
        self.refresh()

    def render(self) -> str:
        p = self._profile
        lines = [
            f"[bold]👤 {p.name}[/bold]",
            "",
            "[dim]Equipos favoritos[/dim]",
        ]
        for t in p.favorite_teams:
            lines.append(f"  [green bold]{t}[/green bold]")

        lines += ["", "[dim]Jugadores[/dim]"]
        for pl in p.favorite_players[:6]:
            lines.append(f"  {pl}")
        if len(p.favorite_players) > 6:
            lines.append(f"  [dim]…+{len(p.favorite_players)-6} más[/dim]")

        lines += ["", "[dim]Disponibilidad[/dim]"]
        for w in p.time_windows:
            day = _DAYS[w.weekday] if w.weekday is not None else "Todos"
            tz  = str(w.timezone).split("/")[-1].replace("_", " ")
            lines.append(f"  {day} {w.start_hour:02d}–{w.end_hour:02d}h")
            lines.append(f"  [dim]{tz}[/dim]")

        return "\n".join(lines)


# ── Detail panel ───────────────────────────────────────────────────────────────

class MatchDetail(Static):
    def render_match(self, c: Classification, profile: UserProfile) -> None:
        m     = c.result.match
        score = c.result.total_score
        emoji = c.emoji
        tz    = (profile.time_windows[0].timezone
                 if profile.time_windows else ZoneInfo("UTC"))
        local    = m.kickoff_utc.astimezone(tz)
        date_str = local.strftime("%d %b %Y %H:%M %Z")
        stage    = _STAGE_SHORT.get(m.stage, m.stage.value).strip()

        filled = round(score / 100 * 20)
        bar    = "█" * filled + "░" * (20 - filled)

        lines = [
            f"[bold]{m.home}[/bold] vs [bold]{m.away}[/bold]",
            f"[dim]{stage}[/dim]",
            f"[dim]{date_str}[/dim]",
            f"[dim]{m.venue[:38]}[/dim]",
            "",
            f"{emoji}  [{bar}]",
            f"   [bold]{score:.1f}[/bold] / 100",
            "",
        ]

        from . import build_default_engine
        weights = {s.name: s.weight * 100 for s in build_default_engine().scorers}

        rows = sorted(
            c.result.breakdown.items(),
            key=lambda kv: (kv[1], weights.get(kv[0], 0)),
            reverse=True,
        )

        lines += [
            f"[dim]{'─'*40}[/dim]",
            f"[dim]{'Factor':<13} {'':^8} {'Aporte':>9}  Raw[/dim]",
            f"[dim]{'─'*40}[/dim]",
        ]

        for name, pts in rows:
            label   = _SCORER_LABELS.get(name, name)[:13]
            max_pts = weights.get(name, 0)
            raw     = c.result.raw_by_scorer.get(name, 0)
            filled  = round((pts / max_pts) * 8) if max_pts > 0 else 0
            mini    = "█" * filled + "░" * (8 - filled)
            aporte  = f"{pts:.1f}/{max_pts:.1f}"
            raw_s   = f"{raw:.0%}"

            if filled >= 7:
                bar_m = f"[green][{mini}][/green]"
            elif filled >= 4:
                bar_m = f"[yellow][{mini}][/yellow]"
            elif filled > 0:
                bar_m = f"[{mini}]"
            else:
                bar_m = f"[dim][{mini}][/dim]"

            lines.append(f"{label:<13} {bar_m} {aporte:>9}  {raw_s:>4}")

        lines += [
            f"[dim]{'─'*40}[/dim]",
            f"[bold]{'TOTAL':<13} {'':^10} {score:>6.1f}/100[/bold]",
        ]

        if c.result.reasons:
            lines += ["", f"[dim]{'─'*40}[/dim]", "[dim]Por qué:[/dim]"]
            for reason in c.result.reasons:
                # Word-wrap at 36 chars
                while len(reason) > 36:
                    lines.append(f"  · {reason[:36]}")
                    reason = "    " + reason[36:]
                lines.append(f"  · {reason}")

        self.update("\n".join(lines))


# ── Bracket view ───────────────────────────────────────────────────────────────

class BracketView(Static):
    def render_bracket(self, mc) -> None:
        from .simulation import MonteCarloResult
        is_mc = isinstance(mc, MonteCarloResult)
        sim   = mc.consensus if is_mc else mc
        n     = mc.n_sims    if is_mc else 1

        lines = [
            f"[bold]SIMULACIÓN MONTE CARLO — {n} corridas[/bold]" if is_mc
            else "[bold]RESULTADOS DE LA SIMULACIÓN[/bold]",
            "",
        ]

        # ── Champion odds ──────────────────────────────────────────────────
        if is_mc:
            lines.append("[bold]PROBABILIDAD DE CAMPEÓN[/bold]")
            top = sorted(mc.champion_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            for team, count in top:
                pct     = count / n
                bar_len = round(pct * 20)
                bar     = "█" * bar_len + "░" * (20 - bar_len)
                color   = "green" if pct >= 0.15 else ("yellow" if pct >= 0.05 else "dim")
                lines.append(f"  [{color}]{team:<4}[/{color}] [{bar}] {pct:.1%}")
            lines.append("")

        # ── Group stage ────────────────────────────────────────────────────
        lines.append("[bold]FASE DE GRUPOS (bracket de consenso)[/bold]")
        for grp in sorted(sim.standings):
            table = sim.standings[grp]
            entries = []
            for i, row in enumerate(table):
                if i < 2:
                    entries.append(f"[green]{row['team']}[/green]")
                elif i == 2:
                    entries.append(f"[yellow]{row['team']}[/yellow]")
                else:
                    entries.append(f"[dim]{row['team']}[/dim]")
            lines.append(f"  [dim]Grp {grp}:[/dim] {' '.join(entries)}")

        # ── Knockout rounds ────────────────────────────────────────────────
        ko_stages = [
            ("RONDA DE 32",  range(73, 89)),
            ("OCTAVOS",      range(89, 97)),
            ("CUARTOS",      range(97, 101)),
            ("SEMIFINALES",  range(101, 103)),
            ("TERCER LUGAR", [103]),
            ("GRAN FINAL",   [104]),
        ]
        ko_map = {m.match_id: m for m in sim.matches if m.stage != Stage.GROUP}

        def _pct(mn: int, team: str) -> str:
            if not is_mc:
                return ""
            cnt = mc.match_winner_counts.get(mn, {}).get(team, 0)
            return f" [dim]({cnt/n:.0%})[/dim]"

        for label, nums in ko_stages:
            lines += ["", f"[bold]{label}[/bold]"]
            for mn in nums:
                m = ko_map.get(f"M{mn:03d}")
                if not m:
                    continue
                w = sim.match_winners.get(mn, "?")
                l = sim.match_losers.get(mn, "?")
                if mn == 104:
                    lines.append(f"  {m.home} vs {m.away}")
                    lines.append(
                        f"  [bold yellow]🥇 {w}[/bold yellow]{_pct(mn, w)}"
                        f"  [dim]🥈 {l}[/dim]"
                    )
                elif mn == 103:
                    lines.append(
                        f"  {m.home} vs {m.away}  → [yellow]🥉 {w}[/yellow]{_pct(mn, w)}"
                    )
                else:
                    lines.append(
                        f"  [dim]M{mn}[/dim] {m.home} vs {m.away}"
                        f"  [dim]→[/dim] [green]{w}[/green]{_pct(mn, w)}"
                    )

        self.update("\n".join(lines))


# ── Main App ───────────────────────────────────────────────────────────────────

PROFILE_CSS = """
ProfileScreen {
    align: center middle;
}

#profile-dialog {
    width: 90;
    height: 42;
    border: thick $primary;
    background: $surface;
    padding: 1 2;
    overflow-y: auto;
}

#profile-dialog > Label.section-title {
    color: $primary;
    text-style: bold;
    margin-top: 1;
}

.team-row {
    height: 1;
    margin-bottom: 0;
}

.team-btn {
    min-width: 6;
    width: 6;
    height: 1;
    border: none;
    background: $surface-darken-2;
    color: $text-muted;
    margin: 0 0;
}

.team-btn.selected {
    background: $success-darken-2;
    color: $text;
    text-style: bold;
}

.player-row {
    height: 1;
}

.day-row {
    height: 1;
    margin-bottom: 0;
}

.time-input {
    width: 5;
}

#profile-actions {
    height: 3;
    align: right middle;
    margin-top: 1;
}
"""


class TeamButton(Button):
    """Toggle button for a team."""

    def __init__(self, code: str, selected: bool) -> None:
        super().__init__(code, classes="team-btn" + (" selected" if selected else ""))
        self.team_code = code
        self._selected = selected

    def toggle_selected(self) -> None:
        self._selected = not self._selected
        if self._selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")

    @property
    def is_selected(self) -> bool:
        return self._selected


class ProfileScreen(ModalScreen):
    """Full-screen profile editor."""

    CSS = PROFILE_CSS

    BINDINGS = [Binding("escape", "dismiss", "Cancelar")]

    def __init__(self, profile: "UserProfile") -> None:
        super().__init__()
        self._profile = profile

    def compose(self) -> ComposeResult:
        from db.query import load_teams, players_by_team
        all_teams   = load_teams()
        fav_teams   = {t.upper() for t in self._profile.favorite_teams}
        fav_players = {p.lower() for p in self._profile.favorite_players}

        with Vertical(id="profile-dialog"):
            yield Label("✏️  Editar Perfil", classes="section-title")

            yield Label("Nombre", classes="section-title")
            yield Input(value=self._profile.name, id="input-name", placeholder="Tu nombre")

            yield Label("Equipos favoritos  (click para seleccionar)", classes="section-title")
            by_group: dict[str, list] = {}
            for t in all_teams:
                if not t.get("is_placeholder"):
                    by_group.setdefault(t["group_letter"], []).append(t)

            for grp in sorted(by_group):
                with Horizontal(classes="team-row"):
                    yield Label(f"[dim]G{grp}[/dim] ")
                    for t in by_group[grp]:
                        yield TeamButton(t["fifa_code"], t["fifa_code"] in fav_teams)

            yield Label("Jugadores favoritos  (de tus equipos)", classes="section-title")
            with Vertical(id="player-list"):
                yield Static("[dim]Selecciona equipos arriba[/dim]")

            yield Label("Disponibilidad horaria", classes="section-title")
            tz_val = (str(self._profile.time_windows[0].timezone)
                      if self._profile.time_windows else "America/Mexico_City")
            yield Label("Zona horaria")
            yield Input(value=tz_val, id="input-tz", placeholder="Ej: America/Mexico_City")

            day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            windows   = {w.weekday: w for w in self._profile.time_windows if w.weekday is not None}
            for i, day in enumerate(day_names):
                w = windows.get(i)
                with Horizontal(classes="day-row"):
                    yield Checkbox(day, value=bool(w), id=f"day-{i}")
                    yield Label("  ")
                    yield Input(value=str(w.start_hour) if w else "14",
                                id=f"start-{i}", classes="time-input", placeholder="hh")
                    yield Label("–")
                    yield Input(value=str(w.end_hour) if w else "23",
                                id=f"end-{i}", classes="time-input", placeholder="hh")

            with Horizontal(id="profile-actions"):
                yield Button("Cancelar", id="btn-cancel", variant="default")
                yield Button("  Guardar  ", id="btn-save", variant="primary")

    def on_mount(self) -> None:
        self._refresh_players()

    def _refresh_players(self) -> None:
        from db.query import players_by_team
        players_map = players_by_team()
        fav_players = {p.lower() for p in self._profile.favorite_players}
        selected    = [b.team_code for b in self.query(TeamButton) if b.is_selected]

        container = self.query_one("#player-list", Vertical)
        for child in list(container.children):
            child.remove()

        # Store ordered player list so save() can look up by index
        self._player_roster: list[str] = []

        if not selected:
            container.mount(Static("[dim]Selecciona equipos arriba[/dim]"))
            return

        shown: set[str] = set()
        widgets = []
        for code in selected:
            for player in (players_map.get(code) or [])[:8]:
                if player in shown:
                    continue
                shown.add(player)
                self._player_roster.append(player)
                idx     = len(self._player_roster) - 1
                checked = any(fav in player.lower() for fav in fav_players)
                widgets.append(
                    Checkbox(player, value=checked, id=f"pl-{idx}", classes="player-cb")
                )
        if widgets:
            container.mount(*widgets)
        else:
            container.mount(Static("[dim]Sin datos de jugadores[/dim]"))

    @on(Button.Pressed, ".team-btn")
    def on_team_toggled(self, event: Button.Pressed) -> None:
        if isinstance(event.button, TeamButton):
            event.button.toggle_selected()
            self._refresh_players()

    @on(Button.Pressed, "#btn-cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-save")
    def on_save(self) -> None:
        from .models import UserProfile, TimeWindow

        name  = self.query_one("#input-name", Input).value.strip() or "Fan"
        teams = [b.team_code for b in self.query(TeamButton) if b.is_selected]

        roster  = getattr(self, "_player_roster", [])
        players = []
        for i, player in enumerate(roster):
            try:
                cb = self.query_one(f"#pl-{i}", Checkbox)
                if cb.value:
                    players.append(player)
            except Exception:
                pass

        tz_str = self.query_one("#input-tz", Input).value.strip()
        try:
            tz = ZoneInfo(tz_str)
        except Exception:
            tz = ZoneInfo("America/Mexico_City")

        windows = []
        for i in range(7):
            cb = self.query_one(f"#day-{i}", Checkbox)
            if cb.value:
                try:
                    start = int(self.query_one(f"#start-{i}", Input).value)
                    end   = int(self.query_one(f"#end-{i}",   Input).value)
                except ValueError:
                    start, end = 14, 23
                windows.append(TimeWindow(
                    start_hour=start, end_hour=end,
                    timezone=tz, weekday=i,
                ))

        self.dismiss(UserProfile(
            name=name,
            favorite_teams=teams,
            favorite_players=[str(p) for p in players],
            time_windows=windows,
        ))


def _build_items(
    classifications: list[Classification],
    profile: UserProfile,
) -> list[ListItem]:
    items: list[ListItem] = []
    groups = {LABEL_IMPERDIBLE: [], LABEL_VALE: [], LABEL_RESUMEN: []}
    for c in classifications:
        groups[c.label].append(c)
    for label, cs in groups.items():
        if not cs:
            continue
        items.append(SectionHeader(f"  {EMOJI[label]} {label.upper()} ({len(cs)})"))
        items.extend(MatchItem(c, profile) for c in cs)
    return items


class WCApp(App):
    TITLE    = "Tu Tiempo, Tu Mundial 2026 🏆"
    CSS      = APP_CSS
    BINDINGS = [
        Binding("q",         "quit",         "Salir"),
        Binding("p",         "edit_profile", "Perfil"),
        Binding("s",         "simulate",     "Simular"),
        Binding("r",         "reseed",       "Nueva semilla"),
        Binding("ctrl+left", "focus_sidebar", "Sidebar", show=False),
        Binding("ctrl+right","focus_detail",  "Detalle",  show=False),
    ]

    _seed: int = 42

    def __init__(
        self,
        profile: UserProfile,
        seed: int | None = None,
        auto_simulate: bool = False,
    ) -> None:
        super().__init__()
        self._profile       = profile
        self._auto_simulate = auto_simulate
        if seed is not None:
            self._seed = seed
        self._confirmed: list[Classification] = []
        self._simulated: list[Classification] = []
        self._sim_result = None

    # ── Layout ─────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield ProfilePanel(self._profile, id="sidebar")
            with Container(id="main"):
                with TabbedContent(id="tabs"):
                    with TabPane("Confirmados", id="tab-confirmed"):
                        yield ListView(id="list-confirmed")
                    with TabPane("Simulados 🎲", id="tab-simulated", disabled=True):
                        yield ListView(id="list-simulated")
                    with TabPane("Bracket 📊", id="tab-bracket", disabled=True):
                        yield ScrollableContainer(
                            BracketView(id="bracket-view"),
                            id="bracket-scroll",
                        )
            yield ScrollableContainer(
                Static("[dim]Selecciona un partido para ver el desglose[/dim]",
                       id="detail-placeholder"),
                id="detail-container",
            )
        yield Footer()

    # ── Mount ──────────────────────────────────────────────────────────────────

    async def on_mount(self) -> None:
        await self._load_confirmed()
        if self._auto_simulate:
            self.action_simulate()

    async def _load_confirmed(self) -> None:
        all_matches = load_all_matches()
        confirmed   = [m for m in all_matches if m.home != "TBD" and m.away != "TBD"]
        self._confirmed = classify_matches(confirmed, self._profile)
        lv = self.query_one("#list-confirmed", ListView)
        await lv.extend(_build_items(self._confirmed, self._profile))

    # ── Simulation ─────────────────────────────────────────────────────────────

    @work(thread=True)
    def action_simulate(self) -> None:
        from .simulation import simulate_bracket
        all_matches = load_all_matches()
        confirmed   = {m for m in all_matches if m.home != "TBD" and m.away != "TBD"}
        sim         = simulate_bracket(all_matches, seed=self._seed)
        probable    = [m for m in sim.matches if m not in confirmed]
        simulated   = classify_matches(probable, self._profile)
        self.app.call_from_thread(self._apply_simulation, sim, simulated)

    def _apply_simulation(self, sim, simulated: list[Classification]) -> None:
        self._sim_result = sim
        self._simulated  = simulated
        self._do_apply_simulation(sim, simulated)

    @work
    async def _do_apply_simulation(self, sim, simulated: list[Classification]) -> None:
        # Populate Simulados tab
        lv = self.query_one("#list-simulated", ListView)
        await lv.clear()
        await lv.extend(_build_items(simulated, self._profile))

        # Populate Bracket tab
        bv = self.query_one("#bracket-view", BracketView)
        bv.render_bracket(sim)

        # Enable tabs
        tabs = self.query_one("#tabs", TabbedContent)
        tabs.enable_tab("tab-simulated")
        tabs.enable_tab("tab-bracket")
        tabs.active = "tab-simulated"

        self.notify(f"Simulación lista — semilla {self._seed}", timeout=3)

    def action_reseed(self) -> None:
        self._seed = random.randint(0, 9999)
        self.notify(f"Nueva semilla: {self._seed} — presiona S para simular", timeout=3)

    def action_edit_profile(self) -> None:
        self.push_screen(ProfileScreen(self._profile), self._on_profile_saved)

    def _on_profile_saved(self, new_profile: "UserProfile | None") -> None:
        if new_profile is None:
            return
        self._profile    = new_profile
        self._sim_result = None
        # Refresh sidebar
        self.query_one("#sidebar", ProfilePanel).update_profile(new_profile)
        # Reload confirmed list
        self._reload_lists()

    @work
    async def _reload_lists(self) -> None:
        from .models import UserProfile
        all_matches = load_all_matches()
        confirmed   = [m for m in all_matches if m.home != "TBD" and m.away != "TBD"]
        self._confirmed = classify_matches(confirmed, self._profile)

        lv = self.query_one("#list-confirmed", ListView)
        await lv.clear()
        await lv.extend(_build_items(self._confirmed, self._profile))

        # Disable sim tabs until re-simulated
        tabs = self.query_one("#tabs", TabbedContent)
        tabs.disable_tab("tab-simulated")
        tabs.disable_tab("tab-bracket")
        tabs.active = "tab-confirmed"

        self.notify(f"Perfil actualizado: {self._profile.name}", timeout=3)

    # ── Selection ──────────────────────────────────────────────────────────────

    @on(ListView.Selected)
    def on_match_selected(self, event: ListView.Selected) -> None:
        if not isinstance(event.item, MatchItem):
            return
        c = event.item.classification
        detail = self.query_one("#detail-container", ScrollableContainer)

        # Replace placeholder with MatchDetail widget if needed
        existing = detail.query("MatchDetail")
        if not existing:
            detail.query_one("#detail-placeholder").remove()
            detail.mount(MatchDetail(id="detail-widget"))

        self.query_one("#detail-widget", MatchDetail).render_match(c, self._profile)
        detail.scroll_home(animate=False)

    # ── Focus helpers ──────────────────────────────────────────────────────────

    def action_focus_sidebar(self) -> None:
        self.query_one("#sidebar").focus()

    def action_focus_detail(self) -> None:
        self.query_one("#detail-container").focus()
