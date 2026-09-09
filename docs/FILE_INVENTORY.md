# Danh sách file đã thêm/sửa — tự viết vs tham khảo bên ngoài

Cập nhật lần cuối: 2026-09-09 (sau khi test bằng CICDDoS2019 thật).

## A. Giai đoạn 3 — FL (FedAvg/FedProx/FedNova so sánh dưới Non-IID)

| File | Nội dung | Nguồn |
|---|---|---|
| [src/preprocessing/load_cicddos2019.py](../src/preprocessing/load_cicddos2019.py) | Đọc CICDDoS2019 (`.csv` hoặc `.parquet`), chuẩn hoá tên cột, xử lý Inf/NaN, map nhãn → binary/multiclass. Có `_normalize_label()` để tránh nhầm nhãn kiểu `UDP-lag` thành lớp `udp` | Tự viết |
| [src/preprocessing/split_noniid.py](../src/preprocessing/split_noniid.py) | Chuẩn hoá đặc trưng (`StandardScaler`, lưu ra `data/processed/scaler_<mode>.joblib`), chia dữ liệu 3 client theo label-skew trong `noniid_distribution.yaml`, chia deu ti le khi thiếu dữ liệu toàn cục thay vì vét theo thứ tự client | Tự viết |
| [src/models/cnn1d.py](../src/models/cnn1d.py) | Model CNN 1D (2 conv + FC), tự tham số hoá theo `input_dim`/`num_classes` | Tự thiết kế |
| [src/fl/dataset.py](../src/fl/dataset.py) | CSV client → `torch.DataLoader`, `infer_input_dim()` đọc số cột thật từ file đã chia (không phụ thuộc placeholder trong config) | Tự viết |
| [src/fl/client.py](../src/fl/client.py) | `flwr.client.NumPyClient` dùng chung cho cả 3 strategy — tự thêm proximal term khi server gửi `proximal_mu` (cơ chế FedProx), luôn trả `tau` (số local step) cho FedNova | Dùng API chuẩn của thư viện `flwr`, phần logic train/eval tự viết |
| [src/fl/server.py](../src/fl/server.py) | Chọn strategy theo config, chạy `flwr.simulation.start_simulation`, ghi log CSV mỗi round | Tự viết |
| [src/fl/fednova_strategy.py](../src/fl/fednova_strategy.py) | Custom `Strategy` (kế thừa `FedAvg`), cài đặt công thức FedNova (chuẩn hoá theo `tau_i`) | **Tự cài đặt từ công thức trong paper gốc** Wang et al. 2020 — `flwr` không có sẵn FedNova, repo tham khảo FLAD cũng không implement, nên không có code nào để copy |
| `config/config.yaml` | Sửa: dataset=CICDDoS2019, `task.mode` (binary/multiclass), `fl.strategy` thêm `fednova` | Tự sửa từ bản gốc có sẵn |
| `config/noniid_distribution.yaml` | Viết lại theo loại tấn công CICDDoS2019 (label-skew), có khối `binary` và `multiclass` riêng | Tự viết lại (bản QoS cũ lưu ở `noniid_distribution_qos_legacy.yaml`) |
| `requirements/ml.txt` | Thêm `flwr[simulation]` (cần `ray` để chạy simulation) | Tự thêm |

## B. Giai đoạn 2 — Thu thập traffic SDN (viết ở phiên trước)

| File | Nội dung |
|---|---|
| [src/osken/flow_collector.py](../src/osken/flow_collector.py) | App OS-Ken thu flow-stats, ghi CSV |
| [src/emulation/topology.py](../src/emulation/topology.py) | Topology Mininet 3 vùng |
| [src/emulation/generate_traffic.py](../src/emulation/generate_traffic.py) | Sinh traffic benign/attack test |
| [docs/feature_set.md](feature_set.md) | Tài liệu bộ đặc trưng |
| [tests/test_ml_env.py](../tests/test_ml_env.py) | Test môi trường ML |

