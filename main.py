import sys

if "--ui" in sys.argv:
    sys.argv.remove("--ui")
    from classifier.cli import _load_profile, _interactive_profile
    from classifier.models import UserProfile, TimeWindow
    from classifier.tui import WCApp
    from zoneinfo import ZoneInfo

    # Minimal arg parse for UI mode
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--seed", type=int, default=None)
    args, _ = parser.parse_known_args()

    if args.profile:
        profile = _load_profile(args.profile)
    elif args.interactive:
        profile = _interactive_profile()
    else:
        profile = UserProfile(
            name="Fan Demo",
            favorite_teams=["ARG", "MEX"],
            favorite_players=["Messi", "Lozano", "De Paul"],
            time_windows=[
                TimeWindow(start_hour=14, end_hour=23, weekday=5,
                           timezone=ZoneInfo("America/Mexico_City")),
                TimeWindow(start_hour=11, end_hour=23, weekday=6,
                           timezone=ZoneInfo("America/Mexico_City")),
            ],
        )

    WCApp(profile=profile, seed=args.seed, auto_simulate=args.simulate).run()
else:
    from classifier.cli import run_cli
    run_cli()
