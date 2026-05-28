import argparse
import json
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .classification import (
    Classification,
    LABEL_IMPERDIBLE, LABEL_VALE, LABEL_RESUMEN,
    EMOJI, THRESHOLD_IMPERDIBLE, THRESHOLD_VALE,
)
from .models import Match, Stage, TimeWindow, UserProfile
from . import classify_matches, load_all_matches

_STAGE_ORDER = [Stage.GROUP, Stage.R32, Stage.R16, Stage.QF, Stage.SF, Stage.THIRD, Stage.FINAL]

_STAGE_FILTER_MAP: dict[str, Stage] = {
    "group": Stage.GROUP,
    "r32": Stage.R32,
    "r16": Stage.R16,
    "qf": Stage.QF,
    "sf": Stage.SF,
    "third": Stage.THIRD,
    "final": Stage.FINAL,
}


# ── Profile loading ────────────────────────────────────────────────────────────

def _load_profile(path: str) -> UserProfile:
    with open(path) as f:
        data = json.load(f)

    windows = []
    for w in data.get("time_windows", []):
        tz = ZoneInfo(w["timezone"])
        windows.append(TimeWindow(
            start_hour=w["start_hour"],
            end_hour=w["end_hour"],
            timezone=tz,
            weekday=w.get("weekday"),
            date=None,
        ))

    # Backward compat: migrate old favorite_teams list
    affinities = data.get("team_affinities")
    if not affinities and data.get("favorite_teams"):
        affinities = {t.upper(): 1.0 for t in data["favorite_teams"]}
    return UserProfile(
        name=data.get("name", "Fan"),
        team_affinities={t.upper(): float(v) for t, v in (affinities or {}).items()},
        favorite_players=data.get("favorite_players", []),
        time_windows=windows,
        language=data.get("language", "es"),
        region=data.get("region", "MX"),
    )


def _interactive_profile() -> UserProfile:
    print("\n=== Configurando tu perfil de fanático ===\n")

    name = input("Tu nombre: ").strip() or "Fan"

    teams_raw = input("Equipos (S-tier favorito, coma separado, ej: ARG,MEX): ").strip()
    teams = [t.strip().upper() for t in teams_raw.split(",") if t.strip()] if teams_raw else []

    players_raw = input("Jugadores favoritos (nombres, coma separados, ej: Messi,Lozano): ").strip()
    players = [p.strip() for p in players_raw.split(",") if p.strip()] if players_raw else []

    tz_name = input("Tu zona horaria (ej: America/Mexico_City, America/New_York): ").strip()
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        print(f"Zona horaria '{tz_name}' no reconocida, usando America/Mexico_City")
        tz = ZoneInfo("America/Mexico_City")

    windows = []
    print("\nAgrega ventanas de disponibilidad (Enter sin valor para terminar):")
    while True:
        weekday_raw = input("  Día de semana disponible (0=Lun..6=Dom) o Enter para todos: ").strip()
        weekday = int(weekday_raw) if weekday_raw.isdigit() else None

        start_raw = input("  Hora inicio (0-23): ").strip()
        end_raw   = input("  Hora fin   (0-23): ").strip()
        if not start_raw or not end_raw:
            break

        try:
            windows.append(TimeWindow(
                start_hour=int(start_raw),
                end_hour=int(end_raw),
                timezone=tz,
                weekday=weekday,
            ))
        except ValueError:
            print("  Hora inválida, omitida.")

        another = input("  ¿Agregar otra ventana? (s/N): ").strip().lower()
        if another != "s":
            break

    return UserProfile(
        name=name,
        team_affinities={t: 1.0 for t in teams},
        favorite_players=players,
        time_windows=windows,
    )


# ── Output formatting ──────────────────────────────────────────────────────────

