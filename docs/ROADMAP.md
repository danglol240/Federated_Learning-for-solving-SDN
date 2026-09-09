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
