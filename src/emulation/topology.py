"""Topology Mininet 3 vung mang, khop config/config.yaml (sdn.num_zones=3,
switches_per_zone=2, hosts_per_switch=2). Moi vung se la 1 FL client sau nay
(xem config/noniid_distribution.yaml: client_1=Van phong, client_2=Ky tuc xa,
client_3=Phong Lab).

Chay (can sudo):
    sudo python3 src/emulation/topology.py
    sudo python3 src/emulation/topology.py --controller-ip 127.0.0.1 --port 6653

Dat ten:
    switch  s<vung><thu_tu>       vd s11, s12 (vung 1), s21, s22 (vung 2)
    host    h<vung><switch><may>  vd h111, h112 (vung 1, switch 1)
    ip      10.0.0.<so_thu_tu_toan_cuc> - CHUNG 1 SUBNET cho ca 12 host.

    Ly do dung chung 1 subnet: mang nay chi co switch L2 (khong co router),
    cac switch duoc noi thanh 1 mien L2 duy nhat qua backbone link. Neu chia
    moi vung 1 subnet /24 rieng, host khac vung se KHONG CO ROUTE toi nhau
    (khong co gateway/router) -> ping/hping3 se that bai am tham hoac loopback
    qua "lo" thay vi di ra mang that.
"""
import argparse

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import OVSKernelSwitch, RemoteController

NUM_ZONES = 3
SWITCHES_PER_ZONE = 2
HOSTS_PER_SWITCH = 2


class MultiZoneTopo(Topo):
    def build(self):
        global_seq = 0
        for zone in range(1, NUM_ZONES + 1):
            zone_switches = []
            host_seq = 0
            for sw_idx in range(1, SWITCHES_PER_ZONE + 1):
                switch = self.addSwitch(f"s{zone}{sw_idx}", cls=OVSKernelSwitch,
                                         protocols="OpenFlow13")
                zone_switches.append(switch)
                for _ in range(HOSTS_PER_SWITCH):
                    host_seq += 1
                    global_seq += 1
                    host = self.addHost(
                        f"h{zone}{sw_idx}{host_seq}",
                        ip=f"10.0.0.{global_seq}/24",
                        mac=f"00:00:00:00:{zone:02d}:{host_seq:02d}",
                    )
                    self.addLink(host, switch)

            for i in range(len(zone_switches) - 1):
                self.addLink(zone_switches[i], zone_switches[i + 1])

        for zone in range(1, NUM_ZONES):
            backbone_a = f"s{zone}1"
            backbone_b = f"s{zone + 1}1"
            self.addLink(backbone_a, backbone_b)


def start_network(controller_ip, port, open_cli):
    topo = MultiZoneTopo()
    controller = RemoteController("c0", ip=controller_ip, port=port)
    net = Mininet(topo=topo, link=TCLink, controller=controller)
    net.start()
    print(f">>> Mang da khoi dong: {NUM_ZONES} vung x {SWITCHES_PER_ZONE} switch x "
          f"{HOSTS_PER_SWITCH} host = {NUM_ZONES * SWITCHES_PER_ZONE * HOSTS_PER_SWITCH} host")
    if open_cli:
        CLI(net)
    net.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--controller-ip", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=6653)
    parser.add_argument("--no-cli", action="store_true", help="Khong mo Mininet CLI, tu dong net.stop() ngay")
    args = parser.parse_args()

    setLogLevel("info")
    start_network(args.controller_ip, args.port, open_cli=not args.no_cli)
