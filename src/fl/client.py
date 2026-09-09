"""Flower NumPyClient dung chung cho ca 3 chien luoc (FedAvg/FedProx/FedNova).
Su khac biet giua cac chien luoc nam o server (aggregation) va o cau hinh
gui xuong qua `config` trong fit(): neu co "proximal_mu" > 0, client tu them
proximal term vao loss (dung FedProx). "tau" (so local step da chay) luon
duoc tra ve trong metrics de server FedNova dung khi aggregate.
"""
import copy
import os
import sys

import numpy as np
import torch
import torch.nn as nn
import yaml
from sklearn.metrics import precision_recall_fscore_support

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "models"))
sys.path.insert(0, os.path.dirname(__file__))

from cnn1d import CNN1D  # noqa: E402
from dataset import load_client_data  # noqa: E402

import flwr as fl


def get_parameters(model):
    return [val.cpu().numpy() for val in model.state_dict().values()]


def set_parameters(model, parameters):
    params_dict = zip(model.state_dict().keys(), parameters)
    state_dict = {k: torch.tensor(v) for k, v in params_dict}
    model.load_state_dict(state_dict, strict=True)


def train_one_client(model, train_loader, epochs, lr, proximal_mu=0.0, global_params=None):
    device = torch.device("cpu")
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    global_tensors = None
    if proximal_mu > 0 and global_params is not None:
        global_tensors = [torch.tensor(p) for p in global_params]

    steps = 0
    model.train()
    for _ in range(epochs):
        for X, y in train_loader:
            X, y = X.to(device), y.to(device)
            optimizer.zero_grad()
            out = model(X)
            loss = criterion(out, y)

            if global_tensors is not None:
                prox_term = 0.0
                for w, w_global in zip(model.parameters(), global_tensors):
                    prox_term += torch.sum((w - w_global) ** 2)
                loss = loss + (proximal_mu / 2.0) * prox_term

            loss.backward()
            optimizer.step()
            steps += 1

    return steps


def evaluate_model(model, data_loader):
    device = torch.device("cpu")
    model.to(device)
    model.eval()
    criterion = nn.CrossEntropyLoss()

    total_loss, total_correct, total_n = 0.0, 0, 0
    all_preds, all_labels = [], []
    with torch.no_grad():
        for X, y in data_loader:
            X, y = X.to(device), y.to(device)
            out = model(X)
            loss = criterion(out, y)
            total_loss += loss.item() * X.size(0)
            preds = out.argmax(dim=1)
            total_correct += (preds == y).sum().item()
            total_n += X.size(0)
            all_preds.extend(preds.tolist())
            all_labels.extend(y.tolist())

    precision, recall, f1, _ = precision_recall_fscore_support(
        all_labels, all_preds, average="macro", zero_division=0
    )
    accuracy = total_correct / total_n if total_n else 0.0
    avg_loss = total_loss / total_n if total_n else 0.0
    return avg_loss, {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}


class FlowerClient(fl.client.NumPyClient):
    def __init__(self, client_dir, cfg):
        self.cfg = cfg
        fl_cfg = cfg["fl"]
        mode = cfg["task"]["mode"]
        num_classes = cfg["task"][mode]["num_classes"]

        self.train_loader, self.val_loader, self.test_loader, input_dim = load_client_data(
            client_dir, batch_size=fl_cfg["batch_size"]
        )
        self.model = CNN1D(
            input_dim=input_dim,
            num_classes=num_classes,
            hidden_dim=cfg["model"]["hidden_dim"],
            dropout=cfg["model"]["dropout"],
        )
        self.local_epochs = fl_cfg["local_epochs"]
        self.lr = fl_cfg["learning_rate"]

    def get_parameters(self, config):
        return get_parameters(self.model)

    def fit(self, parameters, config):
        global_params = copy.deepcopy(parameters)
        set_parameters(self.model, parameters)
        proximal_mu = float(config.get("proximal_mu", 0.0))

        steps = train_one_client(
            self.model, self.train_loader, self.local_epochs, self.lr,
            proximal_mu=proximal_mu, global_params=global_params if proximal_mu > 0 else None,
        )

        num_examples = len(self.train_loader.dataset)
        metrics = {"tau": steps}
        return get_parameters(self.model), num_examples, metrics

    def evaluate(self, parameters, config):
        set_parameters(self.model, parameters)
        loss, metrics = evaluate_model(self.model, self.val_loader)
        num_examples = len(self.val_loader.dataset)
        return loss, num_examples, metrics


def make_client_fn(cfg, splits_dir):
    def client_fn(cid):
        client_dir = os.path.join(splits_dir, f"client_{int(cid) + 1}")
        return FlowerClient(client_dir, cfg).to_client()
    return client_fn


def load_config(config_path=None):
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = config_path or os.path.join(project_root, "config", "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)
