# Lý thuyết các chỉ số đánh giá dùng để so sánh FedAvg/FedProx/FedNova

Tài liệu này giải thích **ý nghĩa, công thức, và điều kiện áp dụng** của từng chỉ số đang được
dùng trong dự án để so sánh các chiến lược FL, cùng quy tắc quyết định khi nào có thể kết luận
"thuật toán A mạnh hơn B". Mục tiêu: dùng làm phần lý thuyết trích vào luận văn (chương phương
pháp đánh giá) và làm căn cứ khi đọc các bảng số liệu ở
[giai_doan_3_phan_tich_ket_qua.md](giai_doan_3_phan_tich_ket_qua.md).

## 1. Nhóm chỉ số phân loại (classification metrics)

Với bài toán phân loại nhị phân (benign/attack) hay đa lớp (13 loại tấn công), 4 chỉ số nền tảng
được tính từ ma trận nhầm lẫn (confusion matrix): True Positive (TP), False Positive (FP), False
Negative (FN), True Negative (TN).

### 1.1. Accuracy

```
Accuracy = (TP + TN) / (TP + TN + FP + FN)
```

Tỉ lệ dự đoán đúng trên tổng số mẫu. **Hạn chế**: không đáng tin khi dữ liệu mất cân bằng (class
imbalance). Ví dụ nếu 99% traffic là benign, một mô hình luôn đoán "benign" vẫn đạt accuracy 99%
dù vô dụng để phát hiện tấn công. Trong dự án, CICDDoS2019 có tỉ lệ attack/benign khá lệch và
multiclass có những lớp chỉ 134-776 mẫu test (`portmap`, `dns`) — đây là lý do accuracy **không**
được dùng làm chỉ số chính để so sánh thuật toán, chỉ dùng làm chỉ số tham khảo.

### 1.2. Precision, Recall

```
Precision = TP / (TP + FP)     # trong số dự đoán "attack", bao nhiêu % đúng
Recall    = TP / (TP + FN)     # trong số attack thật, bao nhiêu % bị phát hiện
```

Trong bài toán DDoS, hai chỉ số này có ý nghĩa vận hành khác nhau:
- **Precision thấp** → nhiều báo động giả (false alarm) → tốn tài nguyên xử lý sự cố không có
  thật, gây "alert fatigue" cho SOC.
- **Recall thấp** → bỏ lọt tấn công thật → hậu quả bảo mật trực tiếp.

Tuỳ ngữ cảnh triển khai mà một trong hai chỉ số quan trọng hơn — nhưng vì dự án không có yêu cầu
ưu tiên cụ thể, **F1** (trung bình điều hoà của cả hai) được chọn làm chỉ số chính.

### 1.3. F1-score

```
F1 = 2 * (Precision * Recall) / (Precision + Recall)
```

F1 chỉ cao khi **cả** precision và recall đều cao — phạt nặng mô hình lệch hẳn về một phía (vd
recall cao nhờ đoán "attack" tràn lan, kéo precision xuống). Đây là lý do F1 (không phải accuracy)
được chọn làm chỉ số chính trong toàn bộ báo cáo kết quả (mục 1, 5, 7, 8 của
`giai_doan_3_phan_tich_ket_qua.md`).

### 1.4. Macro vs Weighted vs Micro averaging (quan trọng cho multiclass)

Với multiclass (13 lớp), precision/recall/F1 được tính riêng cho từng lớp rồi gộp lại theo 1 trong
3 cách:

| Cách gộp | Công thức | Ý nghĩa |
|---|---|---|
| **Macro** | Trung bình cộng đơn giản của F1 từng lớp | Mọi lớp có trọng số **ngang nhau**, kể cả lớp chỉ có vài trăm mẫu |
| **Weighted** | Trung bình có trọng số theo số mẫu thật của mỗi lớp (support) | Lớp nhiều mẫu ảnh hưởng nhiều hơn tới kết quả cuối |
| **Micro** | Gộp TP/FP/FN của tất cả lớp trước rồi tính 1 công thức chung | Tương đương accuracy có trọng số theo mẫu, ít dùng khi cần phân biệt các lớp |

**Bài học rút ra từ dự án (mục 6.1 của báo cáo kết quả)**: kết luận "FedNova thắng FedAvg" ban đầu
dựa trên **macro F1** hoá ra chỉ do 2 lớp hiếm (`portmap` 134 mẫu, `dns` 776 mẫu) dao động ngược
chiều nhau với biên độ lớn hơn cả chênh lệch quan sát được — khi đổi sang **weighted F1**, kết luận
**đảo ngược hoàn toàn**. Quy tắc rút ra: **macro F1 chỉ nên dùng khi mọi lớp có đủ mẫu test (kinh
nghiệm: ≥100 mẫu/lớp)**; nếu có lớp quá hiếm, ưu tiên weighted F1 hoặc báo cáo cả hai kèm bảng
breakdown theo từng lớp để không che giấu hiệu ứng lớp hiếm.

