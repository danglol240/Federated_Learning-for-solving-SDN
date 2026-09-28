"""Sinh traffic trong mang MultiZoneTopo (topology.py) de test Flow Collector,
dong thoi (tuy chon --pcap) thu goi tin bang tcpdump de sau nay trich xuat
77-feature CICFlowMeter-style bang NFStream (xem
src/preprocessing/extract_features_nfstream.py) roi danh gia model FL da
train (xem src/evaluation/live_validate.py) tren traffic THAT thay vi chi
tren tap test noi bo cua CICDDoS2019.

Chay (can sudo vi Mininet + tcpdump deu can quyen root, sau khi da chay
flow_collector controller o terminal khac):
    sudo python3 src/emulation/generate_traffic.py --mode benign --pcap
    sudo python3 src/emulation/generate_traffic.py --mode attack --pcap
    sudo python3 src/emulation/generate_traffic.py --mode mixed --pcap

Neu khong truyen --pcap, chi chay traffic nhu cu (khong thu goi tin) - dung
de test pipeline flow_collector nhu truoc day.
"""
import argparse
import os
import signal
import subprocess
from datetime import datetime
from time import sleep

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import RemoteController

from topology import MultiZoneTopo

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_benign(hosts):
    print(">>> Benign: ping + iperf giua cac host")
    server = hosts[0]
    server.cmd("iperf -s -p 5050 &")
    sleep(1)
    for h in hosts[1:]:
        h.cmd(f"ping -c 5 {server.IP()}")
        h.cmd(f"iperf -p 5050 -c {server.IP()} -t 3")


def run_attack(hosts):
    print(">>> Attack: hping3 flood (can hping3 da cai)")
    target = hosts[0]
    src = hosts[-1]
    src.cmd(f"timeout 10s hping3 -S -V -d 120 -w 64 -p 80 --flood --rand-source {target.IP()}")


MININET_SUBNET = "10.0.0.0/24"  # khop topology.py - CHI bat goi tin trong mang ao, khong dinh
                                 # phai traffic that cua may (wifi/ethernet) neu dung "-i any"
                                 # ma khong loc, tung gay pcap phinh to 11.5GB het sach dia (2026-09-28)
CAPTURE_TIMEOUT_SEC = 60   # gioi han cung, tu dong dung du script co treo/quen tat
CAPTURE_MAX_MB = 200       # gioi han dung luong cung (theo timeout, phong khi 60s van qua nhieu goi)


