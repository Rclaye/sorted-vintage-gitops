#!/usr/bin/env python3
"""Read or change the image tag in a service overlay (T029 build, T030 promote).

  set-image-tag.py get <service> <env>
      print the overlay's current tag
  set-image-tag.py set <service> <env> <tag> [--first-replicas N]
      set the tag; with --first-replicas, also set replicas to N if they are 0 (first promotion)

Only the newTag line (and the replicas count, if asked) changes, so a bot pull request made with
this script touches nothing else. Standard library only: it runs on any Actions runner.
"""

import argparse
import re
import sys
from pathlib import Path

TAG = re.compile(r"^(?P<lead>[ \t]*newTag:[ \t]*)(?P<tag>\S+)[ \t]*$", re.MULTILINE)
REPLICAS = re.compile(r"^(?P<lead>[ \t]*- \{ name: (?P<name>[a-z0-9-]+), count: )(?P<count>\d+)(?P<tail> \}[ \t]*)$", re.MULTILINE)
SAFE_TAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def overlay(service: str, env: str) -> Path:
    if not SAFE_NAME.match(service) or env not in ("dev", "prod"):
        sys.exit(f"bad service or env: {service!r} {env!r}")
    path = Path("services") / service / "overlays" / env / "kustomization.yaml"
    if not path.is_file():
        sys.exit(f"no overlay at {path}")
    return path


def one(pattern: re.Pattern, text: str, what: str, path: Path) -> re.Match:
    found = list(pattern.finditer(text))
    if len(found) != 1:
        sys.exit(f"{path}: expected exactly one {what}, found {len(found)}")
    return found[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["get", "set"])
    parser.add_argument("service")
    parser.add_argument("env")
    parser.add_argument("tag", nargs="?")
    parser.add_argument("--first-replicas", type=int)
    args = parser.parse_args()

    path = overlay(args.service, args.env)
    text = path.read_text()
    tag = one(TAG, text, "newTag", path)

    if args.action == "get":
        print(tag["tag"])
        return

    if not args.tag or not SAFE_TAG.match(args.tag) or args.tag == "unset":
        sys.exit(f"bad tag: {args.tag!r}")
    text = text[: tag.start()] + tag["lead"] + args.tag + text[tag.end() :]

    # A Job (the seed job) has no replicas entry: --first-replicas has nothing to raise there.
    if args.first_replicas is not None and REPLICAS.search(text):
        rep = one(REPLICAS, text, "replicas entry", path)
        if rep["count"] == "0":
            text = text[: rep.start()] + rep["lead"] + str(args.first_replicas) + rep["tail"] + text[rep.end() :]

    path.write_text(text)
    print(f"{path}: newTag {tag['tag']} -> {args.tag}")


if __name__ == "__main__":
    main()
