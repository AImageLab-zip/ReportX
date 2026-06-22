"""
Permanently delete previously-uploaded BraTS samples from a Yggdrasil instance,
by annotation batch. For each batch in annotation_splits.json, finds the
batch's folder (by name), HARD-deletes every patient currently in it
(including their stored files in object storage), then deletes the now-empty
folder itself.

Run with: .venv/bin/python yggdrasil/delete_brats.py --host https://... \
    --username U --password P --splits-json annotation_splits.json [--batches BATCH_01 BATCH_02] [--yes]
"""

import argparse
import json
import re
import sys

import requests
from rich.console import Console
from rich.prompt import Confirm

console = Console()

CSRF_RE = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')
SCAN_ROW_RE = re.compile(r'data-scan-id="(\d+)"')
TOTAL_PAGES_RE = re.compile(r'Page\s+\d+\s+of\s+(\d+)')


def get_csrf_token(session: requests.Session, url: str) -> str:
    page = session.get(url)
    page.raise_for_status()
    match = CSRF_RE.search(page.text)
    if not match:
        raise RuntimeError(f"Could not find CSRF token on {url}")
    return match.group(1)


def login(session: requests.Session, base: str, username: str, password: str) -> None:
    login_url = f"{base}/login/"
    csrf_token = get_csrf_token(session, login_url)
    resp = session.post(
        login_url,
        data={
            "username": username,
            "password": password,
            "csrfmiddlewaretoken": csrf_token,
        },
        headers={"Referer": login_url},
    )
    resp.raise_for_status()
    if "/login/" in resp.url:
        raise RuntimeError("Login failed, still on login page")


def resolve_folder_id(session: requests.Session, base: str, csrf_token: str, name: str) -> str | None:
    """get_or_create is idempotent: if the folder already exists this just
    returns its id without creating a duplicate."""
    resp = session.post(
        f"{base}/brain/folders/create/",
        json={"name": name},
        headers={
            "X-CSRFToken": csrf_token,
            "Referer": f"{base}/brain/upload/",
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success"):
        return None
    return str(payload["folder"]["id"])


def list_patient_ids_in_folder(session: requests.Session, base: str, folder_id: str) -> list[int]:
    patient_ids: list[int] = []
    page = 1
    total_pages = 1
    while page <= total_pages:
        resp = session.get(
            f"{base}/brain/patients/",
            params={"folder": folder_id, "per_page": 100, "page": page},
        )
        resp.raise_for_status()
        patient_ids.extend(int(pid) for pid in SCAN_ROW_RE.findall(resp.text))
        match = TOTAL_PAGES_RE.search(resp.text)
        if match:
            total_pages = int(match.group(1))
        page += 1
    return patient_ids


def bulk_purge(session: requests.Session, base: str, csrf_token: str, scan_ids: list[int]) -> dict:
    resp = session.post(
        f"{base}/brain/patients/bulk-purge/",
        json={"scan_ids": scan_ids},
        headers={
            "X-CSRFToken": csrf_token,
            "Referer": f"{base}/brain/upload/",
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    return resp.json()


def delete_folder(session: requests.Session, base: str, csrf_token: str, folder_id: str, force: bool = False) -> dict:
    resp = session.delete(
        f"{base}/brain/folders/{folder_id}/delete/",
        params={"force": "true"} if force else {},
        headers={"X-CSRFToken": csrf_token, "Referer": f"{base}/brain/upload/"},
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", required=True, help="e.g. https://yggdrasil.example.org")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--splits-json", required=True, help="annotation_splits.json used during upload")
    parser.add_argument("--batches", nargs="*", help="Only delete these batch names (default: all)")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    parser.add_argument("--keep-folders", action="store_true", help="Don't delete the per-batch folders, only the patients")
    parser.add_argument("--dry-run", action="store_true", help="List what would be deleted without deleting")
    args = parser.parse_args()

    host = args.host
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", host):
        host = f"https://{host}"
    base = host.rstrip("/")

    with open(args.splits_json) as f:
        splits: dict[str, list[str]] = json.load(f)

    batch_names = args.batches if args.batches else list(splits.keys())
    unknown = [b for b in batch_names if b not in splits]
    for b in unknown:
        console.print(f"[yellow]!! Unknown batch {b!r}, skipping[/]")
    batch_names = [b for b in batch_names if b in splits]

    session = requests.Session()
    login(session, base, args.username, args.password)
    csrf_token = get_csrf_token(session, f"{base}/brain/upload/")

    batch_folders: dict[str, str] = {}
    batch_patient_ids: dict[str, list[int]] = {}
    for batch_name in batch_names:
        folder_id = resolve_folder_id(session, base, csrf_token, batch_name)
        if folder_id is None:
            console.print(f"[yellow]!! Could not resolve folder for batch {batch_name!r}, skipping[/]")
            continue
        batch_folders[batch_name] = folder_id
        patient_ids = list_patient_ids_in_folder(session, base, folder_id)
        batch_patient_ids[batch_name] = patient_ids
        console.print(f"[bold]{batch_name}[/] -> folder {folder_id}: {len(patient_ids)} modalities(s), {len(patient_ids)//5} patient(s) found")

    all_ids = sorted({pid for ids in batch_patient_ids.values() for pid in ids})
    if not all_ids and args.keep_folders:
        console.print("[yellow]Nothing to delete.[/]")
        return

    if args.dry_run:
        console.print(f"\n[bold]Dry run:[/] would PERMANENTLY delete {len(all_ids)} modalities(s): {all_ids}")
        if not args.keep_folders:
            console.print(f"[bold]Dry run:[/] would also delete {len(batch_folders)} folder(s): {list(batch_folders.values())}")
        return

    if not args.yes and not Confirm.ask(
        f"\nPERMANENTLY delete {len(all_ids)} patient(s) (and their files) across "
        f"{len(batch_patient_ids)} batch(es)"
        + ("" if args.keep_folders else f", then delete {len(batch_folders)} folder(s)")
        + "? This cannot be undone."
    ):
        console.print("Aborted.")
        return

    if all_ids:
        result = bulk_purge(session, base, csrf_token, all_ids)
        if result.get("success"):
            console.print(f"[bold green]{result.get('message', 'Done')}[/]")
            if result.get("storage_errors"):
                console.print(f"[yellow]Warning: failed to delete {len(result['storage_errors'])} storage file(s):[/]")
                for path in result["storage_errors"]:
                    console.print(f"  [yellow]- {path}[/]")
        else:
            console.print(f"[bold red]Patient delete failed:[/] {result}")
            sys.exit(1)

    if args.keep_folders:
        return

    failed_folders = []
    for batch_name, folder_id in batch_folders.items():
        result = delete_folder(session, base, csrf_token, folder_id, force=True)
        if result.get("success"):
            console.print(f"[green]   ✓ deleted folder for {batch_name} (id {folder_id})[/]")
        else:
            console.print(f"[red]   ✗ could not delete folder for {batch_name} (id {folder_id}): {result}[/]")
            failed_folders.append(batch_name)

    if failed_folders:
        console.print(f"\n[bold red]{len(failed_folders)} folder(s) could not be deleted:[/] {', '.join(failed_folders)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
