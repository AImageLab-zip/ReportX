"""
Upload BraTS samples to a Yggdrasil instance, one folder per annotation batch.

Expects the BraTS root directory laid out as:
    root_folder/
        BraTS-GLI-00002-000/
            BraTS-GLI-00002-000-t1c.nii.gz
            BraTS-GLI-00002-000-t1n.nii.gz
            BraTS-GLI-00002-000-t2f.nii.gz
            BraTS-GLI-00002-000-t2w.nii.gz

Batches come from annotation_splits.json (BATCH_01 -> [sample ids]). Each
batch gets its own freshly created Yggdrasil folder (named after the batch),
and all of the batch's samples are uploaded into it. The REMAINING batch
(samples not assigned to any clinician) is skipped by default; pass it
explicitly via --batches REMAINING if you really want it.

Before uploading, the script asks the server for every patient that already
exists (across all folders) and builds a name -> scan id map. For each
sample:
  - if it's already in the target folder, it's skipped entirely;
  - if it exists elsewhere (e.g. a repeated test-set sample assigned to
    several batches, or a sample left over from an interrupted previous run)
    its existing scan is added to the new folder via add-patients, with no
    re-upload;
  - otherwise it's uploaded fresh.
This makes interrupted/partial runs safe to re-launch, and avoids creating
duplicate Patient rows for samples that appear in more than one batch.

Use --concurrency N to send up to N upload requests in parallel.

Run with: .venv/bin/python yggdrasil/upload_brats.py --host https://... \
    --username U --password P --root-folder /path/to/brats --concurrency 4
"""

import argparse
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

console = Console()

# BraTS filename suffix -> Yggdrasil upload field name. Adjust to match the
# field names actually exposed by the brain/upload/ form.
MODALITY_FIELDS = {
    "t1c": "braintumor-mri-t1c",
    "t1n": "braintumor-mri-t1",
    "t2f": "braintumor-mri-flair",
    "t2w": "braintumor-mri-t2",
    "seg": "braintumor-mri-seg",
}

# Batches that exist in the splits json but aren't assigned to clinicians for
# annotation; never uploaded unless explicitly named via --batches.
EXCLUDED_BATCHES = {"REMAINING","REPORTX"}

CSRF_RE = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')
EXCEPTION_VALUE_RE = re.compile(r'<pre class="exception_value">(.*?)</pre>', re.S)
ERRORLIST_RE = re.compile(r'<ul class="errorlist">(.*?)</ul>', re.S)
TOTAL_PAGES_RE = re.compile(r'Page\s+\d+\s+of\s+(\d+)')
SCAN_ROW_RE = re.compile(r'data-scan-id="(\d+)"')
# Matches the BraTS-style sample id used as the patient "name" (e.g.
# BraTS-GLI-00002-000), so we can pull it out of a listing row's visible
# text without depending on the exact surrounding markup.
SAMPLE_ID_RE = re.compile(r'BraTS-[A-Za-z0-9]+-\d+-\d+')


def extract_error_message(html: str) -> str:
    match = EXCEPTION_VALUE_RE.search(html)
    if not match:
        match = ERRORLIST_RE.search(html)
    if match:
        text = re.sub(r"<[^>]+>", " ", match.group(1)).strip()
        text = re.sub(r"\s+", " ", text)
        return text
    return html[:500]


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


def create_folder(session: requests.Session, base: str, csrf_token: str, name: str) -> str:
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
        raise RuntimeError(f"Could not create folder {name!r}: {payload}")
    return str(payload["folder"]["id"])


def fetch_patient_name_to_id(
    session: requests.Session, base: str, folder_id: str | None = None
) -> dict[str, int]:
    """Maps sample id -> scan id, scoped to one folder, or every patient on
    the server if folder_id is None. Each listing row carries a
    data-scan-id="<id>" marker; we pair it with the BraTS-style sample id
    found in that row's own text (up to the next data-scan-id marker), since
    the exact row markup isn't documented."""
    mapping: dict[str, int] = {}
    params: dict[str, object] = {"per_page": 100}
    if folder_id is not None:
        params["folder"] = folder_id

    page = 1
    total_pages = 1
    while page <= total_pages:
        resp = session.get(f"{base}/brain/patients/", params={**params, "page": page})
        resp.raise_for_status()
        text = resp.text
        matches = list(SCAN_ROW_RE.finditer(text))
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            name_match = SAMPLE_ID_RE.search(text[start:end])
            if name_match:
                mapping[name_match.group(0)] = int(m.group(1))
        total_match = TOTAL_PAGES_RE.search(text)
        if total_match:
            total_pages = int(total_match.group(1))
        page += 1
    return mapping


