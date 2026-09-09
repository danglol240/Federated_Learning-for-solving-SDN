"""Doc du lieu 1 client tu data/splits/client_<i>/{train,val,test}.csv
(sinh boi src/preprocessing/split_noniid.py) thanh torch DataLoader.
"""
import os

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, TensorDataset


def _csv_to_tensors(path):
    df = pd.read_csv(path)
    y = torch.tensor(df["label"].to_numpy(), dtype=torch.long)
    X = torch.tensor(df.drop(columns=["label"]).to_numpy(), dtype=torch.float32)
    return X, y


def infer_input_dim(splits_dir, client_name="client_1"):
    """So cot dac trung thuc te (khong tinh 'label') tu file train.csv da
    chia. Dung de dung model dung shape thay vi cfg['model']['input_dim']
    (chi la placeholder, khong khop so dac trung that cua CICDDoS2019)."""
    path = os.path.join(splits_dir, client_name, "train.csv")
    header = pd.read_csv(path, nrows=0)
    return header.shape[1] - 1


def load_client_data(client_dir, batch_size=64):
    train_X, train_y = _csv_to_tensors(os.path.join(client_dir, "train.csv"))
    val_X, val_y = _csv_to_tensors(os.path.join(client_dir, "val.csv"))
    test_X, test_y = _csv_to_tensors(os.path.join(client_dir, "test.csv"))

    train_loader = DataLoader(TensorDataset(train_X, train_y), batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(TensorDataset(val_X, val_y), batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(TensorDataset(test_X, test_y), batch_size=batch_size, shuffle=False)

    return train_loader, val_loader, test_loader, train_X.shape[1]
