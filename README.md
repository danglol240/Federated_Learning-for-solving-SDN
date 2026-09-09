# Đồ án: Tích hợp Federated Learning vào mạng SDN

Phân loại lưu lượng mạng theo 4 nhóm QoS bằng Federated Learning
trong môi trường SDN đa vùng.

## Môi trường

| Thành phần | Công cụ | Cách chạy |
|---|---|---|
| SDN Controller | OS-Ken (bản hệ thống) | không cần venv |
| Machine Learning | PyTorch + Flower | `source .venv/bin/activate` |

## Cài đặt

```bash
# SDN (qua apt)
sudo apt install -y mininet iperf3 hping3 tcpdump libpcap-dev

# ML (venv trong dự án)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements/ml.txt
```

## Chạy thử

```bash
# Terminal 1 — controller
osken-manager --ofp-tcp-listen-port 6653 src/osken/simple_switch_13.py

# Terminal 2 — mạng
sudo mn --controller=remote,ip=127.0.0.1,port=6653 \
        --topo=tree,depth=2,fanout=2 \
        --switch=ovsk,protocols=OpenFlow13
```

## Cấu trúc

- `config/` — tham số tập trung, sửa ở đây thay vì hardcode trong code
- `data/` — raw → interim → processed → splits
- `src/emulation/` — script Mininet (KHÔNG đặt tên `mininet` để tránh shadow thư viện)
- `src/osken/` — ứng dụng SDN controller
- `src/fl/` — Flower client & server
- `src/baselines/` — Centralized và Local-only để so sánh
- `results/` — hình, bảng, log

## Tài liệu

Xem `docs/` cho tài liệu từng giai đoạn.
