"""CNN 1D don gian cho phan loai flow-level features (CICDDoS2019).
Input: vector dac trung so (input_dim), duoc coi nhu 1 "tin hieu" 1 chieu.
Kien truc: 2 khoi Conv1d+ReLU+MaxPool -> flatten -> FC -> output num_classes.
"""
import torch
import torch.nn as nn


class CNN1D(nn.Module):
    def __init__(self, input_dim, num_classes, hidden_dim=128, dropout=0.3):
        super().__init__()
        self.input_dim = input_dim

        self.conv1 = nn.Conv1d(in_channels=1, out_channels=32, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(in_channels=32, out_channels=64, kernel_size=3, padding=1)
        self.pool = nn.MaxPool1d(kernel_size=2)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(dropout)

        conv_out_len = input_dim // 2 // 2
        conv_out_len = max(conv_out_len, 1)
        self.flatten_dim = 64 * conv_out_len

        self.fc1 = nn.Linear(self.flatten_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        # x: (batch, input_dim) -> (batch, 1, input_dim)
        x = x.unsqueeze(1)
        x = self.pool(self.relu(self.conv1(x)))
        x = self.pool(self.relu(self.conv2(x)))
        x = x.flatten(start_dim=1)
        if x.shape[1] != self.flatten_dim:
            # input_dim qua nho de pool 2 lan, dung adaptive pool de khop kich thuoc
            x = nn.functional.adaptive_avg_pool1d(x.unsqueeze(1), self.flatten_dim).squeeze(1)
        x = self.dropout(self.relu(self.fc1(x)))
        return self.fc2(x)


def build_model(cfg):
    model_cfg = cfg["model"]
    mode = cfg["task"]["mode"]
    num_classes = cfg["task"][mode]["num_classes"]
    return CNN1D(
        input_dim=model_cfg["input_dim"],
        num_classes=num_classes,
        hidden_dim=model_cfg["hidden_dim"],
        dropout=model_cfg["dropout"],
    )


if __name__ == "__main__":
    m = CNN1D(input_dim=30, num_classes=2)
    x = torch.randn(8, 30)
    out = m(x)
    print("output shape:", out.shape)
    assert out.shape == (8, 2)
    print("OK")
