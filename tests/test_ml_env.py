import sys
print("Python:", sys.version.split()[0])
print("Vi tri:", sys.executable)
print("-" * 45)

checks = [
    ("torch", "PyTorch"), ("torchvision", "TorchVision"),
    ("flwr", "Flower"), ("numpy", "NumPy"), ("pandas", "Pandas"),
    ("sklearn", "scikit-learn"), ("scipy", "SciPy"),
    ("matplotlib", "Matplotlib"), ("seaborn", "Seaborn"),
    ("imblearn", "imbalanced-learn"), ("nfstream", "NFStream"),
    ("flask", "Flask"), ("yaml", "PyYAML"),
]

fails = 0
for mod, name in checks:
    try:
        m = __import__(mod)
        print(f"[OK]   {name:20s} {getattr(m, '__version__', 'OK')}")
    except Exception as e:
        print(f"[FAIL] {name:20s} {e}")
        fails += 1

print("-" * 45)
import torch
print("Thiet bi:", "GPU" if torch.cuda.is_available() else "CPU")
print("CPU threads:", torch.get_num_threads())

import flwr
from flwr.server.strategy import FedAvg
FedAvg(fraction_fit=1.0, min_fit_clients=3, min_available_clients=3)
print("FedAvg khoi tao: OK")

print("KET QUA:", "TAT CA OK" if fails == 0 else f"{fails} thu vien loi")