def _fmt_match_header(match: Match, profile: UserProfile) -> str:
    home = match.home if match.home != "TBD" else "Por definir"
    away = match.away if match.away != "TBD" else "Por definir"

    tz = None
    if profile.time_windows:
        tz = profile.time_windows[0].timezone
    else:
        tz = ZoneInfo("UTC")

    local_dt = match.kickoff_utc.astimezone(tz)
    date_str  = local_dt.strftime("%d %b %Y %H:%M")
    tz_abbr   = local_dt.strftime("%Z")
    stage_map = {
        Stage.GROUP: "Fase Grupos", Stage.R32: "16vos",
        Stage.R16: "Octavos",       Stage.QF: "Cuartos",
        Stage.SF: "Semifinal",      Stage.THIRD: "3er Lugar",
        Stage.FINAL: "FINAL",
    }
    stage_str = stage_map.get(match.stage, match.stage.value)
    return f"{home} vs {away}  |  {stage_str}  |  {date_str} {tz_abbr}"


_SCORER_LABELS: dict[str, str] = {
    "Favorite Team":        "Equipo favorito",
    "Match Stage":          "Fase del torneo",
    "Competitive Tension":  "Tensión competitiva",
    "Favorite Player":      "Jugador favorito",
    "Chaos Potential":      "Potencial de caos",
    "Upset Potential":      "Sorpresa",
    "Narrative":            "Narrativa",
    "Same Group":           "Mismo grupo",
    "Form":                 "Forma reciente",
    "Star Power":           "Estrellas",
}


def _fmt_score_bar(score: float, width: int = 20) -> str:
    filled = round(score / 100 * width)
    bar    = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {score:.1f}/100"


def _fmt_scorer_bar(pts: float, max_pts: float, width: int = 10) -> str:
    filled = round((pts / max_pts) * width) if max_pts > 0 else 0
    return "█" * filled + "░" * (width - filled)


def _print_classification(
    c: Classification,
    index: int,
    profile: UserProfile,
) -> None:
    m = c.result.match
    print(f"\n  [{index}] {_fmt_match_header(m, profile)}")
    print(f"      {m.venue}")
    print(f"      Score: {_fmt_score_bar(c.result.total_score)}")
    print()

    # Per-scorer breakdown — always shown
    from . import build_default_engine
    engine = build_default_engine()
    weights = {s.name: s.weight * 100 for s in engine.scorers}

    # Sort: highest contribution first, then by max weight
    rows = sorted(
        c.result.breakdown.items(),
        key=lambda kv: (kv[1], weights.get(kv[0], 0)),
        reverse=True,
    )

    col_label = 16
    col_bar   = 10
    col_pts   = 9   # "XX.X/XX.X"
    col_raw   = 6   # "(XX%)"

    d0 = "─" * col_label
    d1 = "─" * col_bar
    d2 = "─" * col_pts
    d3 = "─" * col_raw
    header = (
        f"      {'Factor':<{col_label}}  {'':^{col_bar}}  "
        f"{'Aporte':>{col_pts}}  {'Raw':>{col_raw}}  Razón"
    )
    sep = f"      {d0}  {d1}  {d2}  {d3}  {'─'*28}"
    print(header)
    print(sep)

    for name, pts in rows:
        label   = _SCORER_LABELS.get(name, name)
        max_pts = weights.get(name, 0)
        bar     = _fmt_scorer_bar(pts, max_pts)
        aporte  = f"{pts:.1f}/{max_pts:.1f}"
        raw     = c.result.raw_by_scorer.get(name, 0.0)
        raw_str = f"({raw:.0%})"
        reason  = c.result.reason_by_scorer.get(name, "") or "—"
        # Truncate long reasons
        if len(reason) > 45:
            reason = reason[:43] + "…"
        print(
            f"      {label:<{col_label}}  [{bar}]  "
            f"{aporte:>{col_pts}}  {raw_str:>{col_raw}}  {reason}"
        )

    print(sep)
    print(f"      {'TOTAL':<{col_label}}  {'':^{col_bar+2}}  "
          f"{c.result.total_score:>5.1f}/100")


def _print_group(label: str, emoji: str, items: list[Classification], profile: UserProfile) -> None:
    if not items:
        return
    print(f"\n{'='*60}")
    print(f"  {emoji} {label.upper()} ({len(items)} partidos)")
    print(f"{'='*60}")
    for i, c in enumerate(items, 1):
        _print_classification(c, i, profile)


