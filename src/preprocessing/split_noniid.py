"""Chia du lieu CICDDoS2019 (da qua load_cicddos2019.py) cho 3 client theo
phan bo Non-IID (label-skew) khai bao trong config/noniid_distribution.yaml.

Thuat toan: voi moi lop nhan, gop toan bo mau cua lop do lai thanh 1 pool
(xao tron 1 lan theo seed), roi lan luot chia cho tung client theo so luong
mong muon = phan_bo[client][lop] * client_size. Moi mau chi thuoc DUNG 1
client (khong trung lap giua cac client). Neu pool khong du, lay het phan
con lai va canh bao.

Chay thu:
    python3 src/preprocessing/split_noniid.py --input data/raw/cicddos2019
"""
import argparse
import os

import numpy as np
import pandas as pd
import yaml

from load_cicddos2019 import load_raw_csv, to_feature_label, load_config, PROJECT_ROOT


def load_noniid_distribution(mode, config_path=None):
    config_path = config_path or os.path.join(PROJECT_ROOT, "config", "noniid_distribution.yaml")
    with open(config_path, "r") as f:
        full = yaml.safe_load(f)
    if mode not in full:
        raise ValueError(f"noniid_distribution.yaml khong co khoi '{mode}'. Cac khoi co san: {list(full.keys())}")
    return full[mode]


def assign_clients(y, distribution, client_size, seed):
    """Tra ve dict {client_key: list_of_row_index} khong trung lap."""
    rng = np.random.RandomState(seed)
    classes = sorted(y.unique())
    pool = {}
    for c in classes:
        idx = y.index[y == c].to_numpy().copy()
        rng.shuffle(idx)
        pool[c] = list(idx)

    assignment = {client: [] for client in distribution}
    for client, meta in distribution.items():
        phan_bo = meta["phan_bo"]
        for cls_name, frac in phan_bo.items():
            cls_key = _match_class_key(cls_name, classes, meta)
            if cls_key is None or cls_key not in pool:
                continue
            want = int(round(frac * client_size))
            take = pool[cls_key][:want]
            pool[cls_key] = pool[cls_key][want:]
            if len(take) < want:
                print(f">>> Canh bao: client={client} lop={cls_name} thieu du lieu "
                      f"(muon {want}, chi lay duoc {len(take)})")
            assignment[client].extend(take)

    return assignment


def _match_class_key(cls_name, classes, meta):
    """phan_bo dung ten lop dang string (vd 'ldap'), con y da la int index
    (tu to_feature_label). Can anh xa nguoc ten -> index bang thu tu classes
    trong task config, truyen kem qua meta['_classes_order'] tu main()."""
    order = meta.get("_classes_order")
    if order is None:
        return None
    try:
        return order.index(cls_name)
    except ValueError:
        return None


def train_val_test_split(indices, test_size, val_size, seed):
    rng = np.random.RandomState(seed)
    idx = np.array(indices)
    rng.shuffle(idx)
    n = len(idx)
    n_test = int(round(n * test_size))
    n_val = int(round(n * val_size))
    test_idx = idx[:n_test]
    val_idx = idx[n_test:n_test + n_val]
    train_idx = idx[n_test + n_val:]
    return train_idx, val_idx, test_idx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=os.path.join(PROJECT_ROOT, "data", "raw", "cicddos2019"))
    parser.add_argument("--output", default=os.path.join(PROJECT_ROOT, "data", "splits"))
    parser.add_argument("--mode", choices=["binary", "multiclass"], default=None)
    parser.add_argument("--client-size", type=int, default=None,
                         help="So mau moi client. Mac dinh = tong so mau // so client.")
    args = parser.parse_args()

    cfg = load_config()
    mode = args.mode or cfg["task"]["mode"]
    seed = cfg["project"]["seed"]
    classes_order = [c.lower() for c in cfg["task"][mode]["classes"]]

    df = load_raw_csv(args.input)
    X, y = to_feature_label(df, mode, cfg["task"])

    distribution = load_noniid_distribution(mode)
    for meta in distribution.values():
        meta["_classes_order"] = classes_order

    client_size = args.client_size or (len(X) // len(distribution))
    print(f">>> Tong so mau: {len(X)}, so client: {len(distribution)}, client_size={client_size}")

    assignment = assign_clients(y, distribution, client_size, seed)

    test_size = cfg["data"]["test_size"]
    val_size = cfg["data"]["val_size"]

    for client, indices in assignment.items():
        client_dir = os.path.join(args.output, client)
        os.makedirs(client_dir, exist_ok=True)
        train_idx, val_idx, test_idx = train_val_test_split(indices, test_size, val_size, seed)

        for split_name, split_idx in [("train", train_idx), ("val", val_idx), ("test", test_idx)]:
            out_df = X.loc[split_idx].copy()
            out_df["label"] = y.loc[split_idx].to_numpy()
            out_path = os.path.join(client_dir, f"{split_name}.csv")
            out_df.to_csv(out_path, index=False)

        print(f">>> {client}: total={len(indices)} train={len(train_idx)} "
              f"val={len(val_idx)} test={len(test_idx)} -> {client_dir}")


if __name__ == "__main__":
    main()
