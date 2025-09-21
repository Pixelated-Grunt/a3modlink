#!/usr/bin/env python3
"""
Arma 3 Workshop Mod Link Manager

This script manages symbolic links for Arma 3 workshop mods by:
1. Fetching mod titles from Steam Workshop API
2. Creating sanitized symbolic links from mod IDs to human-readable names
3. Managing existing links (listing, removing, cleaning broken links)

The script helps organize Arma 3 mod directories by creating meaningful
symbolic links instead of using numeric workshop IDs.

Example usage:
    python modlink_manager.py --mods-dir ./mods --links-dir ./links --add 2183975396
    python modlink_manager.py --list
    python modlink_manager.py --unlink "mod_title" --broken
"""

import argparse
import errno
import re
from pathlib import Path
from typing import Dict, List, Optional

import requests
from requests.exceptions import RequestException

# Configuration - should be configurable via CLI args
STEAM_API = (
    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
)


def sanitise_path(path: str) -> str:
    """
    Sanitize a string to be safe for use as a filename.

    Replaces any non-alphanumeric characters with underscores and collapses
    multiple consecutive underscores into single underscores.

    Args:
        path: The input string to sanitize

    Returns:
        str: Sanitized string safe for filesystem use

    Example:
        >>> sanitise_path("My Mod @Home v1.2")
        'My_Mod_Home_v1_2'
    """
    if not path:
        return path

    # Replace non-alphanumeric characters with underscores
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", path)
    # Collapse multiple underscores
    return re.sub(r"_+", "_", sanitized)


def read_mods(mods_dir: str) -> List[str]:
    """
    Read mod directories that contain only digits (workshop IDs).

    Scans the specified directory for subdirectories whose names are
    entirely numeric, which typically correspond to Steam Workshop IDs.

    Args:
        mods_dir: Path to the directory containing mod subdirectories

    Returns:
        List[str]: List of mod directory names (workshop IDs)

    Raises:
        ValueError: If the mods directory does not exist

    Example:
        >>> read_mods("./mods")
        ['2183975396', '450814997', '333310405']
    """
    mods_path = Path(mods_dir)
    if not mods_path.exists() or not mods_path.is_dir():
        raise ValueError(f"Mods directory does not exist: {mods_dir}")

    return [
        entry.name
        for entry in mods_path.iterdir()
        if entry.is_dir() and entry.name.isdigit()
    ]


def read_links(links_dir: str, sort: bool = True) -> Dict[str, str]:
    """
    Read existing symbolic links and their targets.

    Scans the links directory for symbolic links and returns a dictionary
    mapping link names to their target paths. Optionally sorts the results
    alphabetically by link name.

    Args:
        links_dir: Path to the directory containing symbolic links
        sort: Whether to sort the results alphabetically by link name

    Returns:
        Dict[str, str]: Dictionary mapping link names to target paths.
                        Returns empty dict if directory doesn't exist.

    Example:
        >>> read_links("./links")
        {'cfba': '/path/mods/450814997', 'cba_a3': '/path/mods/333310405'}
    """
    links_path = Path(links_dir)
    if not links_path.exists():
        return {}

    results = {}
    for entry in links_path.iterdir():
        if entry.is_symlink():
            try:
                target_path = entry.resolve()
                results[entry.name] = str(target_path)
            except OSError:
                # Broken symlink
                continue

    return dict(sorted(results.items())) if sort else results


def get_mod_title(mod_id: int, lowercase: bool = True) -> Optional[str]:
    """
    Get mod title from Steam Workshop API.

    Fetches the title of a mod from the Steam Workshop API using the
    mod's workshop ID. Handles network errors and API response parsing.

    Args:
        mod_id: Steam Workshop ID of the mod
        lowercase: Whether to return the title in lowercase

    Returns:
        Optional[str]: Mod title if successful, None if failed

    Example:
        >>> get_mod_title(333310405)
        'cba_a3'
    """
    form_data = {"itemcount": 1, "publishedfileids[0]": mod_id}

    try:
        response = requests.post(STEAM_API, data=form_data, timeout=10)
        response.raise_for_status()

        data = response.json()
        title = data["response"]["publishedfiledetails"][0]["title"]
        return title.lower() if lowercase else title

    except (RequestException, KeyError, IndexError) as e:
        print(f"Error fetching title for mod {mod_id}: {e}")
        return None