# ── Simulation bracket printer ─────────────────────────────────────────────────

def _print_simulation_bracket(sim) -> None:
    from .simulation import SimulationResult
    from .models import Stage

    W = 60
    print(f"\n{'='*W}")
    print(f"  RESULTADOS DE LA SIMULACIÓN — MUNDIAL 2026")
    print(f"{'='*W}")

    # Group standings
    print("\n  FASE DE GRUPOS\n")
    for grp in sorted(sim.standings):
        table = sim.standings[grp]
        print(f"  Grupo {grp}:")
        for i, row in enumerate(table):
            medal = "✓" if i < 2 else ("·" if i == 2 else " ")
            adv   = " →" if i < 2 else ("  *" if i == 2 else "   ")
            print(f"    {medal} {row['team']:<4} {row['pts']}pts  GD{row['gd']:+d}{adv}")
    print(f"\n  (✓ = clasificado, * = candidato a mejor tercero)\n")

    # Knockout rounds
    ko_stages = [
        ("RONDA DE 32",   range(73, 89)),
        ("OCTAVOS",       range(89, 97)),
        ("CUARTOS",       range(97, 101)),
        ("SEMIFINALES",   range(101, 103)),
        ("TERCER LUGAR",  [103]),
        ("GRAN FINAL",    [104]),
    ]

    ko_map = {m.match_id: m for m in sim.matches if m.stage != Stage.GROUP}

    for label, match_nums in ko_stages:
        print(f"  {label}")
        print(f"  {'─'*50}")
        for mn in match_nums:
            mid = f"M{mn:03d}"
            m   = ko_map.get(mid)
            if not m:
                continue
            winner = sim.match_winners.get(mn, "?")
            loser  = sim.match_losers.get(mn, "?")
            if mn == 103:
                # 3rd place: winner gets bronze
                print(f"    M{mn}: {m.home} vs {m.away}  →  🥉 {winner}")
            elif mn == 104:
                print(f"    M{mn}: {m.home} vs {m.away}  →  🥇 {winner}  /  🥈 {loser}")
            else:
                print(f"    M{mn}: {m.home} vs {m.away}  →  {winner}")
        print()


# ── Main entry point ───────────────────────────────────────────────────────────

