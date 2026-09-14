"""Ve do thi so sanh FedAvg / FedProx / FedNova / Centralized:
- accuracy theo round (tu results/fl_<strategy>_<mode>.csv va results/centralized_<mode>.csv)
- communication overhead (tong so byte truyen qua lai) cua 3 strategy FL, Centralized = 0

Luu ket qua vao results/figures/accuracy_comparison_<mode>.png va
results/figures/communication_overhead_<mode>.png

Chay:
    python3 src/evaluation/plot_comparison.py
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "models"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fl"))

from cnn1d import CNN1D  # noqa: E402
from client import load_config  # noqa: E402
from dataset import infer_input_dim  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STRATEGIES = ["fedavg", "fedprox", "fednova"]
COLORS = {"fedavg": "#1f77b4", "fedprox": "#ff7f0e", "fednova": "#2ca02c", "centralized": "#7f7f7f"}


def load_results(results_dir, mode):
    data = {}
    for strategy in STRATEGIES:
        path = os.path.join(results_dir, f"fl_{strategy}_{mode}.csv")
        if os.path.exists(path):
            data[strategy] = pd.read_csv(path)
        else:
            print(f">>> Canh bao: khong tim thay {path}, bo qua {strategy}")

    centralized_path = os.path.join(results_dir, f"centralized_{mode}.csv")
    if os.path.exists(centralized_path):
        data["centralized"] = pd.read_csv(centralized_path)
    else:
        print(f">>> Canh bao: khong tim thay {centralized_path}, bo qua centralized")

    return data


def plot_accuracy(data, mode, out_dir):
    plt.figure(figsize=(8, 5))
    for name, df in data.items():
        plt.plot(df["round"], df["accuracy"], marker="o", label=name, color=COLORS.get(name))
    plt.xlabel("Round / Epoch")
    plt.ylabel("Accuracy")
    plt.title(f"Accuracy theo round - mode={mode}")
    plt.legend()
    plt.grid(alpha=0.3)
    out_path = os.path.join(out_dir, f"accuracy_comparison_{mode}.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f">>> Da luu {out_path}")


def compute_communication_bytes(cfg, splits_dir, num_rounds):
    input_dim = infer_input_dim(splits_dir)
    mode = cfg["task"]["mode"]
    model = CNN1D(
        input_dim=input_dim,
        num_classes=cfg["task"][mode]["num_classes"],
        hidden_dim=cfg["model"]["hidden_dim"],
        dropout=cfg["model"]["dropout"],
    )
    num_params = sum(p.numel() for p in model.parameters())
    bytes_per_transfer = num_params * 4  # float32
    num_clients = cfg["fl"]["num_clients"]
    # Moi round: server gui model xuong (download) + nhan model tu moi client ve (upload)
    total_bytes_per_strategy = num_rounds * num_clients * 2 * bytes_per_transfer
    return total_bytes_per_strategy, num_params


def plot_communication(data, cfg, splits_dir, mode, out_dir):
    num_rounds = cfg["fl"]["num_rounds"]
    total_bytes, num_params = compute_communication_bytes(cfg, splits_dir, num_rounds)

    labels, values = [], []
    for strategy in STRATEGIES:
        if strategy in data:
            labels.append(strategy)
            values.append(total_bytes / (1024 ** 2))  # MB
    if "centralized" in data:
        labels.append("centralized")
        values.append(0.0)

    plt.figure(figsize=(6, 5))
    plt.bar(labels, values, color=[COLORS.get(l) for l in labels])
    plt.ylabel("Tong du lieu truyen qua mang (MB)")
    plt.title(f"Communication overhead - mode={mode}\n({num_params:,} tham so/model, {num_rounds} round)")
    out_path = os.path.join(out_dir, f"communication_overhead_{mode}.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f">>> Da luu {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default=os.path.join(PROJECT_ROOT, "results"))
    parser.add_argument("--splits-dir", default=os.path.join(PROJECT_ROOT, "data", "splits"))
    args = parser.parse_args()

    cfg = load_config()
    mode = cfg["task"]["mode"]
    out_dir = os.path.join(args.results_dir, "figures")
    os.makedirs(out_dir, exist_ok=True)

    data = load_results(args.results_dir, mode)
    if not data:
        print(">>> Khong co ket qua nao de ve. Chay src/fl/server.py va src/baselines/centralized.py truoc.")
        return

    plot_accuracy(data, mode, out_dir)
    plot_communication(data, cfg, args.splits_dir, mode, out_dir)


if __name__ == "__main__":
    main()