def add_existing_patient_to_folder(
    session: requests.Session, base: str, csrf_token: str, scan_id: int, folder_id: str
) -> None:
    resp = session.post(
        f"{base}/brain/folders/add-patients/",
        json={"scan_ids": [scan_id], "folder_id": folder_id},
        headers={
            "X-CSRFToken": csrf_token,
            "Referer": f"{base}/brain/upload/",
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success"):
        raise RuntimeError(f"Could not add scan {scan_id} to folder {folder_id}: {payload}")


def find_modality_files(patient_dir: Path, sample_id: str) -> dict[str, Path]:
    found = {}
    for suffix, field in MODALITY_FIELDS.items():
        path = patient_dir / f"{sample_id}-{suffix}.nii.gz"
        if path.exists():
            found[field] = path
    return found


def upload_patient(
    session: requests.Session,
    base: str,
    upload_url: str,
    csrf_token: str,
    sample_id: str,
    modality_files: dict[str, Path],
    folder_id: str | None,
) -> requests.Response:
    data = {
        "csrfmiddlewaretoken": csrf_token,
        "name": sample_id,
    }
    for field in modality_files:
        data[f"{field}_upload_type"] = "file"
    if folder_id is not None:
        data["folder"] = str(folder_id)

    opened = [open(path, "rb") for path in modality_files.values()]
    try:
        files = {
            field: (path.name, handle, "application/gzip")
            for (field, path), handle in zip(modality_files.items(), opened)
        }
        # IMPORTANT: don't follow the redirect. upload_patient() returns
        # 302 -> patient_list on success, but re-renders the same upload
        # page with status 200 on a validation error (e.g. bad folder id).
        # If we let requests follow redirects, both cases look like a final
        # 200 and become indistinguishable.
        resp = session.post(
            upload_url,
            data=data,
            files=files,
            headers={"Referer": upload_url, "X-CSRFToken": csrf_token},
            allow_redirects=False,
        )
    finally:
        for handle in opened:
            handle.close()
    return resp


def process_sample(
    session: requests.Session,
    base: str,
    upload_url: str,
    csrf_token: str,
    root_folder: Path,
    sample_id: str,
    folder_id: str | None,
    dry_run: bool,
    known_scan_id: int | None,
) -> tuple[str, bool, str]:
    """Returns (sample_id, ok, message). If known_scan_id is set, the sample
    already exists elsewhere on the server and is just added to this folder
    instead of being re-uploaded."""
    if known_scan_id is not None:
        if dry_run:
            return sample_id, True, f"would add existing scan {known_scan_id} to folder"
        add_existing_patient_to_folder(session, base, csrf_token, known_scan_id, folder_id)
        return sample_id, True, f"added existing scan {known_scan_id} to folder (no re-upload)"

    patient_dir = root_folder / sample_id
    if not patient_dir.is_dir():
        return sample_id, False, "missing directory"

    modality_files = find_modality_files(patient_dir, sample_id)
    if not modality_files:
        return sample_id, False, "no recognized modality files"

    if dry_run:
        return sample_id, True, f"would upload {[p.name for p in modality_files.values()]}"

    resp = upload_patient(session, base, upload_url, csrf_token, sample_id, modality_files, folder_id)
    # Success path is a 302 redirect to patient_list. A 200 here means the
    # form was re-rendered with validation errors and nothing was created.
    if resp.status_code == 302:
        return sample_id, True, "uploaded"
    return sample_id, False, extract_error_message(resp.text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", required=True, help="e.g. https://yggdrasil.example.org")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--root-folder", required=True, type=Path, help="BraTS root_folder/ containing one dir per sample")
    parser.add_argument("--splits-json", type=Path, default=Path(__file__).parent / "annotation_splits.json")
    parser.add_argument("--batches", nargs="*", help="Only upload these batch names (default: all assigned batches, excluding REMAINING)")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of parallel upload requests")
    parser.add_argument("--dry-run", action="store_true", help="List what would be uploaded without sending requests")
    args = parser.parse_args()

    host = args.host
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", host):
        host = f"https://{host}"
    base = host.rstrip("/")

    with open(args.splits_json) as f:
        splits: dict[str, list[str]] = json.load(f)

    if args.batches:
        batch_names = list(args.batches)
        for batch_name in batch_names:
            if batch_name not in splits:
                console.print(f"[yellow]!! Unknown batch {batch_name!r}, skipping[/]")
        batch_names = [b for b in batch_names if b in splits]
    else:
        batch_names = [b for b in splits if b not in EXCLUDED_BATCHES]

    print_lock = threading.Lock()
    patients_lock = threading.Lock()

    session = requests.Session()
    upload_url = f"{base}/brain/upload/"

    if not args.dry_run:
        login(session, base, args.username, args.password)
        csrf_token = get_csrf_token(session, upload_url)
    else:
        csrf_token = ""

    # Global sample id -> scan id map across every folder, so samples that
    # appear in multiple batches (or are left over from an interrupted prior
    # run) are recognized no matter where they currently live.
    known_patients: dict[str, int] = {} if args.dry_run else fetch_patient_name_to_id(session, base)

    # Resolve each batch's folder up front (create_folder is get_or_create,
    # so this is idempotent), then split its samples into: already in this
    # folder (skip), known elsewhere (add to folder, no re-upload), or new
    # (upload fresh).
    folder_ids: dict[str, str | None] = {}
    samples_by_batch: dict[str, list[tuple[str, int | None]]] = {}
    skipped_already_here = 0
    for batch_name in batch_names:
        all_sample_ids = splits[batch_name]
        if args.dry_run:
            folder_ids[batch_name] = None
            samples_by_batch[batch_name] = [(s, known_patients.get(s)) for s in all_sample_ids]
            continue

        folder_id = create_folder(session, base, csrf_token, batch_name)
        folder_ids[batch_name] = folder_id
        already_here = fetch_patient_name_to_id(session, base, folder_id)

        to_process = []
        for sample_id in all_sample_ids:
            if sample_id in already_here:
                skipped_already_here += 1
                continue
            to_process.append((sample_id, known_patients.get(sample_id)))
        samples_by_batch[batch_name] = to_process

    if skipped_already_here:
        console.print(f"[dim]Skipping {skipped_already_here} sample(s) already present in their target folder[/]")

    total_samples = sum(len(v) for v in samples_by_batch.values())

    failures: list[str] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.fields[batch]}[/]"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[cyan]{task.fields[sample]}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("upload", total=total_samples, batch="", sample="")

        for batch_name in batch_names:
            sample_ids = samples_by_batch[batch_name]
            if not sample_ids:
                continue

            folder_id = folder_ids[batch_name]
            folder_desc = "(dry-run, not created)" if args.dry_run else folder_id
            console.print(f"[bold]== {batch_name}[/] ({len(sample_ids)} samples) -> folder {folder_desc}")

            freshly_uploaded: set[str] = set()

            def handle_result(sample_id: str, ok: bool, message: str, was_fresh_upload: bool) -> None:
                with print_lock:
                    progress.update(task, batch=batch_name, sample=sample_id)
                    if ok:
                        console.print(f"[green]   ✓ {sample_id}: {message}[/]")
                        if was_fresh_upload:
                            freshly_uploaded.add(sample_id)
                    else:
                        console.print(f"[red]   ✗ {sample_id}: {message}[/]")
                        failures.append(sample_id)
                    progress.advance(task)

            with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
                futures = {
                    executor.submit(
                        process_sample, session, base, upload_url, csrf_token,
                        args.root_folder, sample_id, folder_id, args.dry_run, known_scan_id,
                    ): (sample_id, known_scan_id)
                    for sample_id, known_scan_id in sample_ids
                }
                for future in as_completed(futures):
                    sample_id, known_scan_id = futures[future]
                    result_id, ok, message = future.result()
                    handle_result(result_id, ok, message, was_fresh_upload=known_scan_id is None)

            # Learn the scan ids of anything freshly uploaded in this batch so
            # later batches recognize it instead of re-uploading.
            if freshly_uploaded and not args.dry_run:
                refreshed = fetch_patient_name_to_id(session, base, folder_id)
                with patients_lock:
                    for sample_id in freshly_uploaded:
                        if sample_id in refreshed:
                            known_patients[sample_id] = refreshed[sample_id]

    if failures:
        console.print(f"\n[bold red]{len(failures)} sample(s) failed:[/] {', '.join(failures)}")
        sys.exit(1)
    else:
        console.print("\n[bold green]All samples uploaded successfully.[/]")


if __name__ == "__main__":
    main()
