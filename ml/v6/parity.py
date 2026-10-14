"""C++ vs PyTorch parity for an exported v6 net, plus the plane-8 weight audit.
   python ml/v6/parity.py CHECKPOINT.pt SHARD_DIR EXPORT_DIR   (EXPORT_DIR holds policy_weights_v6.hpp; needs WSL g++ for the C++ side)"""
import glob, os, subprocess, sys, shlex, shutil, hashlib
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).resolve().parent; sys.path[:0] = [str(HERE), str(HERE.parent)]
from train import Policy
from shard_manifest import owned_shards
ck_path, shards, exp = sys.argv[1:4]
ck = torch.load(ck_path, map_location="cpu"); m = Policy(planes=19, scalars=6, ch=ck["channels"], hidden=ck["hidden"], classes=7)
m.load_state_dict(ck["state_dict"]); m.eval()
# plane-8 audit: conv1 input channel 8 weights must stay inside the init range (plane 8 is zero in v6)
w = m.c1.weight.detach().numpy(); bound = 1 / np.sqrt(w.shape[1] * 9)
print("plane-8 conv1 max|w| %.4f, init bound %.4f -> %s" % (np.abs(w[:, 8]).max(), bound, "OK" if np.abs(w[:, 8]).max() <= bound + 1e-6 else "FAIL"))
rng = np.random.default_rng(0); P = []; S = []
for f in owned_shards(shards)[:2]:
    z = np.load(f); ix = np.sort(rng.choice(len(z["labels"]), 600, replace=False)); P.append(z["planes"][ix]); S.append(z["scalars"][ix])
P = np.concatenate(P); S = np.concatenate(S)
P = np.concatenate([P, rng.integers(0, 256, (400, 19, 15, 15), dtype=np.uint8) * (rng.random((400, 19, 1, 1)) < 0.5)]).astype(np.uint8)
S = np.concatenate([S, rng.random((400, 6), dtype=np.float32)]).astype(np.float32)
with torch.no_grad():
    ref = m(torch.from_numpy(P).float() / 255, torch.from_numpy(S)).numpy()
tmp = Path(exp); (tmp / "in.bin").write_bytes(np.int32(len(P)).tobytes() + P.tobytes() + S.tobytes())
if not (tmp/'policy_nn_v6.hpp').exists():
    shutil.copy2(HERE/'policy_nn_v6.hpp',tmp/'policy_nn_v6.hpp')
shutil.copy2(HERE/'parity_main.cpp',tmp/'parity_main.cpp')
print('C++ inference header SHA256:',hashlib.sha256((tmp/'policy_nn_v6.hpp').read_bytes()).hexdigest())
def wsl_path(path):
    value = str(Path(path).resolve()).replace("\\", "/")
    return "/mnt/" + value[0].lower() + value[2:]

e = wsl_path(tmp); h = wsl_path(HERE)
script = tmp / "build_run.sh"
lines = ["#!/bin/bash",
         'if which g++ >/dev/null 2>&1; then CXX=(g++); else CXX=("$HOME/toolchains/zig-linux/zig" c++); fi',
         '"${CXX[@]}" -O2 -std=c++17 ' + shlex.join(["-I"+e,"-I"+h,e+"/parity_main.cpp","-o",e+"/parity.out"]) + " && " + shlex.join([e+"/parity.out",e+"/in.bin",e+"/out.bin"])]
script.write_bytes((chr(10).join(lines) + chr(10)).encode())
r = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", e + "/build_run.sh"], capture_output=True, text=True)
if r.returncode: print("C++ build/run failed:", (r.stdout + r.stderr)[-600:]); sys.exit(1)
out = np.fromfile(tmp / "out.bin", np.float32).reshape(-1, 7)
err = np.abs(out - ref).max(); agree = (out.argmax(1) == ref.argmax(1)).mean()
print(f"states {len(P)}  max|C++ - torch| = {err:.2e}  argmax agreement {agree:.4f}  -> {'PASS' if err < 1e-3 and agree == 1.0 else 'FAIL'}")