### 1.5. Loss (Cross-Entropy)

```
Loss = -Σ y_true * log(y_pred)
```

Loss đo **độ tin cậy** của dự đoán, không chỉ đúng/sai nhị phân như accuracy — mô hình dự đoán
đúng nhãn nhưng với xác suất 0.51 vẫn bị phạt loss cao hơn mô hình dự đoán đúng với xác suất 0.99.
Trong dự án, loss được dùng làm **chỉ số phụ trợ để phát hiện bất ổn định huấn luyện** (xem mục
1.6 bên dưới) — vì loss nhạy với thay đổi nhỏ trong phân phối xác suất hơn accuracy/F1 (vốn chỉ
dựa vào argmax), nên là tín hiệu sớm tốt để phát hiện dao động giữa các round.

## 2. Độ ổn định (stability) — chỉ số phát hiện được nhờ Scenario S5

```
std(metric) qua N round cuối, hoặc qua N seed
```

Một thuật toán có **F1 trung bình cao nhưng std lớn** (dao động thất thường giữa các round) kém
đáng tin cậy hơn trong thực tế so với thuật toán có F1 trung bình thấp hơn 1 chút nhưng std rất
nhỏ — vì hệ thống production cần độ dự đoán được (không thể chấp nhận accuracy tụt đột ngột giữa
chừng). Đây chính là phát hiện chính của Scenario S5: FedNova có std loss cao gấp ~100-250 lần
FedAvg/FedProx (0.1031 vs 0.0002-0.0004) dù F1 trung bình chỉ thấp hơn ~0.8 điểm %. Nếu chỉ nhìn
điểm trung bình cuối cùng (round 50 hoặc trung bình round 41-50) mà không nhìn std/biểu đồ
round-by-render, phát hiện quan trọng nhất của cả kịch bản sẽ bị bỏ sót.

**Cách áp dụng**: luôn báo cáo `mean ± std`, không chỉ 1 con số trung bình; vẽ đường cong theo
round (không chỉ bảng số cuối) để mắt người phát hiện được dao động bất thường.

## 3. Sai số chuẩn và khoảng tin cậy — vì sao cần trước khi kết luận

### 3.1. Sai số chuẩn (Standard Error) của accuracy đo trên tập test

Với n mẫu test và accuracy quan sát được p, coi mỗi dự đoán đúng/sai là 1 phép thử Bernoulli:

```
SE = sqrt( p * (1 - p) / n )
```

Chỉ số này trả lời câu hỏi "tập test có đủ lớn để phân biệt 2 accuracy gần nhau không". Ví dụ đã
tính trong dự án (mục 3 báo cáo kết quả): với n = 62,703 mẫu test binary, p ≈ 0.998 → SE ≈
0.0178% — đủ nhỏ để khẳng định chênh lệch accuracy cỡ 0.05-0.1 điểm % giữa các strategy là tín hiệu
thật, không phải nhiễu do cỡ mẫu test nhỏ.

**Lưu ý quan trọng**: SE của tập test chỉ giải quyết được câu hỏi "phép đo có đủ chính xác không",
**không** giải quyết được câu hỏi "kết quả có lặp lại được với random seed khác không" — đó là lý
do cần multi-seed (mục 4).

### 3.2. Khoảng tin cậy (Confidence Interval — CI) và quy tắc so sánh 2 nhóm

Với multi-seed (N lần chạy độc lập, mỗi lần 1 seed khác nhau), CI 95% của trung bình được ước
lượng bằng:

```
CI = mean ± 1.96 * (std / sqrt(N))     # xấp xỉ chuẩn, N nên >= 3-5
```

**Quy tắc quyết định "A tốt hơn B"**: chỉ kết luận có ý nghĩa khi CI của A và B **không chồng lấn
(non-overlapping)**, hoặc chênh lệch trung bình lớn hơn tổng độ lệch chuẩn của cả hai nhóm. Nếu CI
chồng lấn, sự khác biệt quan sát được có thể chỉ do may rủi của lần chạy/seed cụ thể — đúng như
trường hợp đã phát hiện ở mục 6.1 (macro F1 multiclass): chênh lệch FedNova-FedAvg quá nhỏ so với
biến động do 2 lớp hiếm gây ra, tương đương CI chồng lấn nếu tính chính xác.

## 4. Multi-seed replication — vì sao 1 lần chạy không đủ để kết luận

Mỗi lần chạy hiện tại của dự án dùng `seed=42` cố định cho: thứ tự shuffle dữ liệu khi chia
non-IID, khởi tạo trọng số mô hình, thứ tự batch khi huấn luyện. Một kết quả "A > B" quan sát được
ở 1 seed có thể là:
1. **Hiệu ứng thật** của thuật toán (điều muốn chứng minh), hoặc
2. **Hiệu ứng ngẫu nhiên** của riêng seed đó (khởi tạo trọng số may mắn, thứ tự batch thuận lợi
   cho 1 thuật toán cụ thể ở lần chạy này).

