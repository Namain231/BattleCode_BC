import csv, sys, pathlib
src, outdir, col = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3]
outdir.mkdir(parents=True, exist_ok=True)
writers = {}
files = {}
with open(src, newline='', encoding='utf-8') as fh:
    r = csv.DictReader(fh)
    fieldnames = r.fieldnames
    for row in r:
        t = row.get(col)
        if t not in writers:
            safe = "".join(c if c.isalnum() else "_" for c in t)[:40]
            f = open(outdir / f"{safe}.csv", "w", newline='', encoding='utf-8')
            files[t] = f
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            writers[t] = w
        writers[t].writerow(row)
for f in files.values(): f.close()
print(f"{len(writers)} teams split from {src} -> {outdir}")
for t in writers: print(" ", t)
