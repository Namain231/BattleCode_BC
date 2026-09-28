"""Zip the training code and a dataset folder for Colab: upload the result to the root of Google Drive.

    python ml/pack_for_colab.py [--data ml/data] [--out ml_upload.zip]
"""
import argparse
import glob
import os
import zipfile

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="ml/data")
ap.add_argument("--out", default="ml_upload.zip")
a = ap.parse_args()
with zipfile.ZipFile(a.out, "w", zipfile.ZIP_STORED) as z:   # shards are already compressed
    for f in ("ml/train.py",):
        z.write(f, f)
    for f in sorted(glob.glob(os.path.join(a.data, "shard_*.npz"))):
        z.write(f, "ml/data/" + os.path.basename(f))
print(a.out, f"{os.path.getsize(a.out) / 1e6:.0f} MB")