Chỉ có cách chạy lại với **≥3 seed khác nhau** (khuyến nghị dùng cùng bộ seed cho mọi thuật toán để
so sánh công bằng — vd 42, 123, 2024) và xem chênh lệch có **nhất quán về dấu và độ lớn** qua các
seed hay không, mới phân biệt được 2 khả năng trên. Đây là hạng mục còn thiếu ở **mọi** kịch bản
hiện tại (S1-S5 và multiclass) — được nhắc lại nhất quán trong các mục 3, 5, 6.1, 7, 8 của báo cáo
kết quả như điều kiện bắt buộc trước khi đưa bất kỳ kết luận thứ tự thuật toán nào vào luận văn.

## 5. Tính nhất quán qua nhiều điều kiện (cross-scenario consistency)

Một thuật toán chỉ nên được gọi là "mạnh hơn" nếu ưu thế đó **lặp lại qua nhiều kịch bản** (mức
Non-IID khác nhau, mức participation khác nhau, mức heterogeneity compute khác nhau) — không phải
chỉ đúng ở đúng 1 kịch bản bị "vặn" để lộ ra chênh lệch. Đây là lý do dự án dùng ma trận kịch bản
S1-S5 (thay vì chỉ 1 lần chạy) — mỗi kịch bản cô lập đúng 1 biến số (participation, label-skew,
compute heterogeneity), để biết chênh lệch quan sát được có nguyên nhân rõ ràng nào, và có lặp lại
ở kịch bản khác cùng "họ" hay không (vd S1/S2/S4 đều participation/epoch thấp nhưng label-skew vừa
phải → cho kết quả gần giống nhau; chỉ S3 label-skew cực đoan mới tạo chênh lệch → kết luận: label
skew là biến số quyết định, không phải participation).

## 6. Chỉ số phụ trợ (đã cài đặt, dùng khi cần mở rộng phân tích)

| Chỉ số | Ý nghĩa | Nơi tính trong code |
|---|---|---|
| **Tốc độ hội tụ** (rounds-to-target) | Số round cần để đạt 1 ngưỡng F1 cho trước | Có thể tính từ cột `round`/`f1` trong `results/**/*.csv`, chưa tự động hoá |
| **Chi phí giao tiếp** (communication bytes) | Tổng bytes trao đổi client↔server để đạt 1 mức accuracy | `src/evaluation/plot_comparison.py::compute_communication_bytes` |
| **Fairness giữa client** | Chênh lệch accuracy giữa client tốt nhất và tệ nhất (worst-case client không bị hy sinh) | Chưa cài đặt — cần đánh giá riêng từng client thay vì chỉ nhìn global test set |

## 7. Tóm tắt: quy tắc tổng hợp để kết luận "A mạnh hơn B"

Chỉ kết luận khi **đồng thời** thoả:

1. Dùng đúng chỉ số phù hợp với dữ liệu (weighted F1 nếu có lớp hiếm, không phải accuracy hay macro
   F1 mặc định).
2. Chênh lệch vượt quá sai số đo trên tập test (SE, mục 3.1) — loại trừ khả năng do tập test nhỏ.
3. Chạy **≥3 seed**, CI của 2 nhóm **không chồng lấn** — loại trừ khả năng do may rủi random seed.
4. Kết luận **nhất quán qua ≥2 kịch bản** khác nhau — loại trừ khả năng chỉ đúng ở 1 điều kiện bị
   chọn lọc ngẫu nhiên.
5. Nếu chênh lệch trung bình nhỏ nhưng **độ ổn định (std)** khác biệt rõ (như Scenario S5), nêu rõ
   đây là ưu thế về **độ ổn định**, không lẫn với ưu thế về **độ chính xác** — hai loại ưu thế khác
   nhau và có ý nghĩa vận hành khác nhau.

Áp dụng quy tắc này vào trạng thái hiện tại: phát hiện S5 ("FedNova kém ổn định hơn dưới compute
heterogeneity") mới thoả điều kiện 1, 2, 5 — **chưa thoả 3, 4** — nên hiện tại chỉ ở mức
**PLAUSIBLE**, chưa phải **CONFIRMED**, cho đến khi chạy multi-seed.

## Tài liệu tham khảo

- McMahan et al., 2017 — *"Communication-Efficient Learning of Deep Networks from Decentralized
  Data"* (FedAvg gốc).
- Li et al., 2020 — *"Federated Optimization in Heterogeneous Networks"* (FedProx gốc).
- Wang et al., 2020 — *"Tackling the Objective Inconsistency Problem in Heterogeneous Federated
  Optimization"* (FedNova gốc, công thức chuẩn hoá τ_i).
- Li et al., 2022 — *"Federated Learning on Non-IID Data Silos: An Experimental Study"* (phương
  pháp luận thiết kế kịch bản Non-IID và benchmark nhiều thuật toán FL — nguồn tham khảo cho cách
  tiếp cận ma trận kịch bản S1-S5 của dự án).