def link_mod(mod_id: int, mods_dir: str, links_dir: str) -> bool:
    """
    Create symbolic link for a mod.

    Creates a symbolic link from the mod's workshop ID directory to a
    sanitized version of the mod's title. Handles errors during link
    creation and validates that the source directory exists.

    Args:
        mod_id: Steam Workshop ID of the mod to link
        mods_dir: Directory containing the mod subdirectories
        links_dir: Directory where symbolic links should be created

    Returns:
        bool: True if link was created successfully, False otherwise

    Example:
        >>> link_mod(333310405, "./mods", "./links")
        Created link: cba_a3 -> ./mods/333310405
        True
    """
    title = sanitise_path(get_mod_title(mod_id))
    if not title:
        print(f"Unable to get title for mod {mod_id}")
        return False

    source_path = Path(mods_dir).resolve() / str(mod_id)
    target_path = Path(links_dir) / title

    if not source_path.exists():
        print(f"Mod directory does not exist: {source_path}")
        return False

    try:
        target_path.symlink_to(source_path, target_is_directory=True)
        print(f"Created link: {title} -> {source_path}")
        return True
    except OSError as e:
        if e.errno == errno.EEXIST:
            return True
        else:
            print(f"Unable to create link for {title} (mod {mod_id}): {e}")
            return False


def unlink_mod(titles: List[str], links_dir: str) -> None:
    """
    Remove symbolic links.

    Removes one or more symbolic links from the links directory.
    Validates that each path is actually a symbolic link before
    attempting removal.

    Args:
        titles: List of link names to remove
        links_dir: Directory containing the symbolic links

    Example:
        >>> unlink_mod(["cba_a3", "cfba"], "./links")
        Removed link: cba_a3
        Removed link: cfba
    """
    links_path = Path(links_dir)
    for title in titles:
        link_path = links_path / title
        if link_path.exists() and link_path.is_symlink():
            try:
                link_path.unlink()
                print(f"Removed link: {title}")
            except OSError as e:
                print(f"Unable to remove link {title}: {e}")
        else:
            print(f"Link not found or not a symlink: {title}")


def remove_broken_links(links_dir: str) -> None:
    """
    Remove broken symbolic links.

    Scans the links directory for symbolic links whose targets no longer
    exist and removes them. Provides feedback on the number of broken
    links found and removed.

    Args:
        links_dir: Directory containing the symbolic links

    Example:
        >>> remove_broken_links("./links")
        Removed broken link: old_mod
        Removed 1 broken link(s)
    """
    links = read_links(links_dir, sort=False)
    broken_count = 0

    for name, target_path in links.items():
        if not Path(target_path).exists():
            try:
                (Path(links_dir) / name).unlink()
                print(f"Removed broken link: {name}")
                broken_count += 1
            except OSError as e:
                print(f"Unable to remove broken link {name}: {e}")

    if broken_count == 0:
        print("No broken links found.")
    else:
        print(f"Removed {broken_count} broken link(s)")


def main():
    """
    Main function that parses command-line arguments and executes commands.

    Handles the primary workflow of the script:
    - Parsing command-line arguments
    - Validating and creating directories if needed
    - Executing the requested operations (list, add, unlink, clean)

    Command-line interface provides four main operations:
    1. List existing links and their targets
    2. Add new links for specified mod IDs
    3. Remove existing links by their names
    4. Clean up broken symbolic links
    """
    parser = argparse.ArgumentParser(
        description="Manage symbolic links for Arma 3 workshop mods",
        epilog="Example: %(prog)s --mods-dir ./mods --links-dir ./links --add 2183975396",
    )

    # Directory arguments
    parser.add_argument(
        "--mods-dir",
        default="./mods",
        help="Mods directory containing workshop ID subdirectories (default: ./mods)",
    )
    parser.add_argument(
        "--links-dir",
        default="./links",
        help="Directory where symbolic links will be created (default: ./links)",
    )

    # Action arguments
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List existing links and their targets",
    )
    parser.add_argument(
        "-a",
        "--add",
        type=int,
        nargs="*",
        metavar="ID",
        help="Add links for specified mod IDs or all mods if no IDs provided",
    )
    parser.add_argument(
        "-u",
        "--unlink",
        nargs="+",
        metavar="TITLE",
        help="Remove links for specified titles",
    )
    parser.add_argument(
        "-b", "--broken", action="store_true", help="Remove broken symbolic links"
    )

    args = parser.parse_args()

    # Execute requested operations
    if args.list:
        links = read_links(args.links_dir)
        if links:
            print(f"{'Title':<40} {'Target':<40}")
            print("=" * 80)
            for title, target in links.items():
                print(f"{title:<40} {target:<40}")
        else:
            print("No links found.")

    if args.add is not None:
        mod_ids = args.add if args.add else read_mods(args.mods_dir)
        for mod_id in mod_ids:
            link_mod(mod_id, args.mods_dir, args.links_dir)

    if args.unlink:
        unlink_mod(args.unlink, args.links_dir)

    if args.broken:
        remove_broken_links(args.links_dir)


if __name__ == "__main__":
    main()
