# Bo dac trung flow-level (Giai doan 2)

Duoc trich xuat boi `src/osken/flow_collector.py` tu `OFPFlowStatsReply` cua
OpenFlow 1.3. Doi chieu voi CICDDoS2019 de de ket hop neu traffic tu sinh
trong Mininet khong du da dang.

| Cot CSV | Nguon OpenFlow | Tuong duong CICDDoS2019 |
|---|---|---|
| `flow_id` | ghep `ip_src-port_src-ip_dst-port_dst-proto` | (khong co san, tu dat) |
| `ip_src`, `ip_dst` | `match.ipv4_src/dst` | Source/Destination IP |
| `port_src`, `port_dst` | `match.tcp_src/dst` hoac `udp_src/dst` | Source/Destination Port |
| `ip_proto` | `match.ip_proto` | Protocol |
| `icmp_code`, `icmp_type` | `match.icmpv4_code/type` | (rieng cho ICMP, CICDDoS2019 khong tach) |
| `duration_sec`, `duration_nsec` | `stat.duration_sec/nsec` | Flow Duration |
| `packet_count` | `stat.packet_count` | Total Fwd Packets (xap xi) |
| `byte_count` | `stat.byte_count` | Total Length of Fwd Packets (xap xi) |
| `packet_count_per_second` | tinh tu packet_count/duration | Flow Packets/s |
| `byte_count_per_second` | tinh tu byte_count/duration | Flow Bytes/s |
| `idle_timeout`, `hard_timeout` | `stat.idle_timeout/hard_timeout` | (dac thu OpenFlow, khong co trong CICDDoS2019) |
| `label` | gan boi nguoi van hanh khi chay collector (`FLOW_LABEL=...`) | Label |

## Gioi han da biet

- OpenFlow flow stats la theo **huong** cua match (ipv4_src -> ipv4_dst), khac
  voi CICDDoS2019 tach rieng Fwd/Bwd cho 1 flow 2 chieu. Muon co ca 2 huong
  can hoi 2 flow entry (A->B va B->A) roi ghep lai o buoc tien xu ly.
- Khong co cac dac trung thong ke chi tiet (IAT mean/std, packet length
  std, so luong TCP flags...) vi OpenFlow khong bao cao o muc do nay. Neu can,
  phai tinh them o tang packet-level (vd bang NFStream) thay vi flow-stats.
- Bo dac trung nay dung de **kiem tra pipeline thu thap** (Giai doan 2). Du
  lieu huan luyen chinh cho bai toan QoS van la ISCX-VPN2016 xu ly qua
  NFStream (xem `config/config.yaml`, `config/qos_mapping.yaml`).
- `packet_count_per_second`/`byte_count_per_second` la **trung binh cong don
  tu luc flow duoc cai** (`packet_count`/`duration_sec` cua OpenFlow la bo
  dem cong don, khong reset giua cac lan poll), khong phai toc do tuc thoi
  trong khoang `FLOW_STATS_INTERVAL` gan nhat. Voi flow bi poll nhieu lan,
  cac dong sau se cho gia tri "muot" dan chu khong phan anh dot bien tuc thoi.
- Truoc ban vá `idle_timeout` (xem ROADMAP.md), flow entry khong bao gio het
  han (`idle_timeout=hard_timeout=0`) nen bi poll lai vinh vien va giu nguyen
  flow tu phien nhan truoc neu khong `mn -c` giua 2 lan test -> co the gay
  nham nhan. Tu ban vá: flow IP se tu dong het han sau
  `FLOW_IDLE_TIMEOUT` giay (mac dinh 20s) khong hoat dong.
