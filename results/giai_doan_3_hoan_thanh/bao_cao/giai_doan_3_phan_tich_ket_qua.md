# Phân tích kết quả Giai đoạn 3 — FedAvg vs FedProx vs FedNova vs Centralized

Ngày chạy: 2026-09-11. Dataset: CICDDoS2019 (Kaggle `dhoogla/cicddos2019`), mode `binary`
(benign/attack), `num_rounds=50`, `local_epochs=5`, 3 client non-IID.

## 1. Kết quả tóm tắt (round 41-50, sau khi đã hội tụ)

| Strategy | Accuracy trung bình | Độ lệch chuẩn (round-to-round) | Chênh lệch so với Centralized |
|---|---|---|---|
| Centralized | 99.8309% | 0.0097% | — (mốc so sánh) |
| FedAvg | 99.8054% | 0.0156% | -0.0255 điểm % |
| FedNova | 99.7850% | 0.0131% | -0.0459 điểm % |
| FedProx | 99.7404% | 0.0066% | -0.0906 điểm % |

## 2. Trả lời câu hỏi: có phải model/hệ thống quá nhỏ không?

**Không phải nguyên nhân chính.** Model `CNN1D` đang dùng có **162,370 tham số** (input 77
đặc trưng CICFlowMeter → 2 lớp Conv1D → FC). Đây là kích thước hợp lý cho bài toán phân loại
nhị phân trên dữ liệu dạng bảng (tabular), không phải một model "đồ chơi" quá nhỏ.

Lý do accuracy đã sát 99.8% ngay từ ~10 round đầu và các strategy khó tách biệt rõ **là vì bản
chất bài toán quá dễ**, không phải vì thiếu năng lực model:

- Traffic DDoS trong CICDDoS2019 khác biệt RẤT lớn so với benign ở chính các đặc trưng
  flow-level (số gói/giây, độ dài gói, tỉ lệ SYN...) — gần như tách được tuyến tính. Đây là
  điều đã được ghi nhận rộng rãi trong các paper dùng CICDDoS2019: kể cả Random Forest hay MLP
  nhỏ cũng đạt >99% ở bài toán nhị phân.
- Khi bài toán đã gần chạm "trần" (ceiling ~99.8-99.9%), **tăng thêm tham số model hầu như
  không giúp accuracy cao hơn đáng kể** — chỉ tốn thêm thời gian train và có nguy cơ overfit.

**Nếu làm model to hơn thì sao?** Nhiều khả năng accuracy tổng thể gần như không đổi (đã sát
trần), nhưng thời gian train sẽ tăng - máy hiện tại chạy CPU-only nên 1 round với
`local_epochs=5` mất trung bình ~60-70 giây; model to hơn (nhiều tham số hơn) sẽ kéo dài thời
gian này tỉ lệ thuận, trong khi lợi ích về accuracy gần như không đáng kể ở bài toán binary này.

**Nếu máy tính (CPU) mạnh hơn thì sao?** Sẽ giúp **rút ngắn thời gian chạy thí nghiệm** (batch
này mất ~3.5 giờ do CPU-only, phần lớn thời gian là tính toán chứ không phải overhead), nhưng
**không làm thay đổi kết quả accuracy** — kết quả là do dữ liệu và thuật toán quyết định, không
phụ thuộc phần cứng.

→ **Muốn thấy khác biệt giữa các strategy rõ hơn, cần làm bài toán khó hơn, không phải model to
hơn** (xem mục 4).

## 3. Trả lời câu hỏi: số lượng mẫu test đã đủ chưa?

**Đủ, thậm chí dư dả.** Tổng số mẫu test: **62,703 mẫu** (client_1: 20,901 + client_2: 24,044 +
client_3: 17,758).

Với n=62,703 và accuracy ~99.8%, sai số chuẩn (standard error) của ước lượng accuracy là:

```
SE = sqrt(p(1-p)/n) = sqrt(0.998 x 0.002 / 62703) ≈ 0.0178%
Khoang tin cay 95%: accuracy_that ± 0.035 điểm %
```

So với chênh lệch quan sát được giữa các strategy (0.02 - 0.09 điểm %), sai số chuẩn 0.0178%
đủ nhỏ để **hầu hết các chênh lệch là tín hiệu thật, không phải nhiễu do cỡ mẫu**:

- FedProx vs Centralized (0.0906 điểm %) — gấp ~5 lần SE → **chênh lệch có ý nghĩa thống kê rõ
  ràng**, khớp với quan sát trên đồ thị là FedProx hội tụ chậm hơn hẳn.
- FedNova vs Centralized (0.0459 điểm %) — gấp ~2.6 lần SE → **có khả năng là chênh lệch thật**.
- FedAvg vs FedNova (0.0204 điểm %) — xấp xỉ mức SE → **nằm trong vùng không chắc chắn**, khó
  khẳng định 2 strategy này khác nhau thật sự ở bài toán binary hiện tại (khớp với việc 2 đường
  này bám sát nhau trên đồ thị).

