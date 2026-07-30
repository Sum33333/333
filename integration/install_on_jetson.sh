#!/usr/bin/env bash
# Install helper for Jetson conda env.
# Mentor task: try mmdet + mmengine; if fail, fall back to base libs.
set -euo pipefail

LOG_FILE="${1:-install_log.txt}"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "==== Jetson install helper ===="
echo "time: $(date)"
echo "user: $(whoami)"
echo "pwd : $(pwd)"
echo "python: $(command -v python || true)"
python -V || true

echo
echo "[1/4] Check conda env"
if [[ -z "${CONDA_DEFAULT_ENV:-}" ]]; then
  echo "WARNING: CONDA_DEFAULT_ENV is empty. Please: conda activate <your_env>"
else
  echo "conda env: $CONDA_DEFAULT_ENV"
fi

echo
echo "[2/4] Install base libraries (always useful)"
python -m pip install -U pip
python -m pip install "numpy" "Pillow" "opencv-python-headless" || \
  python -m pip install "numpy" "Pillow"

echo
echo "[3/4] Try install mmengine + mmdet"
set +e
python -m pip install -U openmim
python -m mim install "mmengine" || python -m pip install "mmengine"
# mmdet 3.x 常要求 mmcv>=2.0.0rc4,<2.2.0；装太新会 AssertionError
python -m mim install "mmcv==2.1.0" || python -m pip install "mmcv==2.1.0"
python -m mim install "mmdet" || python -m pip install "mmdet"
MM_OK=$?
set -e

echo
echo "[4/4] Verify imports"
set +e
python - <<'PY'
import sys
print("python", sys.version)
try:
    import numpy as np
    print("numpy", np.__version__)
except Exception as e:
    print("numpy FAIL", e)
try:
    from PIL import Image
    print("Pillow OK")
except Exception as e:
    print("Pillow FAIL", e)
try:
    import mmengine
    import mmdet
    print("MMDET OK", mmengine.__version__, mmdet.__version__)
except Exception as e:
    print("MMDET FAIL (use base/mock path):", e)
    sys.exit(2)
PY
VERIFY=$?
set -e

echo
if [[ $VERIFY -eq 0 ]]; then
  echo "RESULT: mmdet/mmengine install SUCCESS"
  exit 0
fi

echo "RESULT: mmdet/mmengine install FAILED"
echo "FALLBACK: use base library / mock adapter path"
echo "  python integration/mmdet_adapter_server.py --force-mock ..."
echo "  python integration/smoke_test.py"
exit 1
