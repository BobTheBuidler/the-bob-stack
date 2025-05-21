import requests
from bs4 import BeautifulSoup
import csv
import os
import datetime
import json

# ====== SETTINGS ======

PYPI_USER = 'your_username'  # <-- CHANGE this for your actual username
CSV_FILE = 'daily_downloads.csv'
OUT_DIR = 'package_metadata'

# ====== FETCH ALL USER PACKAGES FROM PYPI ======

def get_user_packages(username):
    print(f"Fetching PyPI packages for user: {username}")
    base_url = f'https://pypi.org/user/{username}/'
    resp = requests.get(base_url)
    if not resp.ok:
        raise Exception(f"Failed to fetch PyPI user page for {username}: {resp.status_code}")
    soup = BeautifulSoup(resp.text, "html.parser")
    pkgs = [a.text.strip() for a in soup.select('a.package-snippet')]
    return pkgs

# ====== GET LATEST RELEASE INFO FROM PYPI API ======

def get_latest_release_info(pkg):
    url = f'https://pypi.org/pypi/{pkg}/json'
    resp = requests.get(url)
    if not resp.ok:
        print(f"PyPI info not found for {pkg}")
        return None
    data = resp.json()
    latest_ver = data['info']['version']
    releases = data['releases'].get(latest_ver)
    if not releases:
        print(f"No releases found for {pkg} {latest_ver}")
        return None
    latest_file = releases[0]
    return {
        "url": latest_file['url'],
        "filename": latest_file['filename'],
        "upload_time": latest_file['upload_time_iso_8601'],
    }

# ====== GET DAILY DOWNLOAD COUNT (PYPISTATS) ======

def get_daily_downloads(pkg):
    url = f"https://pypistats.org/api/packages/{pkg}/recent"
    r = requests.get(url)
    if not r.ok:
        print(f"Could not get daily downloads for {pkg}")
        return None
    j = r.json()
    if "data" not in j or "last_day" not in j["data"]:
        return None
    return j["data"]["last_day"]

# ====== CSV UTILITIES ======

def read_csv(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, newline='') as f:
        return list(csv.DictReader(f))

def write_csv(rows, fieldnames, filename):
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

# ====== MAIN ======

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    pkgs = get_user_packages(PYPI_USER)
    print(f"Found {len(pkgs)} packages: {pkgs}")

    # Prepare today's row for the CSV
    date_str = datetime.date.today().isoformat()
    today_data = {'date': date_str}
    for pkg in pkgs:
        count = get_daily_downloads(pkg)
        today_data[pkg] = count if count is not None else 0

    # Load CSV and append today's row
    rows = read_csv(CSV_FILE)
    fieldnames = ['date'] + pkgs
    # If new columns appear, update past rows with zeros for those columns
    if rows:
        all_flds = set(fieldnames) | set(rows[0].keys())
        fieldnames = ['date'] + sorted(f for f in all_flds if f != 'date')
        for r in rows:
            for col in fieldnames:
                if col not in r:
                    r[col] = 0
    rows.append(today_data)
    write_csv(rows, fieldnames, CSV_FILE)

    # Compute cumulative totals
    lib_totals = {pkg: 0 for pkg in pkgs}
    for row in rows:
        for pkg in pkgs:
            lib_totals[pkg] += int(row.get(pkg, 0) or 0)

    # Generate per-package JSON files
    for pkg in pkgs:
        relinfo = get_latest_release_info(pkg)
        if not relinfo:
            print(f"Skipping {pkg}, no release info")
            continue
        meta = {
            "url": relinfo["url"],
            "filename": relinfo["filename"],
            "upload_time": relinfo["upload_time"],
            "download_count": lib_totals.get(pkg, 0),
            "rank": None  # Placeholder; see earlier messages for options
        }
        with open(os.path.join(OUT_DIR, f"{pkg}.json"), "w") as jf:
            json.dump(meta, jf, indent=2)
        print(f"Wrote {pkg}.json")

    # Optionally print summary
    print("\n=== Cumulative Totals ===")
    for pkg, total in lib_totals.items():
        print(f"{pkg}: {total}")
    print(f"\nGrand total: {sum(lib_totals.values())}")

if __name__ == "__main__":
    main()
