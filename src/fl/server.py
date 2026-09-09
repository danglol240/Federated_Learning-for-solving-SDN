"""Chay FL simulation (FedAvg / FedProx / FedNova) tren du lieu da chia o
data/splits/client_<i>/ (sinh boi src/preprocessing/split_noniid.py).

Chien luoc chon qua config/config.yaml: fl.strategy = fedavg | fedprox | fednova.
Ket qua (loss/accuracy/precision/recall/f1 theo tung round) ghi ra
results/fl_<strategy>_<mode>.csv de ve do thi so sanh sau (Giai doan 3).

Chay thu:
    cd src/fl
    python3 server.py --strategy fedavg
    python3 server.py --strategy fedprox
    python3 server.py --strategy fednova
"""
import argparse
import csv
import os
import sys

import flwr as fl
from flwr.common import ndarrays_to_parameters
from flwr.server import ServerConfig

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "models"))

from client import get_parameters, load_config, make_client_fn  # noqa: E402
from cnn1d import CNN1D  # noqa: E402
from dataset import infer_input_dim  # noqa: E402
from fednova_strategy import FedNova  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def weighted_average(metrics_list):
    """metrics_list: list[(num_examples, {"accuracy":..., "precision":..., ...})]"""
    total = sum(n for n, _ in metrics_list)
    if total == 0:
        return {}
    keys = metrics_list[0][1].keys()
    return {k: sum(n * m[k] for n, m in metrics_list) / total for k in keys}


def build_strategy(strategy_name, cfg, initial_parameters):
    fl_cfg = cfg["fl"]
    common_kwargs = dict(
        fraction_fit=fl_cfg["fraction_fit"],
        fraction_evaluate=1.0,
        min_fit_clients=fl_cfg["min_available_clients"],
        min_evaluate_clients=fl_cfg["min_available_clients"],
        min_available_clients=fl_cfg["min_available_clients"],
        initial_parameters=initial_parameters,
        fit_metrics_aggregation_fn=weighted_average,
        evaluate_metrics_aggregation_fn=weighted_average,
    )

    if strategy_name == "fedavg":
        return fl.server.strategy.FedAvg(**common_kwargs)
    elif strategy_name == "fedprox":
        return fl.server.strategy.FedProx(proximal_mu=fl_cfg["fedprox_mu"], **common_kwargs)
    elif strategy_name == "fednova":
        return FedNova(**common_kwargs)
    else:
        raise ValueError(f"Chien luoc khong ho tro: {strategy_name}")


def save_history(history, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    rounds = [r for r, _ in history.losses_distributed]
    losses = dict(history.losses_distributed)
    metrics_by_round = {r: m for r, m in history.metrics_distributed.get("accuracy", [])}

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["round", "loss"]
        extra_keys = sorted(k for k in history.metrics_distributed.keys())
        writer.writerow(header + extra_keys)
        for r in rounds:
            row = [r, losses.get(r)]
            for k in extra_keys:
                round_to_val = dict(history.metrics_distributed[k])
                row.append(round_to_val.get(r))
            writer.writerow(row)
    print(f">>> Da ghi log training vao {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", choices=["fedavg", "fedprox", "fednova"], default=None)
    parser.add_argument("--splits-dir", default=os.path.join(PROJECT_ROOT, "data", "splits"))
    args = parser.parse_args()

    cfg = load_config()
    strategy_name = args.strategy or cfg["fl"]["strategy"]
    mode = cfg["task"]["mode"]

    input_dim = infer_input_dim(args.splits_dir)
    dummy_model = CNN1D(
        input_dim=input_dim,
        num_classes=cfg["task"][mode]["num_classes"],
        hidden_dim=cfg["model"]["hidden_dim"],
        dropout=cfg["model"]["dropout"],
    )
    initial_parameters = ndarrays_to_parameters(get_parameters(dummy_model))

    strategy = build_strategy(strategy_name, cfg, initial_parameters)
    client_fn = make_client_fn(cfg, args.splits_dir)

    history = fl.simulation.start_simulation(
        client_fn=client_fn,
        num_clients=cfg["fl"]["num_clients"],
        config=ServerConfig(num_rounds=cfg["fl"]["num_rounds"]),
        strategy=strategy,
    )

    out_path = os.path.join(PROJECT_ROOT, "results", f"fl_{strategy_name}_{mode}.csv")
    save_history(history, out_path)


if __name__ == "__main__":
    main()
