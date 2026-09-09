# Roadmap đồ án

Ước lượng thời gian chỉ mang tính tham khảo, điều chỉnh theo deadline thực tế.

## Giai đoạn 1 — Dựng môi trường (xong)

- [x] `.venv` trong dự án + `pip install -r requirements/ml.txt` (torch CPU, flwr, nfstream, ...) — verify bằng `tests/test_ml_env.py`, tất cả OK
- [x] `libpcap-dev`
- [x] `mininet`, `iperf3`, `tcpdump`
- [x] OS-Ken (`os_ken`, `osken-manager`) cài hệ thống, chạy được `src/osken/simple_switch_13.py`
- [x] `hping3`

## Giai đoạn 2 — Trích xuất traffic (≈ 2 tuần)

Mục tiêu: có được pipeline thu thập flow-level features thực tế từ Mininet qua controller.

- [x] Clone `chiragbiradar/DDoS-Attack-Detection-and-Mitigation` để tham khảo (chỉ dùng để đọc code, không vendor vào repo — bản clone nằm ngoài dự án)
- [x] Chuyển phần code Ryu controller sang OS-Ken — `src/osken/simple_switch_13.py` (đã có sẵn từ trước) + `src/osken/flow_collector.py` (mới viết, port từ `collect_ddos_trafic.py`)
- [x] Tích hợp module Flow Collector vào controller: `FlowCollector` kế thừa `SimpleSwitch13`, override `packet_in_handler` để cài flow match theo 5-tuple IP/port (bản gốc chỉ match L2 nên không đủ để lấy flow-stats theo IP)
- [x] **Chạy thử thực tế** trong Mininet — đã chạy benign (pingall, full-mesh 132/132 cặp host) và attack (hping3 flood). Phát hiện + sửa 2 lỗi trong quá trình test (xem "Sự cố đã xử lý" bên dưới).
- [x] Chuẩn hóa output CSV: `flow_id, timestamp, datapath_id, ip_src, port_src, ip_dst, port_dst, ip_proto, icmp_code, icmp_type, duration_sec, duration_nsec, idle_timeout, hard_timeout, packet_count, byte_count, packet_count_per_second, byte_count_per_second, label`
- [x] Chốt bộ đặc trưng, đối chiếu CICDDoS2019 — xem [docs/feature_set.md](feature_set.md) (kèm giới hạn đã biết)

### Sự cố đã xử lý

1. **Chạy 2 mạng Mininet song song** (`topology.py` để CLI mở + `generate_traffic.py` tạo mạng riêng cùng tên host/switch) → lỗi `RTNETLINK answers: File exists`. Xử lý: chỉ dùng 1 mạng tại một thời điểm, gõ traffic trực tiếp vào `mininet>` CLI đang mở.
2. **Mỗi vùng có subnet `/24` riêng** (`10.0.{zone}.x`) trong khi mạng chỉ là 1 miền L2 (không router) → host khác vùng không có route tới nhau, `hping3`/`ping` chạy chéo vùng thất bại âm thầm qua `lo`. Xử lý: gộp về 1 subnet `10.0.0.0/24` chung cho toàn bộ 12 host ([topology.py](../src/emulation/topology.py)). Đã verify: `pingall` cho đủ 132/132 cặp src-dst.
3. **Flow entry không bao giờ hết hạn** (`add_flow()` không set `idle_timeout`/`hard_timeout`, mặc định OpenFlow = 0 = vĩnh viễn) → 2 hệ quả: (a) mỗi chu kỳ poll ghi lại toàn bộ flow còn sống → file CSV phình rất nhanh (phiên attack test đầu tiên: 848k dòng, 111 MB, chỉ ~13.5k flow duy nhất); (b) không `mn -c` giữa 2 phiên label khác nhau → flow benign cũ (ICMP) còn sống bị poll lại và gán nhầm nhãn "attack" (21,132 dòng bị nhiễm nhãn trong file `flow_stats_attack_20260909_134942.csv`). Xử lý: thêm `idle_timeout` (mặc định 20s, chỉnh qua env `FLOW_IDLE_TIMEOUT`) khi cài flow IP trong [flow_collector.py](../src/osken/flow_collector.py), truyền qua `add_flow()` đã mở rộng tham số trong [simple_switch_13.py](../src/osken/simple_switch_13.py). **File `flow_stats_attack_20260909_134942.csv` cũ nên xoá/không dùng để train vì bị nhiễm nhãn — chạy lại theo hướng dẫn bên dưới để có file sạch.**

### Cách chạy thử (3 terminal, cần sudo)

```bash
# Terminal 1 — controller + flow collector (label = loại traffic đang test)
cd src/osken
FLOW_LABEL=benign osken-manager --ofp-tcp-listen-port 6653 flow_collector.py

# Terminal 2 — dựng mạng 3 vùng (khớp config.yaml)
sudo python3 src/emulation/topology.py

# Terminal 3 (tuỳ chọn) — sinh traffic test thay vì gõ tay trong Mininet CLI
sudo python3 src/emulation/generate_traffic.py --mode benign   # cần cài xong mới chạy --mode attack/mixed (hping3)
```

