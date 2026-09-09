"""Sinh traffic trong mang MultiZoneTopo (topology.py) de test Flow Collector.
Chi dung de KIEM TRA pipeline thu flow-stats (Giai doan 2) - khong dung de
tao du lieu huan luyen chinh thuc (du lieu chinh la ISCX-VPN2016, xem README).

Chay (can sudo, sau khi da chay flow_collector controller o terminal khac):
    sudo python3 src/emulation/generate_traffic.py --mode benign
    sudo python3 src/emulation/generate_traffic.py --mode attack
    sudo python3 src/emulation/generate_traffic.py --mode mixed
"""
import argparse
from time import sleep

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import RemoteController

from topology import MultiZoneTopo


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--controller-ip", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=6653)
    parser.add_argument("--mode", choices=["benign", "attack", "mixed"], default="mixed")
    args = parser.parse_args()

    setLogLevel("info")
    topo = MultiZoneTopo()
    controller = RemoteController("c0", ip=args.controller_ip, port=args.port)
    net = Mininet(topo=topo, link=TCLink, controller=controller)
    net.start()

    hosts = net.hosts
    try:
        if args.mode in ("benign", "mixed"):
            run_benign(hosts)
        if args.mode in ("attack", "mixed"):
            run_attack(hosts)
    finally:
        net.stop()


if __name__ == "__main__":
    main()