def start_pcap_capture(mode):
    """Bat tcpdump tren interface 'any', LOC theo MININET_SUBNET de chi bat
    goi tin trong mang ao (khong dinh traffic that cua may), va boc trong
    `timeout` + gioi han dung luong (-C/-W) de tu dong dung ke ca khi script
    bi treo/quen goi stop_pcap_capture(). Tra ve (process, duong dan pcap).

    -Z root: mac dinh tcpdump TU HA QUYEN xuong user he thong "tcpdump" TRUOC
    khi mo file ghi (xem man tcpdump, muc -Z/-C) - user do KHONG co quyen ghi
    vao data/captures/ (thu muc cua danglol240) nen tao file that bai AM
    THAM (2026-09-28, stderr bi DEVNULL nen khong thay loi). Giu quyen root
    (script da chay qua sudo) de tranh loai loi nay.
    """
    session = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(PROJECT_ROOT, "data", "captures")
    os.makedirs(out_dir, exist_ok=True)
    pcap_path = os.path.join(out_dir, f"pcap_{mode}_{session}.pcap")
    proc = subprocess.Popen(
        [
            "timeout", f"--signal=INT", str(CAPTURE_TIMEOUT_SEC),
            "tcpdump", "-i", "any", "-Z", "root",
            "-y", "LINUX_SLL",  # ep dinh dang Linux cooked v1 (KHONG phai v2/SLL2 mac dinh moi cua
                                 # libpcap) - NFStream (dua tren nDPI) chua ho tro SLL2, se am
                                 # tham tra ve 0 flow neu dung mac dinh (2026-09-28)
            "-C", str(CAPTURE_MAX_MB), "-W", "1",  # dung han sau khi 1 file day CAPTURE_MAX_MB
            "-w", pcap_path,
            f"net {MININET_SUBNET}",
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    sleep(1)  # doi tcpdump khoi dong xong truoc khi sinh traffic
    if proc.poll() is not None:  # da thoat ngay lap tuc -> loi khoi dong, in ra de biet
        out, err = proc.communicate()
        print(f">>> LOI: tcpdump thoat ngay voi ma {proc.returncode}. stderr: {err.decode(errors='replace')}")
    else:
        print(f">>> tcpdump dang thu goi tin (loc {MININET_SUBNET}, toi da {CAPTURE_MAX_MB}MB / "
              f"{CAPTURE_TIMEOUT_SEC}s) vao {pcap_path} (pid={proc.pid})")
    return proc, pcap_path


def stop_pcap_capture(proc, pcap_path):
    if proc.poll() is not None:
        return pcap_path  # da thoat tu truoc (loi khoi dong, da bao o start_pcap_capture)
    sleep(1)  # doi goi tin cuoi cung den (vd FIN/ACK sau khi lenh host da tra ve)
    proc.send_signal(signal.SIGINT)  # SIGINT (khong phai kill) de tcpdump ghi dung trailer pcap
    try:
        out, err = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    if proc.returncode not in (0, -signal.SIGINT, 124, 130):  # 124/130 = timeout/SIGINT thoat binh thuong
        print(f">>> CANH BAO: tcpdump thoat voi ma {proc.returncode}. stderr: {err.decode(errors='replace')}")
    # Luu y: voi -C + -W 1, file DAU TIEN giu dung ten -w (khong hau to so) - chi file THU 2
    # tro di moi them so (vd .pcap1) - vi -W 1 gioi han dung o 1 file nen se khong bao gio xay ra.
    size_mb = os.path.getsize(pcap_path) / 1e6 if os.path.exists(pcap_path) else 0
    print(f">>> Da dung tcpdump. File pcap: {pcap_path} ({size_mb:.2f} MB)")
    return pcap_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--controller-ip", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=6653)
    parser.add_argument("--mode", choices=["benign", "attack", "mixed"], default="mixed")
    parser.add_argument("--pcap", action="store_true",
                         help="Thu goi tin bang tcpdump song song luc sinh traffic, de sau nay "
                              "trich xuat feature bang NFStream va danh gia model tren traffic that.")
    args = parser.parse_args()

    setLogLevel("info")
    topo = MultiZoneTopo()
    controller = RemoteController("c0", ip=args.controller_ip, port=args.port)
    net = Mininet(topo=topo, link=TCLink, controller=controller)
    net.start()

    pcap_proc, pcap_path = (start_pcap_capture(args.mode) if args.pcap else (None, None))

    hosts = net.hosts
    try:
        if args.mode in ("benign", "mixed"):
            run_benign(hosts)
        if args.mode in ("attack", "mixed"):
            run_attack(hosts)
    finally:
        if pcap_proc is not None:
            stop_pcap_capture(pcap_proc, pcap_path)
        net.stop()

    if pcap_path is not None:
        if args.mode == "mixed":
            print(">>> CANH BAO: --mode mixed tron ca benign+attack trong 1 pcap, khong co nhan "
                  "rach roi tung flow. De danh gia co ground-truth dung, nen chay rieng "
                  "--mode benign --pcap va --mode attack --pcap thanh 2 phien khac nhau.")
        else:
            print(f"\n>>> Buoc tiep theo (chay trong .venv, KHONG can sudo):")
            print(f"    source .venv/bin/activate")
            print(f"    python3 src/preprocessing/extract_features_nfstream.py "
                  f"--pcap {pcap_path} --label {args.mode} "
                  f"--output data/captures/features_{args.mode}.csv")


if __name__ == "__main__":
    main()