## C. Đã có sẵn trong scaffold ban đầu (không phải mình viết)

`README.md`, `config/qos_mapping.yaml`, `requirements/sdn.txt`, [src/osken/simple_switch_13.py](../src/osken/simple_switch_13.py) (switch L2 cơ bản, có sẵn từ trước khi mình tham gia dự án), toàn bộ cấu trúc thư mục rỗng (`__init__.py`, `.gitkeep`).

## D. Chỉ tham khảo (đọc code để lấy ý tưởng) — KHÔNG nằm trong repo

Cả 2 repo dưới đây được `git clone` tạm vào `/tmp` để đọc, rồi xoá ngay sau đó — không có dòng code nào copy trực tiếp vào project.

- `chiragbiradar/DDoS-Attack-Detection-and-Mitigation` — tham khảo cách port Ryu→OS-Ken cho `flow_collector.py` (Giai đoạn 2)
- `doriguzzi/flad-federated-learning-ddos` — tham khảo thiết kế vòng lặp FL (Giai đoạn 3). Repo này dùng TensorFlow/Keras (khác `flwr`+`torch` của dự án) nên chỉ tham khảo ý tưởng, không copy được code.

## E. Dữ liệu — nguồn và trạng thái xử lý

- **CICDDoS2019**: tải từ Kaggle (`dhoogla/cicddos2019`, dạng `.parquet` đã làm sạch, 77 đặc trưng số, không còn cột IP/port/timestamp) vào `data/raw/cicddos2019/` — **do bạn tự tải**, không phải mình tạo ra.
- Sau khi tải, đã phát hiện và sửa 4 vấn đề trong code xử lý (chưa lường trước vì lúc viết chưa có data thật):
  1. Code chỉ đọc `.csv`, data thật là `.parquet` → thêm hỗ trợ đọc cả 2.
  2. Nhãn không đồng nhất giữa các file (`DrDoS_LDAP` vs `LDAP`, `UDP-lag` vs `UDPLag`) → so khớp bằng substring cũ làm `UDP-lag` bị nhầm thành lớp `udp` → viết `_normalize_label()` so khớp chính xác.
  3. `server.py` dùng `input_dim=30` (placeholder trong config) để dựng model ban đầu, trong khi data thật có 77 cột → sai shape khi gộp tham số FL → sửa để tự đọc số cột thật từ file đã chia (`infer_input_dim()`).
  4. Thuật toán chia non-IID xử lý tuần tự theo thứ tự client trong YAML — khi thiếu dữ liệu (benign khan hiếm so với attack trong CICDDoS2019), client xử lý sau cùng bị vét sạch, phá vỡ tỉ lệ đã thiết kế → sửa để chia sẻ phần thiếu hụt theo tỉ lệ nhu cầu của từng client.
  5. Chưa chuẩn hoá đặc trưng (StandardScaler) trước khi train → loss ban đầu rất lớn (round 1: ~2252) → thêm bước scale, lưu lại scaler để dùng nhất quán sau này.
- Sau khi sửa: đã chạy thật `split_noniid.py` + `server.py` cho cả 3 strategy (FedAvg/FedProx/FedNova) trên 431,371 dòng dữ liệu thật, mode binary — loss giảm ổn định (0.024→0.016), accuracy ~99.6-99.7% chỉ sau 2 round/1 epoch. Xem chi tiết trong [docs/ROADMAP.md](ROADMAP.md).
- **Ghi chú riêng cho mode multiclass**: bản Kaggle này có thêm 4 loại tấn công (DNS, NTP, SNMP, TFTP) không nằm trong 9 lớp đã cấu hình ở `config.yaml` → khi chạy multiclass, ~226,671/431,371 dòng (52%) bị loại vì không khớp. Chưa xử lý — cần quyết định mở rộng danh sách lớp hay giữ nguyên 9 lớp.