Kết quả ghi vào `data/captures/flow_stats_<label>_<timestamp>.csv`.

**Quan trọng — giữa 2 phiên đổi nhãn (vd benign → attack): phải dọn sạch mạng và restart controller**, không chỉ đổi `FLOW_LABEL` rồi chạy tiếp trên mạng cũ, nếu không flow còn sống của phiên trước sẽ bị nhãn nhầm:

```bash
# Ở terminal đang mở mininet> CLI
mininet> exit
sudo mn -c

# Ctrl+C ở terminal 1 (dừng controller cũ), rồi chạy lại với label mới
cd src/osken
FLOW_LABEL=attack osken-manager --ofp-tcp-listen-port 6653 flow_collector.py

# Terminal 2 — dựng lại mạng
sudo python3 src/emulation/topology.py
```

## Giai đoạn 3 — So sánh FedAvg / FedProx / FedNova dưới Non-IID cho DDoS detection (≈ 2 tuần)

**Chốt hướng (2026-09-09, thay cho bản nháp ban đầu):** mục tiêu chính của luận văn ở
giai đoạn này là **so sánh FedAvg/FedProx/FedNova dưới điều kiện Non-IID cho bài toán
DDoS detection trong SDN** — không phải QoS 4-lớp như khung ban đầu (`config/qos_mapping.yaml`,
ISCX-VPN2016 vẫn giữ nguyên trong repo cho giai đoạn sau, hiện không active).

- **Dataset chính để train**: CICDDoS2019 — dùng **bản CSV đã trích đặc trưng sẵn qua
  CICFlowMeter** (mirror trên Kaggle, vd `dhoogla/cicddos2019`), không dùng route pcap +
  tshark/pyshark của FLAD/LUCID vì nặng và không cần thiết.
- **Dataset live validation**: CSV Mininet/hping3 tự sinh ở Giai đoạn 2
  (`data/captures/flow_stats_*.csv`) — chỉ để kiểm tra mô hình trên traffic thật tự tạo,
  không dùng để train chính.
- **Bài toán phân loại**: làm cả 2 bản — **binary** (benign/attack) làm trước, **multiclass**
  theo loại tấn công (benign + LDAP/MSSQL/NetBIOS/Portmap/Syn/UDP/UDPLag/WebDDoS) nâng cấp
  sau. Xem `config/config.yaml` mục `task.mode`.
- **Chiến lược FL**: FedAvg và FedProx có sẵn trong `flwr` (đã verify `flwr==1.34.0` có
  `flwr.server.strategy.FedProx`). **FedNova không có sẵn trong flwr — phải tự cài đặt
  custom `Strategy`.**

Repo đã có sẵn khung thư mục rỗng cho giai đoạn này (chỉ `__init__.py`): `src/preprocessing/`, `src/fl/`, `src/models/`, `src/baselines/`, `src/evaluation/`, và `data/splits/client_1|2|3/`.

