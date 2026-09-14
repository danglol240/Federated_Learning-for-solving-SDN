"""Baseline centralized: gop toan bo du lieu 3 client (khong chia FL) de
train 1 model duy nhat, lam moc so sanh voi FedAvg/FedProx/FedNova.

Dung lai chinh du lieu da chia o data/splits/client_{1,2,3}/ (gop nguoc lai
thanh 1 tap) thay vi doc lai CICDDoS2019 tu dau - vi cac client la partition
khong chong lap cua cung 1 tap da duoc StandardScaler o split_noniid.py, gop
lai dung la tap goc voi dac trung da scale nhat quan.

Chay:
    python3 src/baselines/centralized.py
"""
import argparse
import csv
import glob
import os
import sys

import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "models"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fl"))

from cnn1d import CNN1D  # noqa: E402
from client import evaluate_model, load_config  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_combined(splits_dir, split_name):
    files = sorted(glob.glob(os.path.join(splits_dir, "client_*", f"{split_name}.csv")))
    if not files:
        raise FileNotFoundError(
            f"Khong tim thay {split_name}.csv nao trong {splits_dir}/client_*/ "
            "- chay src/preprocessing/split_noniid.py truoc."
        )
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    y = torch.tensor(df["label"].to_numpy(), dtype=torch.long)
    X = torch.tensor(df.drop(columns=["label"]).to_numpy(), dtype=torch.float32)
    return X, y


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--splits-dir", default=os.path.join(PROJECT_ROOT, "data", "splits"))
    args = parser.parse_args()

    cfg = load_config()
    mode = cfg["task"]["mode"]
    fl_cfg = cfg["fl"]

    train_X, train_y = load_combined(args.splits_dir, "train")
    val_X, val_y = load_combined(args.splits_dir, "val")

    print(f">>> Centralized: tong {len(train_X)} mau train, {len(val_X)} mau val, {train_X.shape[1]} dac trung")

    train_loader = DataLoader(TensorDataset(train_X, train_y), batch_size=fl_cfg["batch_size"], shuffle=True)
    val_loader = DataLoader(TensorDataset(val_X, val_y), batch_size=fl_cfg["batch_size"], shuffle=False)

    model = CNN1D(
        input_dim=train_X.shape[1],
        num_classes=cfg["task"][mode]["num_classes"],
        hidden_dim=cfg["model"]["hidden_dim"],
        dropout=cfg["model"]["dropout"],
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=fl_cfg["learning_rate"])
    criterion = nn.CrossEntropyLoss()

    # So epoch = num_rounds de so sanh tuong doi voi tong so vong FL (moi
    # round FL client cung chay local_epochs tren du lieu rieng cua no; o
    # day centralized chay 1 epoch/vong tren TOAN BO du lieu gop - khong
    # phai cung don vi tinh toan tuyet doi, chi la moc so sanh don gian).
    out_rows = []
    for epoch in range(1, fl_cfg["num_rounds"] + 1):
        model.train()
        for X, y in train_loader:
            optimizer.zero_grad()
            loss = criterion(model(X), y)
            loss.backward()
            optimizer.step()

        val_loss, metrics = evaluate_model(model, val_loader)
        out_rows.append([epoch, val_loss, metrics["accuracy"], metrics["f1"],
                          metrics["precision"], metrics["recall"]])
        print(f">>> [epoch {epoch}] loss={val_loss:.4f} accuracy={metrics['accuracy']:.4f} f1={metrics['f1']:.4f}")

    out_path = os.path.join(PROJECT_ROOT, "results", f"centralized_{mode}.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "loss", "accuracy", "f1", "precision", "recall"])
        writer.writerows(out_rows)
    print(f">>> Da ghi log training vao {out_path}")

    ckpt_path = os.path.join(PROJECT_ROOT, "checkpoints", f"centralized_{mode}.pt")
    os.makedirs(os.path.dirname(ckpt_path), exist_ok=True)
    torch.save({
        "state_dict": model.state_dict(),
        "input_dim": train_X.shape[1],
        "num_classes": cfg["task"][mode]["num_classes"],
        "hidden_dim": cfg["model"]["hidden_dim"],
        "dropout": cfg["model"]["dropout"],
        "mode": mode,
    }, ckpt_path)
    print(f">>> Da luu model vao {ckpt_path}")


if __name__ == "__main__":
    main()
