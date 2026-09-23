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
import torch
from flwr.common import ndarrays_to_parameters, parameters_to_ndarrays
from flwr.server import ServerConfig

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "models"))

from client import get_parameters, load_config, make_client_fn, set_parameters  # noqa: E402
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
    # min_fit_clients TRUOC DAY bi ep bang min_available_clients -> fraction_fit<1
    # khong co tac dung gi (luon lay du 3/3 client). Tach rieng de fraction_fit
    # thuc su tao ra partial participation (vd fraction_fit=0.67 + min_fit_clients=2
    # -> chi 2/3 client duoc chon moi round).
    min_fit_clients = fl_cfg.get("min_fit_clients", fl_cfg["min_available_clients"])
    common_kwargs = dict(
        fraction_fit=fl_cfg["fraction_fit"],
        fraction_evaluate=1.0,
        min_fit_clients=min_fit_clients,
        min_evaluate_clients=fl_cfg["min_available_clients"],
        min_available_clients=fl_cfg["min_available_clients"],
        initial_parameters=initial_parameters,
        fit_metrics_aggregation_fn=weighted_average,
        evaluate_metrics_aggregation_fn=weighted_average,
    )

    if strategy_name == "fedavg":
        strategy = fl.server.strategy.FedAvg(**common_kwargs)
    elif strategy_name == "fedprox":
        strategy = fl.server.strategy.FedProx(proximal_mu=fl_cfg["fedprox_mu"], **common_kwargs)
    elif strategy_name == "fednova":
        strategy = FedNova(**common_kwargs)
    else:
        raise ValueError(f"Chien luoc khong ho tro: {strategy_name}")

    return _capture_last_parameters(strategy)


def _capture_last_parameters(strategy):
    """Boc aggregate_fit de luu lai parameters cua round gan nhat vao
    strategy.last_parameters - flwr khong tu luu lai gia tri nay, va
    start_simulation() cung khong tra ve model cuoi cung, chi tra ve History
    (log so lieu). Can de sau nay torch.save() duoc global model cuoi."""
    original_aggregate_fit = strategy.aggregate_fit

    def aggregate_fit_and_capture(server_round, results, failures):
        parameters, metrics = original_aggregate_fit(server_round, results, failures)
        if parameters is not None:
            strategy.last_parameters = parameters
        return parameters, metrics

    strategy.aggregate_fit = aggregate_fit_and_capture
    strategy.last_parameters = None
    return strategy


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
    parser.add_argument("--seed", type=int, default=None,
                         help="Seed rieng cho lan chay nay (khac project.seed dung de chia du "
                              "lieu). Dat torch.manual_seed truoc khi khoi tao global model, va "
                              "truyen xuong client de kiem soat thu tu shuffle batch - dung cho "
                              "multi-seed replication. Neu dat, output se co hau to _seed<N> de "
                              "khong ghi de ket qua mac dinh.")
    parser.add_argument("--mu", type=float, default=None,
                         help="Override fedprox_mu (chi co tac dung voi --strategy fedprox). "
                              "Dung de sweep mu ma khong can sua config.yaml. Neu dat, output se "
                              "co hau to _mu<X>.")
    parser.add_argument("--lr", type=float, default=None,
                         help="Override fl.learning_rate cho lan chay nay (dung de sweep LR rieng "
                              "cho 1 strategy, vd giam LR cho fednova khi tau_i chenh lech manh, "
                              "khong anh huong config mac dinh dung cho cac strategy khac). Neu "
                              "dat, output se co hau to _lr<X>.")
    args = parser.parse_args()

    cfg = load_config()
    strategy_name = args.strategy or cfg["fl"]["strategy"]
    mode = cfg["task"]["mode"]

    if args.mu is not None:
        cfg["fl"]["fedprox_mu"] = args.mu
    if args.lr is not None:
        cfg["fl"]["learning_rate"] = args.lr

    if args.seed is not None:
        torch.manual_seed(args.seed)

    input_dim = infer_input_dim(args.splits_dir)
    dummy_model = CNN1D(
        input_dim=input_dim,
        num_classes=cfg["task"][mode]["num_classes"],
        hidden_dim=cfg["model"]["hidden_dim"],
        dropout=cfg["model"]["dropout"],
    )
    initial_parameters = ndarrays_to_parameters(get_parameters(dummy_model))

    strategy = build_strategy(strategy_name, cfg, initial_parameters)
    client_fn = make_client_fn(cfg, args.splits_dir, run_seed=args.seed)

    history = fl.simulation.start_simulation(
        client_fn=client_fn,
        num_clients=cfg["fl"]["num_clients"],
        config=ServerConfig(num_rounds=cfg["fl"]["num_rounds"]),
        strategy=strategy,
    )

    suffix = ""
    if args.seed is not None:
        suffix += f"_seed{args.seed}"
    if args.mu is not None:
        suffix += f"_mu{args.mu}"
    if args.lr is not None:
        suffix += f"_lr{args.lr}"
    out_path = os.path.join(PROJECT_ROOT, "results", f"fl_{strategy_name}_{mode}{suffix}.csv")
    save_history(history, out_path)

    if strategy.last_parameters is not None:
        set_parameters(dummy_model, parameters_to_ndarrays(strategy.last_parameters))
        ckpt_path = os.path.join(PROJECT_ROOT, "checkpoints", f"fl_{strategy_name}_{mode}{suffix}.pt")
        os.makedirs(os.path.dirname(ckpt_path), exist_ok=True)
        torch.save({
            "state_dict": dummy_model.state_dict(),
            "input_dim": input_dim,
            "num_classes": cfg["task"][mode]["num_classes"],
            "hidden_dim": cfg["model"]["hidden_dim"],
            "dropout": cfg["model"]["dropout"],
            "mode": mode,
            "strategy": strategy_name,
        }, ckpt_path)
        print(f">>> Da luu model global cuoi cung vao {ckpt_path}")
    else:
        print(">>> Canh bao: khong bat duoc parameters cuoi cung, khong luu checkpoint")


if __name__ == "__main__":
    main()