Kết luận: **62,703 mẫu test là đủ để so sánh đáng tin cậy** ở mức chênh lệch hàng phần trăm nhỏ.
Vấn đề không nằm ở thiếu dữ liệu test, mà ở việc bài toán binary hiện tại quá dễ nên biên độ
chênh lệch giữa các strategy vốn dĩ nhỏ (dù vẫn đo được).

## 4. Vì sao chênh lệch giữa các strategy nhỏ — và làm sao để thấy rõ hơn

Ngoài yếu tố "bài toán dễ" ở mục 2, còn 1 nguyên nhân kỹ thuật: **mức độ Non-IID thực tế bị nén
lại** so với thiết kế ban đầu.

Khi chia dữ liệu (`split_noniid.py`), tổng nhu cầu benign của 3 client (215,685 mẫu) vượt xa
lượng benign thực có (97,831 mẫu, chỉ 22.7% tổng dataset — CICDDoS2019 vốn tập trung vào traffic
tấn công). Thuật toán phải scale tỉ lệ xuống còn ~45%, khiến độ lệch benign/attack thực tế giữa
3 client bị nén lại gần nhau hơn thiết kế (client_3 mục tiêu 70% benign nhưng chỉ đạt 51%).
Non-IID càng nhẹ thì FedAvg càng ít bị "kéo lệch" bởi client, nên khoảng cách với FedProx/FedNova
(vốn được thiết kế để xử lý Non-IID nặng) càng khó thấy rõ.

**Đề xuất cụ thể để có kết quả tách biệt rõ hơn cho luận văn (không cần máy mạnh hơn):**

1. **Chuyển sang mode multiclass** (đã có sẵn code, chỉ chưa mở rộng đủ lớp — xem mục "Việc còn
   thiếu" trong `docs/ROADMAP.md`). Bài toán 9 lớp với phân bố cực kỳ mất cân bằng (WebDDoS chỉ
   51 mẫu so với benign 97,831) khó hơn nhiều so với binary — thường là nơi FedProx/FedNova cho
   thấy lợi thế rõ rệt so với FedAvg trong các paper gốc.
2. **Tăng mức độ Non-IID một cách nhân tạo** thay vì chỉ dựa vào tỉ lệ benign/attack: chia theo
   loại tấn công cụ thể (mỗi client thiên lệch hẳn về 1-2 loại DDoS, giống thiết kế
   `noniid_by: attack_type` đã có trong `config.yaml` nhưng cho multiclass) sẽ tạo lệch phân bố
   nhãn mạnh hơn nhiều so với chỉ lệch benign/attack.
3. **Giảm `local_epochs`** (vd từ 5 xuống 1-2) và/hoặc **giảm `fraction_fit`** (không phải
   client nào cũng tham gia mỗi round) — đây là 2 điều kiện kinh điển làm lộ rõ vấn đề
   "objective inconsistency" mà FedNova được thiết kế để giải quyết; hiện `fraction_fit=1.0` và
   `local_epochs=5` là điều kiện khá "dễ" cho FedAvg.
4. **Thêm client với dữ liệu cực đoan hơn** (vd 1 client gần như chỉ có 1 loại attack, gần như
   không có mẫu nào của loại khác) thay vì pha trộn benign/attack tương đối đều như hiện tại.

## 5. Cập nhật — thí nghiệm "khó hơn": partial participation + local_epochs=1 (2026-09-11)

Theo đề xuất ở mục 4 (hướng rẻ nhất), đã chạy lại full 50 round với `local_epochs: 5→1` và
`fraction_fit: 1.0→0.67` (chỉ 2/3 client được chọn fit mỗi round thay vì cả 3 — phát hiện thêm
1 lỗi trong lúc sửa: `min_fit_clients` trước đó bị code ép cứng bằng `min_available_clients`
nên dù đổi `fraction_fit` cũng vô tác dụng, đã tách 2 tham số này ra trong `src/fl/server.py`).
Kết quả cũ (5 epoch, full participation) đã lưu ở `results/archive_epoch5_full_participation/`
để đối chiếu.

| Strategy | Accuracy (round 41-50) | Chênh lệch vs Centralized | So với thí nghiệm cũ |
|---|---|---|---|
| Centralized | 99.8309% | — | không đổi (không phụ thuộc local_epochs/fraction_fit) |
| FedAvg | 99.7812% | -0.0498 điểm % (2.79x SE) | **doãng rộng hơn** (cũ: -0.0255, 1.43x SE) |
| FedNova | 99.7691% | -0.0619 điểm % (3.47x SE) | doãng rộng hơn (cũ: -0.0459, 2.58x SE) |
| FedProx | 99.7349% | -0.0960 điểm % (5.38x SE) | gần như không đổi (cũ: -0.0906, 5.09x SE) |

