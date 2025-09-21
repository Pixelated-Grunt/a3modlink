#!/usr/bin/env python

import argparse
import os
import re
import sys

import requests

steam_api = (
    "https://api.steampowered.com/"  # noqa: E501
    "ISteamRemoteStorage/GetPublishedFileDetails/v1/"
)
mods_dir = "/home/z/Development/projects/arma3/a3modlink/tests/mods"
links_dir = "/home/z/Development/projects/arma3/a3modlink/tests/links"


def sanitise_path(path=str):
    new_str = ""

    if path == "":
        return path

    new_str = re.sub(r"[^a-zA-Z0-9_]", "_", path)

    return re.sub(r"_+", "_", new_str)


def read_mods(path=mods_dir):
    with os.scandir(path) as entries:
        return [
            entry.name
            for entry in entries
            if entry.is_dir() and entry.name.isdigit()  # noqa: E501
        ]


def read_links(path=links_dir, sort=True):
    results = dict()
    with os.scandir(path) as entries:
        for entry in entries:
            if entry.is_symlink():
                results[entry.name] = os.path.abspath(os.readlink(entry.path))

        if sort:
            return dict(sorted(results.items()))

        return results


def get_mod_title(int=int, lc=True):
    title = ""
    workshop_id = int
    form_data = {"itemcount": 1, "publishedfileids[0]": workshop_id}

    response = requests.post(steam_api, data=form_data)

    try:
        title = response.json()["response"]["publishedfiledetails"][0]["title"]
    except KeyError:
        pass

    if lc:
        return title.lower()

    return title


def link_mod(mod_id: int):
    title = sanitise_path(get_mod_title(mod_id))

    if title:
        try:
            os.symlink(f"{mods_dir}/{mod_id}", f"{links_dir}/{title}")
        except OSError as e:
            print(f"Unable to create link for {title}, {mod_id}, {e}.")
    else:
        print(f"Unable to get title for {mod_id}.")


def unlink_mod(titles):
    for title in titles:
        try:
            os.unlink(f"{links_dir}/{title}")
        except OSError as e:
            print(f"Unable to remove link for {title}. {e}.")


def remove_broken_links():
    links = read_links()

    if len(links) != 0:
        for k, v in links.items():
            if not (os.path.exists(v) or os.path.isdir(v)):
                try:
                    os.unlink(f"{links_dir}/{k}")
                except OSError as e:
                    print(f"Unable to remove {k}, {e}.")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "A simple script that lookup Arma 3 workshop"
            " for downloaded mods and create or remove their symbolic links."
        ),
        epilog="Example: %(prog)s --unlink 2183975396",
    )

    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List existing mod ids and their names",
    )

    parser.add_argument(
        "-a",
        "--add",
        type=int,
        const=-1,
        nargs="?",
        metavar="ID",
        help="Add a symlink from given mod id or no id given for all found in mod_dir",
    )

    parser.add_argument(
        "-u",
        "--unlink",
        type=str,
        nargs="*",
        metavar="Title(s)",
        help="Remove symlinks from given mod ids separated by space",
    )

    parser.add_argument(
        "-b",
        "--broken",
        action="store_true",
        help="Remove any broken symlinks",
    )

    args = parser.parse_args(args=None if sys.argv[1:] else parser.print_help())

    if args.list:
        mods = read_links()

        if mods:
            print(f"{'Title':<40}Actual Path")
            print("=" * 90)
            for k, v in mods.items():
                print(f"{k:<40}{v}")

    if args.add:
        if args.add == -1:
            mods = read_mods()
            links = read_links()

            if len(links) != 0:
                ids = [path.split("/")[-1] for path in links.values()]
                final_ids = [
                    item for item in mods + ids if (item in mods) != (item in ids)
                ]

                if len(final_ids) != 0:
                    for mod_id in final_ids:
                        link_mod(mod_id)
                else:
                    print("All mods have already been linked.")
            else:
                for mod in mods:
                    link_mod(mod)
        else:
            link_mod(args.add)

    if args.unlink:
        unlink_mod(args.unlink)

    if args.broken:
        remove_broken_links()


if __name__ == "__main__":
    main()
