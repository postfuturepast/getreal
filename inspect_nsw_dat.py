"""
Quick diagnostic — prints the first 5 B records from a cached NSW DAT file
so we can see the exact field structure before fixing the parser.
"""
import io, zipfile, os, glob

CACHE_DIR = ".nsw_psi_cache"

# Find any cached weekly ZIP
zips = sorted(glob.glob(os.path.join(CACHE_DIR, "weekly_*.zip")))
if not zips:
    zips = sorted(glob.glob(os.path.join(CACHE_DIR, "annual_*.zip")))

if not zips:
    print("No cached ZIPs found — run load_nsw_data.py first")
    exit(1)

zip_path = zips[0]
print(f"Inspecting: {zip_path}\n")

with zipfile.ZipFile(zip_path) as zf:
    dat_files = [n for n in zf.namelist() if n.upper().endswith(".DAT")]
    print(f"DAT files in ZIP: {len(dat_files)}")
    print(f"First few: {dat_files[:5]}\n")

    # Find first DAT with B records
    for dat_name in dat_files:
        with zf.open(dat_name) as f:
            content = f.read().decode("latin-1")
        lines = content.splitlines()
        b_lines = [l for l in lines if l.startswith("B")]
        if b_lines:
            print(f"── File: {dat_name} ──")
            print(f"Total lines: {len(lines)}, B records: {len(b_lines)}\n")
            print("First A record (header):")
            a_lines = [l for l in lines if l.startswith("A")]
            if a_lines:
                print(f"  {a_lines[0]}")
            print("\nFirst 3 B records (raw):")
            for line in b_lines[:3]:
                print(f"  {line}")
            print("\nField breakdown of first B record:")
            parts = b_lines[0].split(";")
            for i, p in enumerate(parts):
                print(f"  [{i:2d}] = {repr(p)}")
            break
    else:
        print("No B records found in any DAT file!")
        print("\nSample lines from first DAT:")
        with zf.open(dat_files[0]) as f:
            content = f.read().decode("latin-1")
        for line in content.splitlines()[:20]:
            print(f"  {repr(line)}")
