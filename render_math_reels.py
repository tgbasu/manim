"""Compatibility wrapper. Prefer: python -m reelstudio [scenes] [options]."""

from reelstudio.render import main


if __name__ == "__main__":
    main()