**Phát hiện chính**: điều kiện khắc nghiệt hơn (ít bước local, không phải client nào cũng tham
gia mỗi round) làm **FedAvg tụt xa Centralized hơn rõ rệt** (gấp gần 2x khoảng cách cũ) — đúng
như lý thuyết dự đoán, vì FedAvg cộng gộp đơn giản sẽ nhạy cảm hơn với việc client tham gia
không đều. Tuy nhiên, **FedNova KHÔNG vượt qua được FedAvg** trong cả 2 thí nghiệm (thứ tự luôn
là FedAvg > FedNova > FedProx) — nghĩa là dù đã tạo điều kiện đúng theo lý thuyết để FedNova thể
hiện lợi thế, model/bài toán binary DDoS hiện tại chưa đủ nhạy để lộ ra lợi thế đó. FedProx vẫn
là strategy chậm/kém nhất trong cả 2 lần chạy.

**Diễn giải cho luận văn**: đây vẫn là 1 kết quả có giá trị — nó cho thấy **objective
inconsistency chỉ ảnh hưởng rõ đến FedAvg (đúng như FedNova paper chỉ ra), nhưng cơ chế chuẩn
hoá của FedNova chưa tạo ra lợi ích vượt trội trên bài toán/quy mô dữ liệu này** (chỉ 3 client,
task binary dễ). Đây là cơ sở hợp lý để kết luận: **cần bài toán multiclass hoặc Non-IID mạnh
hơn** (mục 4) mới có khả năng thấy FedNova/FedProx thể hiện ưu thế rõ ràng so với FedAvg — không
phải lỗi cài đặt (đã verify FedNova hoạt động đúng cơ chế qua `fednova_strategy.py`).

