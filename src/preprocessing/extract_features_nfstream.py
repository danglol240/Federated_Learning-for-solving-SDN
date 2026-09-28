"""Trich xuat dac trung tu file .pcap (thu bang tcpdump trong luc chay
Mininet/hping3) bang NFStream, roi anh xa sang dung 77 cot CICFlowMeter-style
ma model (train tren CICDDoS2019) dang ky vong - de co the ap dung
scaler_<mode>.joblib + checkpoint da train cho traffic THAT.

QUAN TRONG - day la anh xa GAN DUNG, khong phai NFStream tinh chinh xac cung
cong thuc CICFlowMeter: NFStream KHONG track duoc 1 so nhom dac trung
(TCP window size, bulk-transfer, active/idle period, header length) - cac cot
nay duoc DIEN 0 va liet ke ro trong ZERO_FILLED_COLUMNS ben duoi. Ket qua danh
gia tren dac trung nay can duoc bao cao kem canh bao ro rang day la validation
cross-domain co xap xi, khong phai "dung boi CICFlowMeter" 100%.

Chay:
    python3 src/preprocessing/extract_features_nfstream.py \
        --pcap data/captures/pcap_attack_20260101_120000.pcap \
        --label attack \
        --output data/captures/features_attack_20260101_120000.csv
"""
import argparse
import os

import numpy as np
import pandas as pd
from nfstream import NFStreamer

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cac cot KHONG the tinh tu NFStream (statistical_analysis=True) - dien 0.
# Ly do tung nhom, xem docstring o dau file.
ZERO_FILLED_COLUMNS = [
    "fwd_header_length", "bwd_header_length",
    "fwd_avg_bytes_bulk", "fwd_avg_packets_bulk", "fwd_avg_bulk_rate",
    "bwd_avg_bytes_bulk", "bwd_avg_packets_bulk", "bwd_avg_bulk_rate",
    "init_fwd_win_bytes", "init_bwd_win_bytes",
    "active_mean", "active_std", "active_max", "active_min",
    "idle_mean", "idle_std", "idle_max", "idle_min",
]


def _safe_div(a, b):
    return np.where(b == 0, 0.0, a / b)


