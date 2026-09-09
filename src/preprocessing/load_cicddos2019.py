"""Doc CSV CICDDoS2019 (dac trung da trich qua CICFlowMeter, vd ban Kaggle
dhoogla/cicddos2019) va chuan hoa ve DataFrame dung chung cho split_noniid.py
va cac buoc training.

CSV CICFlowMeter goc co quirk: ten cot co khoang trang dau (" Label",
" Source IP"...) va gia tri Infinity/NaN o mot so dong (do chia cho 0 khi
tinh Flow Bytes/s, Flow Packets/s). Ham load_raw_csv() xu ly ca hai.

Chay thu:
    python3 src/preprocessing/load_cicddos2019.py --input data/raw/cicddos2019 --mode binary
"""
import argparse
import glob
import os

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cot dinh danh / khong dung lam dac trung hoc may (leak thong tin hoac khong
# co y nghia thong ke). Ten da chuan hoa (strip + lower + underscore).
ID_COLUMNS = {
    "flow_id", "source_ip", "src_ip", "destination_ip", "dst_ip",
    "timestamp", "simillarhttp", "unnamed:_0",
}

LABEL_ALIASES = {"label"}


def _normalize_col(col: str) -> str:
    return col.strip().lower().replace(" ", "_").replace("/", "_")


def load_raw_csv(path_or_dir):
    """Doc 1 file CSV hoac gop toan bo *.csv trong 1 thu muc."""
    if os.path.isdir(path_or_dir):
        files = sorted(glob.glob(os.path.join(path_or_dir, "**", "*.csv"), recursive=True))
        if not files:
            raise FileNotFoundError(f"Khong tim thay file .csv nao trong {path_or_dir}")
        frames = [pd.read_csv(f, low_memory=False) for f in files]
        df = pd.concat(frames, ignore_index=True)
    else:
        df = pd.read_csv(path_or_dir, low_memory=False)

    df.columns = [_normalize_col(c) for c in df.columns]

    label_col = next((c for c in df.columns if c in LABEL_ALIASES), None)
    if label_col is None:
        raise ValueError(f"Khong tim thay cot Label trong CSV. Cac cot hien co: {list(df.columns)[:10]}...")
    if label_col != "label":
        df = df.rename(columns={label_col: "label"})

    df = df.replace([np.inf, -np.inf], np.nan)
    n_before = len(df)
    df = df.dropna()
    n_after = len(df)
    if n_after < n_before:
        print(f">>> Da loai {n_before - n_after} dong chua Inf/NaN ({n_before} -> {n_after})")

    return df


def to_feature_label(df, mode, task_cfg):
    """Tach df thanh (X: DataFrame dac trung so, y: Series nhan int) theo
    task.mode trong config.yaml ("binary" hoac "multiclass").
    """
    drop_cols = {"label"} | {c for c in ID_COLUMNS if c in df.columns}
    feature_cols = [c for c in df.columns if c not in drop_cols]
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce")
    bad_rows = X.isna().any(axis=1)
    if bad_rows.any():
        print(f">>> Loai them {bad_rows.sum()} dong co cot dac trung khong phai so")
        X = X[~bad_rows]
        df = df[~bad_rows]

    raw_label = df["label"].astype(str).str.strip().str.lower()

    if mode == "binary":
        classes = [c.lower() for c in task_cfg["binary"]["classes"]]
        y = raw_label.apply(lambda v: 0 if v == "benign" else 1)
    elif mode == "multiclass":
        classes = [c.lower() for c in task_cfg["multiclass"]["classes"]]
        alias_to_idx = {}
        for idx, cls in enumerate(classes):
            alias_to_idx[cls] = idx
        def map_label(v):
            for cls, idx in alias_to_idx.items():
                if cls == "benign":
                    if v == "benign":
                        return idx
                elif cls in v:
                    return idx
            return None
        y = raw_label.apply(map_label)
        unmapped = y.isna()
        if unmapped.any():
            unknown_vals = sorted(raw_label[unmapped].unique())
            print(f">>> Canh bao: {unmapped.sum()} dong co nhan khong khop danh sach multiclass, se bi loai: {unknown_vals}")
            X = X[~unmapped]
            y = y[~unmapped]
        y = y.astype(int)
    else:
        raise ValueError(f"task.mode khong hop le: {mode} (chi nhan binary|multiclass)")

    return X.reset_index(drop=True), y.reset_index(drop=True)


def load_config(config_path=None):
    config_path = config_path or os.path.join(PROJECT_ROOT, "config", "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=os.path.join(PROJECT_ROOT, "data", "raw", "cicddos2019"))
    parser.add_argument("--mode", choices=["binary", "multiclass"], default=None,
                         help="Mac dinh lay tu config.yaml task.mode")
    args = parser.parse_args()

    cfg = load_config()
    mode = args.mode or cfg["task"]["mode"]

    df = load_raw_csv(args.input)
    X, y = to_feature_label(df, mode, cfg["task"])

    print(f">>> Tong so dong: {len(X)}, so dac trung: {X.shape[1]}")
    print(f">>> Phan bo nhan (mode={mode}):")
    print(y.value_counts().sort_index())


if __name__ == "__main__":
    main()
