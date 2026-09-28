"""Danh gia model da train (checkpoint FL/centralized) tren traffic THAT
(trich xuat boi src/preprocessing/extract_features_nfstream.py tu pcap thu
qua tcpdump trong luc chay Mininet/hping3) - kiem tra cross-domain
generalization, khac voi tap test noi bo cua CICDDoS2019.

Chay:
    python3 src/evaluation/live_validate.py \
        --checkpoint checkpoints/fl_fedavg_binary.pt \
        --features data/captures/features_attack_xxx.csv data/captures/features_benign_yyy.csv
"""
import argparse
import os
import sys

import joblib
import pandas as pd
import torch
from sklearn.metrics import (accuracy_score, classification_report,
                              confusion_matrix, precision_recall_fscore_support)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "models"))
from cnn1d import CNN1D  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_checkpoint(path):
    ckpt = torch.load(path, weights_only=False, map_location="cpu")
    model = CNN1D(
        input_dim=ckpt["input_dim"],
        num_classes=ckpt["num_classes"],
        hidden_dim=ckpt["hidden_dim"],
        dropout=ckpt["dropout"],
    )
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    return model, ckpt["mode"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--features", nargs="+", required=True,
                         help="1 hoac nhieu file CSV tu extract_features_nfstream.py (se gop lai)")
    args = parser.parse_args()

    model, mode = load_checkpoint(args.checkpoint)
    scaler_path = os.path.join(PROJECT_ROOT, "data", "processed", f"scaler_{mode}.joblib")
    scaler_bundle = joblib.load(scaler_path)
    scaler, feature_columns = scaler_bundle["scaler"], scaler_bundle["feature_columns"]

    dfs = [pd.read_csv(f) for f in args.features]
    df = pd.concat(dfs, ignore_index=True)
    print(f">>> Tong {len(df)} flow tu {len(args.features)} file, phan bo nhan:")
    print(df["label"].value_counts())

    label_map = {"benign": 0, "attack": 1}
    y_true = df["label"].map(label_map).to_numpy()

    X = df[feature_columns].to_numpy()
    X_scaled = scaler.transform(X)
    X_tensor = torch.tensor(X_scaled, dtype=torch.float32)

    with torch.no_grad():
        logits = model(X_tensor)
        y_pred = logits.argmax(dim=1).numpy()

    acc = accuracy_score(y_true, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="macro", zero_division=0
    )

    print(f"\n>>> KET QUA VALIDATION TREN TRAFFIC THAT (checkpoint: {args.checkpoint})")
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1:        {f1:.4f}")
    print("\nConfusion matrix (hang=that, cot=du doan, thu tu [benign, attack]):")
    print(confusion_matrix(y_true, y_pred))
    print("\nBao cao chi tiet:")
    print(classification_report(y_true, y_pred, target_names=["benign", "attack"], zero_division=0))


if __name__ == "__main__":
    main()