def run_cli() -> None:
    parser = argparse.ArgumentParser(
        prog="wc-classify",
        description="Clasificador de partidos del Mundial 2026 según tu perfil",
    )
    parser.add_argument("--profile", metavar="FILE",
                        help="JSON con tu perfil de fanático")
    parser.add_argument("--interactive", action="store_true",
                        help="Configurar perfil interactivamente")
    parser.add_argument("--stage", choices=list(_STAGE_FILTER_MAP.keys()),
                        help="Filtrar por etapa del torneo")
    parser.add_argument("--top", type=int, default=0,
                        help="Mostrar solo los N mejores por categoría")
    parser.add_argument("--json", dest="output_json", action="store_true",
                        help="Salida en formato JSON")
    parser.add_argument("--simulate", action="store_true",
                        help="Simular resultados para completar el fixture hasta la Final")
    parser.add_argument("--seed", type=int, default=None,
                        help="Semilla aleatoria para la simulación (reproducible)")

    args = parser.parse_args()

    # Build profile
    if args.profile:
        try:
            profile = _load_profile(args.profile)
        except FileNotFoundError:
            print(f"Error: archivo '{args.profile}' no encontrado.", file=sys.stderr)
            sys.exit(1)
        except (KeyError, ValueError) as e:
            print(f"Error al leer perfil: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.interactive:
        profile = _interactive_profile()
    else:
        # Demo profile
        profile = UserProfile(
            name="Fan Demo",
            team_affinities={"ARG": 1.0, "MEX": 1.0},
            favorite_players=["Messi", "Lozano", "De Paul"],
            time_windows=[
                TimeWindow(start_hour=14, end_hour=23, weekday=5,
                           timezone=ZoneInfo("America/Mexico_City")),
                TimeWindow(start_hour=11, end_hour=23, weekday=6,
                           timezone=ZoneInfo("America/Mexico_City")),
            ],
        )
        print(f"\nUsando perfil demo: equipos=[ARG, MEX], "
              f"jugadores=[Messi, Lozano, De Paul], "
              f"disponible sáb 14-23h / dom 11-23h MX")
        print("(usa --profile archivo.json o --interactive para tu perfil real)\n")

    # Load matches — split into confirmed (no TBD) and knockout (TBD)
    all_matches = load_all_matches()
    confirmed   = [m for m in all_matches if m.home != "TBD" and m.away != "TBD"]

    # Stage filter applies to confirmed section; probable section always shows full knockout
    confirmed_filtered = confirmed
    if args.stage:
        stage_filter       = _STAGE_FILTER_MAP[args.stage]
        confirmed_filtered = [m for m in confirmed if m.stage == stage_filter]

    # JSON mode — unified output (simulate if requested, then dump everything)
    if args.output_json:
        sim_result = None
        if args.simulate:
            from .simulation import simulate_bracket
            sim_result = simulate_bracket(all_matches, seed=args.seed)

        def _to_dict(c: Classification, is_probable: bool = False) -> dict:
            m = c.result.match
            return {
                "match_id":   m.match_id,
                "home":       m.home,
                "away":       m.away,
                "stage":      m.stage.value,
                "kickoff_utc": m.kickoff_utc.isoformat(),
                "venue":      m.venue,
                "score":      round(c.result.total_score, 2),
                "label":      c.label,
                "emoji":      c.emoji,
                "reasons":    c.result.reasons,
                "probable":   is_probable,
            }

        output = [_to_dict(c) for c in classify_matches(confirmed_filtered, profile)]
        if sim_result is not None:
            sim_probable = [m for m in sim_result.matches if m not in set(confirmed)]
            output += [_to_dict(c, is_probable=True) for c in classify_matches(sim_probable, profile)]
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    # ── Text output ────────────────────────────────────────────────────────────

    def _classify_and_print(
        matches: list[Match],
        header: str,
        subtitle: str,
        top: int,
    ) -> None:
        if not matches:
            return
        classifications = classify_matches(matches, profile)
        groups: dict[str, list[Classification]] = {
            LABEL_IMPERDIBLE: [], LABEL_VALE: [], LABEL_RESUMEN: [],
        }
        for c in classifications:
            groups[c.label].append(c)
        if top:
            for key in groups:
                groups[key] = groups[key][:top]

        print(f"\n{'='*60}")
        print(f"  {header}")
        print(f"  {subtitle}")
        print(f"{'='*60}")
        _print_group(LABEL_IMPERDIBLE, EMOJI[LABEL_IMPERDIBLE], groups[LABEL_IMPERDIBLE], profile)
        _print_group(LABEL_VALE,       EMOJI[LABEL_VALE],       groups[LABEL_VALE],       profile)
        _print_group(LABEL_RESUMEN,    EMOJI[LABEL_RESUMEN],    groups[LABEL_RESUMEN],    profile)
        print(f"\n{'='*60}")

    # ── Section 1: confirmed matches ───────────────────────────────────────────
    _classify_and_print(
        confirmed_filtered,
        header   = f"MUNDIAL 2026 — {profile.name}",
        subtitle = f"{len(confirmed_filtered)} partidos confirmados",
        top      = args.top,
    )

    # ── Section 2 + 3: simulation ──────────────────────────────────────────────
    if args.simulate:
        from .simulation import simulate_bracket
        seed_str   = f" (semilla={args.seed})" if args.seed is not None else ""
        sim_result = simulate_bracket(all_matches, seed=args.seed)
        print(f"\n  [Simulación{seed_str}] Fixture completado hasta la Final.\n")

        _print_simulation_bracket(sim_result)

        probable = [m for m in sim_result.matches if m not in set(confirmed)]
        if args.stage:
            stage_filter = _STAGE_FILTER_MAP[args.stage]
            probable = [m for m in probable if m.stage == stage_filter]

        _classify_and_print(
            probable,
            header   = "PARTIDOS PROBABLES (SIMULADOS)",
            subtitle = f"{len(probable)} partidos según simulación",
            top      = args.top,
        )

    print()