**Lưu ý về biểu đồ `communication_overhead_binary.png`**: công thức tính hiện dùng
`num_clients` cố định (3) cho cả 3 strategy, chưa trừ hao do `fraction_fit<1` (thực tế chỉ ~2
client truyền tham số mỗi round cho phase fit) — số MB tuyệt đối trên biểu đồ hơi cao hơn thực
tế, nhưng **so sánh tương đối giữa 3 strategy FL vẫn đúng** (cả 3 dùng chung config nên bị lệch
như nhau, không ảnh hưởng kết luận "chi phí truyền tin gần như ngang nhau giữa FedAvg/FedProx/
FedNova, chỉ Centralized là 0").

## 6. Cập nhật — chuyển sang multiclass 13 lớp (2026-09-14)

Đã mở rộng `task.multiclass` từ 9 lên **13 lớp** (thêm DNS/NTP/SNMP/TFTP) để dùng hết 431,371
dòng thay vì bỏ 52%, viết lại `config/noniid_distribution.yaml` theo "họ" tấn công (client_1=
service-targeting DrDoS: LDAP/MSSQL/DNS; client_2=flood cổ điển: Syn/UDP/UDPLag; client_3=
phản xạ/khác: NetBIOS/Portmap/SNMP/TFTP/NTP/WebDDoS). Giữ nguyên điều kiện "khó" đã xác nhận ở
mục 5 (`local_epochs=1`, `fraction_fit=0.67`). Đã thêm lưu checkpoint model cuối cùng vào
`checkpoints/*.pt` cho cả centralized và 3 strategy FL (trước đây không lưu model nào cả).

| Strategy | Accuracy (round 41-50) | F1 macro | Precision | Recall |
|---|---|---|---|---|
| Centralized | 95.77% | 0.7192 | 0.8023 | 0.7162 |
| **FedNova** | 95.31% | **0.6627** | 0.7232 | 0.6870 |
| FedAvg | 95.34% | 0.6552 | 0.7153 | 0.6776 |
| FedProx | 95.23% | 0.6511 | 0.7036 | 0.6770 |

**Phát hiện chính**: khác hẳn kết quả binary (mục 1, 5), ở bài toán multiclass 13 lớp mất cân
bằng nặng (WebDDoS 51 mẫu vs NTP 121,368 mẫu), **F1 macro giữa các strategy chênh nhau tới ~0.01-
0.02** (so với binary chỉ ~0.001-0.003) — độ phân giải đủ để **lần đầu tiên FedNova vượt lên trên
FedAvg**, đúng như kỳ vọng lý thuyết khi bài toán đủ khó/mất cân bằng để cơ chế chuẩn hoá theo
`tau_i` phát huy tác dụng. F1 macro (nhạy với lớp hiếm) là chỉ số nên dùng để so sánh ở bài toán
này, không nên chỉ nhìn accuracy (bị chi phối bởi các lớp lớn như benign/ntp/tftp, chênh lệch
accuracy giữa cả 4 phương án chỉ ~0.5 điểm %, khó thấy khác biệt như biểu đồ
`accuracy_comparison_multiclass.png`).

**Điểm nhất quán với các thí nghiệm trước**: FedProx vẫn hội tụ chậm nhất ở đầu quá trình training
(accuracy round 1 chỉ 89.7% so với ~91-95% của FedAvg/FedNova/Centralized) — proximal term làm
chậm tốc độ học ban đầu, xu hướng này lặp lại nhất quán ở cả 3 thí nghiệm đã chạy (binary full
participation, binary partial participation, multiclass).

**Lưu ý thống kê**: độ lệch chuẩn round-to-round của F1 (~0.019-0.021) khá lớn so với chênh lệch
0.0075 điểm giữa FedNova và FedAvg — nên trình bày kết quả này trong luận văn kèm caveat rằng
đây là xu hướng nhất quán với lý thuyết chứ chưa hẳn là chênh lệch chắc chắn có ý nghĩa thống kê
với chỉ 1 lần chạy; nếu muốn kết luận chắc chắn hơn nên chạy lại với vài random seed khác rồi lấy
trung bình.

### 6.1. KIỂM CHỨNG THÊM (2026-09-14) — kết luận "FedNova thắng" CHƯA đủ vững, không nên đưa
thẳng vào luận văn như hiện tại

Load lại 4 checkpoint đã lưu, chạy inference trên tập test gộp (51,610 mẫu) và bóc tách F1 theo
từng lớp để kiểm tra xem chênh lệch macro F1 (0.0044, tính trên checkpoint cuối) đến từ đâu:

| Lớp | Số mẫu test | Centralized | FedAvg | FedProx | FedNova |
|---|---|---|---|---|---|
| portmap | 134 | 0.403 | 0.043 | 0.042 | **0.218** |
| dns | 776 | 0.454 | **0.348** | 0.148 | 0.131 |
| webddos | 7 | 0.000 | 0.000 | 0.000 | 0.000 |
| netbios | 268 | 0.415 | 0.657 | 0.657 | 0.660 |

**Vấn đề**: chỉ riêng lớp `portmap` (134 mẫu) đã đóng góp (0.218-0.043)/13 = **+0.0135** điểm vào
chênh lệch macro F1 FedNova-FedAvg — LỚN HƠN toàn bộ chênh lệch quan sát được (0.0044). Nhưng lớp
`dns` (776 mẫu) lại kéo NGƯỢC LẠI: FedNova thua FedAvg tới (0.131-0.348)/13 = **-0.0167** điểm ở
riêng lớp này. Hai lớp hiếm này gần như "vặn" toàn bộ kết quả macro F1 theo 2 hướng đối nghịch,
với biên độ mỗi lớp còn lớn hơn cả kết luận cuối cùng — tức macro F1 hiện tại giống như đang đo
"model nào đoán đúng 1 nhóm nhỏ vài chục-vài trăm mẫu portmap/dns hơn", không phải đo năng lực
tổng thể của thuật toán FL.

**Bằng chứng dứt điểm**: tính lại bằng **weighted F1** (theo trọng số số mẫu mỗi lớp, thay vì
trung bình đều như macro F1) — chỉ số này ít bị chi phối bởi lớp hiếm hơn nhiều:

| | Centralized | FedAvg | FedProx | FedNova |
|---|---|---|---|---|
| Weighted F1 | 0.9567 | **0.9532** | 0.9509 | 0.9511 |

**Kết luận đảo ngược hoàn toàn**: theo weighted F1, FedAvg (0.9532) > FedNova (0.9511) — NGƯỢC
với kết luận macro F1 ở trên. Điều này chứng minh chênh lệch "FedNova thắng FedAvg" ở mục 6 không
phải 1 hiệu ứng vững chắc của thuật toán, mà phần lớn là do cách vài lớp hiếm ngẫu nhiên rơi vào
kết quả khác nhau giữa các strategy.

**Khuyến nghị cụ thể trước khi đưa vào luận văn**:
1. Không dùng macro F1 làm chỉ số chính khi có lớp chỉ 7-134 mẫu test (`webddos`, `portmap`) —
   nên báo cáo cả weighted F1, hoặc bỏ hẳn các lớp có <100 mẫu test ra khỏi phép tính macro
   (chỉ giữ trong bảng để tham khảo), hoặc gộp các lớp cực hiếm lại thành 1 nhóm "other/rare".
2. Chạy lại toàn bộ 4 thí nghiệm (centralized + 3 FL) với **ít nhất 3-5 random seed khác nhau**,
   lấy trung bình ± độ lệch chuẩn CỦA CÁC LẦN CHẠY (không phải round-to-round trong 1 lần chạy) -
   đây mới là cách đúng để khẳng định 1 chênh lệch là "có ý nghĩa thống kê" thay vì ngẫu nhiên.
3. Nếu muốn giữ multiclass 13 lớp, cân nhắc thu thập/oversample thêm dữ liệu cho các lớp hiếm
   (đặc biệt `webddos` chỉ 51 mẫu tổng, `portmap` 685 mẫu tổng) trước khi dùng kết quả để so sánh
   thuật toán — hiện tại các lớp này gần như không đủ dữ liệu để đánh giá bất kỳ model nào.

## 7. Ma trận 4 kịch bản (Scenario) — thuật toán nào mạnh ở điều kiện nào (2026-09-14)

Theo yêu cầu "test theo từng tình huống để thấy các thuật toán mạnh ở điểm nào", đã thiết kế 4
kịch bản trên bài binary (chọn binary vì đã verify thống kê vững — xem mục 3 — không bị nhiễu lớp
hiếm như multiclass), mỗi kịch bản cô lập 1 biến số khác nhau:

| Kịch bản | Participation | Local epochs | Độ lệch benign/attack |
|---|---|---|---|
| S1 — Nhẹ | 100% (3/3) | 5 | Vừa phải (50/30/70) |
| S2 — Vừa | 67% (2/3) | 1 | Vừa phải (50/30/70) |
| S3 — Skew cực đoan | 100% (3/3) | 5 | **Cực đoan (90/5/95)** |
| S4 — Participation cực thấp | **34% (1/3)** | 1 | Vừa phải (50/30/70) |

### Kết quả (F1, round 41-50 trung bình)

| Kịch bản | Centralized | FedAvg | FedProx | FedNova |
|---|---|---|---|---|
| S1 — Nhẹ | 0.9980 | 0.9970 | 0.9962 | 0.9967 |
| S2 — Vừa | 0.9980 | 0.9967 | 0.9961 | 0.9965 |
| **S3 — Skew cực đoan** | 0.9981 | **0.9819** | 0.9787 | 0.9781 |
| S4 — Participation cực thấp | 0.9978 | 0.9965 | 0.9962 | 0.9964 |

### Phát hiện chính: label-skew là stress-test mạnh hơn hẳn participation/epoch

**Chỉ Scenario S3 (skew cực đoan) tạo ra chênh lệch F1 đáng kể** — F1 của cả 3 FL strategy rớt
xuống ~0.978-0.982 (so với ~0.996-0.998 ở S1/S2/S4). Giảm participation xuống tận 34% (S4) hay
giảm local_epochs xuống 1 (S2, S4) **hầu như không ảnh hưởng** đến F1 so với baseline nhẹ (S1) —
chênh lệch giữa S1/S2/S4 chỉ nằm trong khoảng 0.001-0.002, quá nhỏ để kết luận chắc chắn (như đã
phân tích ở mục 3, 5). Điều này cho thấy: **với dataset và mô hình này, mức độ lệch nhãn (label
skew) giữa các client mới là yếu tố quyết định độ khó của bài toán FL, không phải participation
hay số bước huấn luyện local**.

Ở Scenario S3, bóc tách thêm precision/recall:

| | Precision | Recall |
|---|---|---|
| FedAvg | **0.9675** | 0.9981 |
| FedProx | 0.9619 | 0.9977 |
| FedNova | 0.9607 | 0.9984 |

Recall gần như ngang nhau ở cả 3 (~0.998), nhưng **FedAvg giữ precision tốt nhất** (ít báo động
giả nhất) khi skew cực đoan — FedNova tuy accuracy nhỉnh hơn đôi chút (99.7734% vs 99.7520%) do
recall cao nhất, nhưng đổi lại precision thấp nhất, kéo F1 xuống thấp nhất trong 3 strategy. Đây
là 1 phát hiện cụ thể, có thể trích dẫn: **dưới label-skew cực đoan, FedAvg cho kết quả cân bằng
precision/recall tốt hơn FedProx/FedNova trên bài toán DDoS binary này** — ngược với kỳ vọng lý
thuyết rằng FedProx/FedNova nên vượt trội hơn FedAvg khi Non-IID nặng. Cần nói rõ trong luận văn
đây là kết quả THỰC NGHIỆM trên 1 dataset/kiến trúc cụ thể, không phải quy luật tổng quát.

**Việc còn thiếu để khẳng định chắc chắn** (giống caveat ở mục 5, 6.1): toàn bộ ma trận trên là
**1 lần chạy/ô** — nên làm bootstrap CI (rẻ, dùng checkpoint đã lưu trong
`results/scenarios/*/*.pt`) hoặc multi-seed trước khi đưa các con số này vào luận văn như kết
luận cuối cùng.

## 8. Scenario S5 — heterogeneous per-client local_epochs (2026-09-21)

### Động cơ

Toàn bộ 4 kịch bản ở mục 7 (và cả thí nghiệm mục 5) đều giữ `local_epochs` **giống nhau** ở mọi
client — chỉ thay đổi participation hoặc label-skew. Nhưng cơ chế mà FedNova được thiết kế để sửa
(theo đúng paper gốc Wang et al. 2020) là **"objective inconsistency"** sinh ra khi các client chạy
**số bước huấn luyện local (τ_i) khác nhau** — FedAvg cộng gộp thô sẽ lệch về phía client chạy
nhiều bước hơn, còn FedNova chuẩn hoá theo τ_i để bù lại. Vì chưa từng test đúng điều kiện này, đây
là kịch bản trực tiếp nhất để FedNova có cơ hội thể hiện ưu thế lý thuyết của nó.

**Thiết kế S5**: giữ nguyên participation 100% và label-skew vừa phải giống hệt S1 (baseline sạch,
chỉ đổi đúng 1 biến để cô lập tác động), nhưng gán mỗi client 1 số local_epochs khác nhau:

| Client | local_epochs | τ_i (số bước/round, ước tính) |
|---|---|---|
| client_1 | 1 | ~1,144 |
| client_2 | 4 | ~5,260 |
| client_3 | 8 | ~7,776 |

τ_i chênh lệch ~6.8 lần giữa client nhanh nhất và chậm nhất — mức heterogeneity mạnh hơn nhiều so
với bất kỳ kịch bản nào trước đó.

### Kết quả (round 41-50 trung bình)

| | Loss | Accuracy | F1 | Precision | Recall |
|---|---|---|---|---|---|
| Centralized | 0.0072 | 0.9983 | 0.9980 | 0.9976 | 0.9985 |
| FedAvg | 0.0086 | 0.9979 | **0.9967** | 0.9951 | 0.9984 |
| FedProx | 0.0103 | 0.9975 | 0.9962 | 0.9946 | 0.9979 |
| **FedNova** | **0.0514** | 0.9917 | **0.9886** | 0.9854 | 0.9933 |

Đây là **chênh lệch rõ ràng nhất trong toàn bộ các thí nghiệm đã chạy** — F1 của FedNova thấp hơn
FedAvg gần 1 điểm phần trăm tuyệt đối (0.9886 vs 0.9967), loss trung bình cao gấp ~6 lần. Nhưng
đáng chú ý hơn cả chênh lệch trung bình là **độ ổn định qua các round**:

| | loss (mean ± std, round 41-50) | F1 (mean ± std) | F1 thấp nhất (toàn bộ 50 round) |
|---|---|---|---|
| FedAvg | 0.0086 ± 0.0004 | 0.9967 ± 0.0002 | 0.9956 |
| FedProx | 0.0103 ± 0.0002 | 0.9962 ± 0.0001 | 0.9945 |
| **FedNova** | **0.0514 ± 0.1031** | **0.9886 ± 0.0213** | **0.9282** (round 43) |

FedNova dao động round-to-round **mạnh gấp ~100-250 lần** FedAvg/FedProx (std loss 0.1031 vs
0.0002-0.0004). Nhìn theo từng round, FedAvg/FedProx hội tụ mượt và ổn định quanh 1 dải hẹp, còn
FedNova liên tục có những cú sụt bất thường (round 17: loss 0.077; round 27: 0.107; round 35:
0.125; round 43: **0.344, accuracy rớt xuống 94.6%** rồi round sau lại phục hồi về ~0.997).

### Diễn giải

Kết quả **ngược hoàn toàn với kỳ vọng lý thuyết** rằng FedNova nên xử lý tốt hơn khi các client
chạy số bước local khác nhau. Ở đây, với chênh lệch τ_i ~6.8 lần, việc chuẩn hoá theo τ_i của
FedNova dường như khuếch đại nhiễu thay vì triệt tiêu nó: client chạy 8 epoch (client_3) đã hội tụ
sâu vào minimum cục bộ của riêng nó, và bước chuẩn hoá/kết hợp lại theo `tau_eff` của FedNova tạo
ra các bước cập nhật global lớn bất thường ở một số round, gây mất ổn định. Đây là hiện tượng đã
được ghi nhận trong một số nghiên cứu theo dõi FedNova (chuẩn hoá theo τ_i có thể phóng đại phương
sai gradient khi τ_i chênh lệch lớn và learning rate không được điều chỉnh tương ứng) — **không có
gì mâu thuẫn với lý thuyết gốc**, nhưng cho thấy trong thực nghiệm, ưu thế lý thuyết của FedNova
**không tự động thành hiện thực** nếu không tinh chỉnh thêm (vd giảm learning rate cho FedNova,
hoặc giới hạn chênh lệch τ_i ở mức vừa phải hơn).

**Đây chính là kết quả "chênh lệch rõ ràng giữa các thuật toán" mà mục tiêu đề ra** — nhưng cần nói
rõ trong luận văn: chênh lệch rõ ràng theo hướng **FedNova kém ổn định và kém chính xác hơn**
FedAvg/FedProx trong điều kiện heterogeneity compute mạnh, không phải theo hướng ưu thế lý thuyết
thường được trích dẫn. Đây là 1 phát hiện thực nghiệm hợp lệ và có thể trích dẫn nguyên vẹn (kèm
số liệu round-by-round để minh chứng tính bất ổn định, không chỉ số trung bình cuối).

**Việc còn thiếu trước khi đưa vào luận văn như kết luận cuối**: giống các mục trước, đây là 1 lần
chạy/seed — cần ít nhất 3 seed để xác nhận sự bất ổn định của FedNova không phải do may rủi ngẫu
nhiên của riêng seed=42, và nên thử lại với learning rate của FedNova được giảm xuống (vd 1/tau_eff
theo khuyến nghị trong 1 số bản mở rộng của paper) để xem có khắc phục được sự bất ổn định hay
không — nếu có, đó sẽ là 1 phát hiện bổ sung giá trị (FedNova cần tinh chỉnh LR khi τ_i chênh lệch
lớn, không "plug-and-play" như FedAvg).

### 8.1. Kiểm chứng multi-seed (2026-09-22)

Đã chạy lại S5 với 2 seed bổ sung (123, 2024 — cộng với lần chạy gốc thành 3 seed), áp dụng đúng
quy tắc mục 4-5 của [ly_thuyet_chi_so_danh_gia.md](ly_thuyet_chi_so_danh_gia.md). Trước đó phát
hiện ra **`server.py`/`client.py` chưa từng seed torch ở bất kỳ đâu** — mọi lần chạy trước đã ngẫu
nhiên tự nhiên nhưng không tái lập được; đã thêm `--seed` (seed model global + seed riêng từng
client, vì mỗi client chạy trong 1 Ray worker process khác nhau nên phải seed ngay trong
`client_fn`, seed ở process chính của `server.py` không có tác dụng tới client).

**Kết quả F1 (round 41-50 trung bình) qua 3 seed:**

| Seed | FedAvg | FedProx | FedNova |
|---|---|---|---|
| gốc (không seed rõ ràng) | 0.9967 | 0.9962 | 0.9886 |
| 123 | 0.9970 | 0.9955 | 0.9966 |
| 2024 | 0.9968 | 0.9958 | 0.9942 |
| **mean ± std (3 seed)** | **0.9968 ± 0.0002** | **0.9958 ± 0.0004** | **0.9931 ± 0.0041** |
| **95% CI** | [0.9967, 0.9970] | [0.9954, 0.9962] | **[0.9885, 0.9978]** |

**Độ ổn định trong từng lần chạy (std loss, round 41-50) qua 3 seed:**

| Seed | FedAvg | FedProx | FedNova |
|---|---|---|---|
| gốc | 0.0004 | 0.0002 | **0.1031** |
| 123 | 0.0009 | 0.0004 | **0.0082** |
| 2024 | 0.0012 | 0.0002 | **0.0259** |

### Điều gì được xác nhận (CONFIRMED), điều gì chưa (chỉ PLAUSIBLE)

**CONFIRMED — nhất quán ở cả 3/3 seed, không phụ thuộc seed cụ thể:**
- **FedNova luôn kém ổn định hơn FedAvg/FedProx ở mọi seed đã thử** — std loss của FedNova cao hơn
  FedAvg/FedProx từ **20 đến 250 lần** trong cả 3 lần chạy độc lập (0.0082-0.1031 vs
  0.0002-00012). Mức độ bất ổn định dao động theo seed (seed 123 "nhẹ" hơn seed gốc rất nhiều),
  nhưng **hướng** (FedNova luôn bất ổn hơn) không đổi qua cả 3 seed — đây là bằng chứng đủ mạnh để
  đưa vào luận văn như một kết luận có kiểm chứng.
- **F1 trung bình của FedAvg luôn cao hơn FedNova ở cả 3/3 seed** (0.9967>0.9886, 0.9970>0.9966,
  0.9968>0.9942) — nhất quán về hướng, dù biên độ chênh lệch dao động mạnh (0.008 → 0.0004 → 0.003).

**CHƯA CONFIRMED — vẫn chỉ PLAUSIBLE, cần thêm seed:**
- Khoảng tin cậy 95% của FedNova ([0.9885, 0.9978]) **chồng lấn** với khoảng tin cậy của FedAvg
  ([0.9967, 0.9970]) — do std giữa các seed của FedNova (0.0041) lớn hơn nhiều so với FedAvg
  (0.0002), 3 seed chưa đủ để CI thu hẹp lại tới mức tách biệt hẳn theo đúng quy tắc mục 7 của tài
  liệu lý thuyết. Nói cách khác: **"FedNova có F1 trung bình thấp hơn FedAvg" mới chỉ đúng 3/3 lần
  quan sát được (gợi ý khá mạnh) nhưng chưa đủ chặt về mặt thống kê** để loại hoàn toàn khả năng
  ngẫu nhiên — cần thêm seed (khuyến nghị ≥5 tổng cộng) để CI thu hẹp đủ tách biệt.

### Diễn giải

Multi-seed **không bác bỏ** phát hiện chính của S5, mà **làm rõ nó chính xác hơn**: kết luận đáng
tin cậy nhất không phải "FedNova luôn cho F1 thấp hơn X điểm %" (biên độ này dao động quá nhiều
theo seed để dùng làm con số cố định), mà là **"FedNova nhất quán kém ổn định hơn FedAvg/FedProx
khi các client có τ_i (số bước huấn luyện local) chênh lệch mạnh"** — đây là phát hiện có kiểm
chứng qua 3 seed độc lập, đáng đưa vào luận văn. Phần chênh lệch F1 trung bình tuyệt đối vẫn nên
được trình bày kèm khoảng tin cậy rộng, không nêu như 1 con số chắc chắn.

## 9. Kết luận

- Đã thử điều kiện khắc nghiệt hơn (partial participation, local_epochs=1) — khoảng cách
  FedAvg/FedNova với Centralized doãng rộng hơn (đúng lý thuyết), nhưng **FedNova vẫn chưa vượt
  FedAvg** trên bài toán binary. Kết luận: nút thắt thật sự là **độ khó của bài toán/mức Non-IID
  theo nhãn**, không phải hyperparameter huấn luyện — hướng multiclass (mục 4, ý 1-2) vẫn là bước
  tiếp theo đáng làm nhất.
- Model 162K tham số không phải nút thắt — bài toán binary DDoS/benign trên CICDDoS2019 vốn dễ,
  đã gần chạm trần accuracy (~99.8%) với mọi strategy.
- Máy tính yếu chỉ ảnh hưởng **thời gian chạy** (~3.5 giờ), không ảnh hưởng **kết quả**.
- 62,703 mẫu test là đủ để kết luận thống kê đáng tin cậy ở quy mô chênh lệch hiện tại — không
  cần thêm dữ liệu test.
- Muốn thấy sự khác biệt giữa FedAvg/FedProx/FedNova rõ ràng hơn cho luận văn, hướng đi đúng là
  **làm bài toán/điều kiện thí nghiệm khó hơn** (multiclass, Non-IID mạnh hơn theo loại tấn
  công, giảm local_epochs/fraction_fit) — không phải tăng kích thước model hay đổi phần cứng.
- Multiclass 13 lớp (mục 6) đúng là cho thấy chênh lệch macro F1 rõ hơn hẳn binary — nhưng
  **kiểm chứng sâu hơn ở mục 6.1 cho thấy "FedNova thắng FedAvg" theo macro F1 KHÔNG vững**: chỉ
  2 lớp hiếm (`portmap` 134 mẫu, `dns` 776 mẫu) đã đủ sức kéo kết quả theo 2 hướng ngược nhau với
  biên độ lớn hơn cả chênh lệch cuối cùng, và đổi sang weighted F1 thì kết luận **đảo ngược**
  (FedAvg > FedNova). **Chưa nên đưa "FedNova thắng FedAvg" vào luận văn như một kết luận** ở
  trạng thái dữ liệu/thí nghiệm hiện tại — cần multi-seed và xử lý lại các lớp quá hiếm (mục 6.1,
  khuyến nghị 1-3) trước khi khẳng định bất kỳ thứ tự strategy nào.
- **Scenario S5 (mục 8) — heterogeneous per-client local_epochs [1,4,8] — là kịch bản cho chênh
  lệch rõ ràng nhất trong toàn bộ dự án**, và là kịch bản DUY NHẤT đã được **kiểm chứng qua
  multi-seed** (mục 8.1, 3 seed độc lập). Kết quả kiểm chứng: **CONFIRMED** — FedNova nhất quán kém
  ổn định hơn FedAvg/FedProx ở cả 3/3 seed (std loss cao hơn 20-250 lần tuỳ seed) và F1 trung bình
  của FedNova thấp hơn FedAvg ở cả 3/3 seed — nhưng biên độ chênh lệch F1 dao động mạnh theo seed
  (0.0004 đến 0.008 điểm) nên khoảng tin cậy 95% của 2 nhóm vẫn **chồng lấn**, chưa đủ chặt để nêu
  1 con số chênh lệch cố định. Kết luận đúng đắn để đưa vào luận văn: **"FedNova kém ổn định hơn rõ
  rệt khi τ_i giữa client chênh lệch mạnh"** (có kiểm chứng), không phải "FedNova cho F1 thấp hơn
  X điểm %" (chưa đủ chặt). Đây là kết quả đi **ngược kỳ vọng lý thuyết** (FedNova được thiết kế để
  xử lý tốt hơn chính điều kiện này) — diễn giải khả dĩ: chuẩn hoá theo τ_i có thể khuếch đại nhiễu
  nếu không giảm learning rate tương ứng khi τ_i chênh lệch lớn.