- [x] Clone `flad-federated-learning-ddos` để tham khảo — đọc xong, **quyết định không dựng conda+TensorFlow riêng chỉ để sanity-check** (khác stack, tốn thời gian không cần thiết). Dùng `flad_main.py`/`ann_models.py` làm tham khảo thiết kế vòng lặp FL, viết thẳng bằng `flwr`+`torch`.
- [x] **Đã tải CICDDoS2019 từ Kaggle** (`dhoogla/cicddos2019`, dạng `.parquet` đã làm sạch) vào `data/raw/cicddos2019/` — 17 file, 431,371 dòng, 77 đặc trưng số, không còn cột IP/port/timestamp.
- [x] Viết [src/preprocessing/load_cicddos2019.py](../src/preprocessing/load_cicddos2019.py): đọc CSV/parquet CICFlowMeter, map `Label` về `task.mode` (binary/multiclass) — **đã chạy trên data thật**, phát hiện và sửa 2 lỗi so với thiết kế ban đầu (chỉ test bằng data giả lập trước đó): (1) data thật là `.parquet` không phải `.csv`, đã thêm hỗ trợ đọc cả 2; (2) nhãn không đồng nhất giữa các file ngày capture (`DrDoS_LDAP` vs `LDAP`, `UDP-lag` vs `UDPLag`) khiến cách so khớp substring cũ nhầm `UDP-lag` thành lớp `udp` — viết lại bằng `_normalize_label()` so khớp chính xác.
- [x] Viết [src/preprocessing/split_noniid.py](../src/preprocessing/split_noniid.py): chuẩn hoá đặc trưng (`StandardScaler`, lưu `data/processed/scaler_<mode>.joblib`), chia dữ liệu cho 3 client theo label-skew trong `config/noniid_distribution.yaml` (viết lại theo loại tấn công CICDDoS2019, bản QoS cũ lưu ở `noniid_distribution_qos_legacy.yaml`), ghi ra `data/splits/client_{1,2,3}/{train,val,test}.csv`. **Sửa 1 lỗi thiết kế phát hiện khi chạy trên data thật**: thuật toán chia tuần tự theo thứ tự client trong YAML làm client xử lý sau cùng bị vét sạch khi thiếu dữ liệu (benign khan hiếm so với attack trong CICDDoS2019 — client_3 lẽ ra 70% benign nhưng ban đầu nhận được 0%) → sửa để chia sẻ phần thiếu hụt theo tỉ lệ nhu cầu, giữ đúng thứ tự tương đối giữa các client.
- [x] Cài mô hình `cnn1d` trong [src/models/cnn1d.py](../src/models/cnn1d.py), tham số hoá theo `config.yaml` (`model.*`, `task.<mode>.num_classes`) — đã test forward pass.
- [x] Cài FL client trong [src/fl/client.py](../src/fl/client.py) (`flwr.client.NumPyClient`, dùng chung cho cả 3 strategy; tự thêm proximal term khi server gửi `proximal_mu` — đúng cơ chế FedProx của flwr; luôn trả `tau` = số local step đã chạy để FedNova dùng khi aggregate)
- [x] Cài FL server trong [src/fl/server.py](../src/fl/server.py) + [src/fl/fednova_strategy.py](../src/fl/fednova_strategy.py) (custom, kế thừa `FedAvg`, tự implement công thức chuẩn hoá theo `tau_i`). **Sửa 1 lỗi phát hiện khi chạy trên data thật**: server dùng `input_dim=30` (placeholder trong config) để dựng model ban đầu trong khi data thật có 77 cột → sai shape khi gộp tham số FL → thêm `infer_input_dim()` trong `dataset.py` để tự đọc số cột thật từ file đã chia.
- [x] **Đã chạy thật trên CICDDoS2019 (431,371 dòng, mode binary)** cho cả 3 strategy — loss giảm ổn định (0.024→0.016 chỉ sau 2 round/1 epoch), accuracy ~99.6-99.7%, không lỗi. Xác nhận pipeline train end-to-end hoạt động đúng trên dữ liệu thật (không chỉ dữ liệu giả lập).
- [ ] Train một mô hình centralized (gộp toàn bộ dữ liệu, không chia client) làm mốc so sánh — trong `src/baselines/` (chưa viết)
- [ ] Chạy live validation: nạp `data/captures/flow_stats_*.csv` (Giai đoạn 2) vào model đã train, xem độ chệch so với test set CICDDoS2019 (chưa viết — cần dùng lại đúng `scaler_binary.joblib` đã lưu để scale CSV Mininet nhất quán với lúc train)
- [ ] Vẽ đồ thị: FedAvg vs FedProx vs FedNova vs Centralized theo accuracy/round, và communication overhead (chưa viết, trong `src/evaluation/`)
- [ ] **Mode multiclass**: bản Kaggle có thêm 4 loại tấn công (DNS, NTP, SNMP, TFTP) không nằm trong 9 lớp đã cấu hình ở `config.yaml` → hiện ~226,671/431,371 dòng (52%) bị loại khi chạy multiclass. Cần quyết định: mở rộng danh sách lớp lên 13 hay giữ 9 lớp và chấp nhận bỏ bớt data.
- [ ] Chạy training thật với `fl.num_rounds`/`local_epochs` đầy đủ theo `config.yaml` (mới chỉ verify bằng 2 round/1 epoch để bắt lỗi nhanh) và lưu kết quả chính thức vào `results/`

### Việc cần cài thêm

- `pip install "flwr[simulation]"` (kéo theo `ray`) — bắt buộc để chạy `src/fl/server.py`, đã thêm vào `requirements/ml.txt`.
- `pip install pyarrow` — bắt buộc để đọc `.parquet`, **chưa có trong `requirements/ml.txt`, cần thêm**.

### Cảnh báo đã biết (không chặn tiến độ)

- `client_fn(cid)` trong `src/fl/client.py`/`server.py` dùng API cũ của flwr (`cid` thay vì `Context`) — flwr 1.34.0 báo `DEPRECATED FEATURE`, vẫn chạy được nhưng sẽ bị gỡ ở bản sau. Cần migrate sang API `Context` khi nâng cấp flwr.
- Ray ghi cảnh báo dung lượng `/tmp` gần đầy trong lúc chạy simulation — theo dõi khi train với dữ liệu CICDDoS2019 thật (nặng hơn nhiều so với data giả lập).

### Tải CICDDoS2019 (Kaggle)

```bash
# Cai kaggle CLI (trong .venv), can kaggle.json (Account -> Create New Token tren kaggle.com)
pip install kaggle
mkdir -p ~/.kaggle && mv ~/Downloads/kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json

mkdir -p data/raw/cicddos2019
kaggle datasets download -d dhoogla/cicddos2019 -p data/raw/cicddos2019 --unzip
```

### Điểm kiểm tra tiến độ

Nếu FedAvg/FedProx/FedNova đều hội tụ và có accuracy gần với centralized (chênh lệch nhỏ), đồng thời thấy được sự khác biệt hợp lý giữa 3 chiến lược dưới Non-IID (vd FedProx/FedNova ổn định hơn FedAvg khi mức độ lệch dữ liệu tăng) → pipeline ổn, có thể tự tin bước sang Giai đoạn 4.