def map_nfstream_to_cicddos_schema(df):
    """df: DataFrame tra ve tu NFStreamer(...).to_pandas(). Tra ve DataFrame
    dung 77 cot theo dung ten trong scaler_<mode>.joblib['feature_columns']."""
    out = pd.DataFrame(index=df.index)

    dur_s = (df["bidirectional_duration_ms"] / 1000.0).replace(0, np.nan)

    out["protocol"] = df["protocol"]
    out["flow_duration"] = df["bidirectional_duration_ms"] * 1000.0  # ms -> us
    out["total_fwd_packets"] = df["src2dst_packets"]
    out["total_backward_packets"] = df["dst2src_packets"]
    out["fwd_packets_length_total"] = df["src2dst_bytes"]
    out["bwd_packets_length_total"] = df["dst2src_bytes"]
    out["fwd_packet_length_max"] = df["src2dst_max_ps"]
    out["fwd_packet_length_min"] = df["src2dst_min_ps"]
    out["fwd_packet_length_mean"] = df["src2dst_mean_ps"]
    out["fwd_packet_length_std"] = df["src2dst_stddev_ps"]
    out["bwd_packet_length_max"] = df["dst2src_max_ps"]
    out["bwd_packet_length_min"] = df["dst2src_min_ps"]
    out["bwd_packet_length_mean"] = df["dst2src_mean_ps"]
    out["bwd_packet_length_std"] = df["dst2src_stddev_ps"]
    out["flow_bytes_s"] = _safe_div(df["bidirectional_bytes"], dur_s.fillna(0))
    out["flow_packets_s"] = _safe_div(df["bidirectional_packets"], dur_s.fillna(0))
    out["flow_iat_mean"] = df["bidirectional_mean_piat_ms"] * 1000.0
    out["flow_iat_std"] = df["bidirectional_stddev_piat_ms"] * 1000.0
    out["flow_iat_max"] = df["bidirectional_max_piat_ms"] * 1000.0
    out["flow_iat_min"] = df["bidirectional_min_piat_ms"] * 1000.0
    out["fwd_iat_total"] = df["src2dst_duration_ms"] * 1000.0
    out["fwd_iat_mean"] = df["src2dst_mean_piat_ms"] * 1000.0
    out["fwd_iat_std"] = df["src2dst_stddev_piat_ms"] * 1000.0
    out["fwd_iat_max"] = df["src2dst_max_piat_ms"] * 1000.0
    out["fwd_iat_min"] = df["src2dst_min_piat_ms"] * 1000.0
    out["bwd_iat_total"] = df["dst2src_duration_ms"] * 1000.0
    out["bwd_iat_mean"] = df["dst2src_mean_piat_ms"] * 1000.0
    out["bwd_iat_std"] = df["dst2src_stddev_piat_ms"] * 1000.0
    out["bwd_iat_max"] = df["dst2src_max_piat_ms"] * 1000.0
    out["bwd_iat_min"] = df["dst2src_min_piat_ms"] * 1000.0
    out["fwd_psh_flags"] = df["src2dst_psh_packets"]
    out["bwd_psh_flags"] = df["dst2src_psh_packets"]
    out["fwd_urg_flags"] = df["src2dst_urg_packets"]
    out["bwd_urg_flags"] = df["dst2src_urg_packets"]
    out["fwd_header_length"] = 0
    out["bwd_header_length"] = 0
    out["fwd_packets_s"] = _safe_div(df["src2dst_packets"], dur_s.fillna(0))
    out["bwd_packets_s"] = _safe_div(df["dst2src_packets"], dur_s.fillna(0))
    out["packet_length_min"] = df["bidirectional_min_ps"]
    out["packet_length_max"] = df["bidirectional_max_ps"]
    out["packet_length_mean"] = df["bidirectional_mean_ps"]
    out["packet_length_std"] = df["bidirectional_stddev_ps"]
    out["packet_length_variance"] = df["bidirectional_stddev_ps"] ** 2
    out["fin_flag_count"] = df["bidirectional_fin_packets"]
    out["syn_flag_count"] = df["bidirectional_syn_packets"]
    out["rst_flag_count"] = df["bidirectional_rst_packets"]
    out["psh_flag_count"] = df["bidirectional_psh_packets"]
    out["ack_flag_count"] = df["bidirectional_ack_packets"]
    out["urg_flag_count"] = df["bidirectional_urg_packets"]
    out["cwe_flag_count"] = df["bidirectional_cwr_packets"]
    out["ece_flag_count"] = df["bidirectional_ece_packets"]
    out["down_up_ratio"] = _safe_div(df["dst2src_packets"], df["src2dst_packets"])
    out["avg_packet_size"] = _safe_div(df["bidirectional_bytes"], df["bidirectional_packets"])
    out["avg_fwd_segment_size"] = df["src2dst_mean_ps"]
    out["avg_bwd_segment_size"] = df["dst2src_mean_ps"]
    out["fwd_avg_bytes_bulk"] = 0
    out["fwd_avg_packets_bulk"] = 0
    out["fwd_avg_bulk_rate"] = 0
    out["bwd_avg_bytes_bulk"] = 0
    out["bwd_avg_packets_bulk"] = 0
    out["bwd_avg_bulk_rate"] = 0
    out["subflow_fwd_packets"] = df["src2dst_packets"]
    out["subflow_fwd_bytes"] = df["src2dst_bytes"]
    out["subflow_bwd_packets"] = df["dst2src_packets"]
    out["subflow_bwd_bytes"] = df["dst2src_bytes"]
    out["init_fwd_win_bytes"] = 0
    out["init_bwd_win_bytes"] = 0
    out["fwd_act_data_packets"] = df["src2dst_packets"]  # xap xi tho: khong tach duoc goi co payload
    out["fwd_seg_size_min"] = df["src2dst_min_ps"]
    out["active_mean"] = 0
    out["active_std"] = 0
    out["active_max"] = 0
    out["active_min"] = 0
    out["idle_mean"] = 0
    out["idle_std"] = 0
    out["idle_max"] = 0
    out["idle_min"] = 0

    return out.fillna(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pcap", required=True)
    parser.add_argument("--label", choices=["benign", "attack"], required=True,
                         help="Nhan that cua toan bo phien capture nay (dung de tinh accuracy sau).")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    pcap_size = os.path.getsize(args.pcap) if os.path.exists(args.pcap) else 0
    if pcap_size < 100:  # pcap global header ~24 byte - duoi 100 byte nghia la 0 goi tin
        print(f">>> LOI: file pcap chi {pcap_size} byte - khong co goi tin nao ca.")
        print(">>> Nguyen nhan pho bien: luc chay generate_traffic.py, controller (terminal 1) "
              "CHUA KIP san sang khien switch khong ket noi duoc ('Unable to contact the remote "
              "controller' trong log Mininet) -> khong co flow rule -> khong goi tin nao duoc "
              "forward giua cac host.")
        print(">>> Cach khac phuc: chay lai, nhung PHAI cho terminal 1 (controller) in het dong "
              "'>>> Switch ... da ket noi' cho CA 6 SWITCH roi moi chay generate_traffic.py o "
              "terminal 2 (dung chay gan nhu dong thoi 2 terminal).")
        return

    print(f">>> Doc pcap va tinh flow features bang NFStream: {args.pcap}")
    raw = NFStreamer(source=args.pcap, statistical_analysis=True).to_pandas()
    print(f">>> NFStream tim thay {len(raw)} flow")

    if len(raw) == 0:
        print(">>> Khong co flow nao - kiem tra lai file pcap (co goi tin IP khong).")
        return

    mapped = map_nfstream_to_cicddos_schema(raw)
    mapped["label"] = args.label

    n_zero_filled = len(ZERO_FILLED_COLUMNS)
    n_total = len(mapped.columns) - 1
    print(f">>> Anh xa xong {n_total} cot ({n_total - n_zero_filled} tinh tu NFStream, "
          f"{n_zero_filled} dien 0 do NFStream khong track: {ZERO_FILLED_COLUMNS})")

    output = args.output or os.path.join(
        PROJECT_ROOT, "data", "captures",
        f"features_{args.label}_{os.path.basename(args.pcap).replace('.pcap', '')}.csv"
    )
    mapped.to_csv(output, index=False)
    print(f">>> Da ghi {len(mapped)} dong vao {output}")


if __name__ == "__main__":
    main()
