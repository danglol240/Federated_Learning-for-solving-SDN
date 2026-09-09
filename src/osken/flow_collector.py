"""OS-Ken app: mo rong SimpleSwitch13, dinh ky poll flow stats va ghi CSV.

Chay tu thu muc src/osken/ de import sibling module don gian:
    cd src/osken
    FLOW_LABEL=benign osken-manager --ofp-tcp-listen-port 6653 flow_collector.py

Bien moi truong:
    FLOW_LABEL            nhan gan cho toan bo flow thu duoc trong phien nay
                           (vd: benign, attack, unknown). Mac dinh "unknown".
    FLOW_STATS_INTERVAL   chu ky poll flow stats, giay. Mac dinh 10.
    FLOW_OUTPUT_DIR       thu muc ghi CSV. Mac dinh <project_root>/data/captures.
"""
import csv
import os
from datetime import datetime

from simple_switch_13 import SimpleSwitch13
from os_ken.controller import ofp_event
from os_ken.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from os_ken.controller.handler import set_ev_cls
from os_ken.lib import hub
from os_ken.lib.packet import packet, ethernet, ether_types, in_proto, ipv4, icmp, tcp, udp

CSV_HEADER = [
    "flow_id", "timestamp", "datapath_id",
    "ip_src", "port_src", "ip_dst", "port_dst", "ip_proto",
    "icmp_code", "icmp_type",
    "duration_sec", "duration_nsec", "idle_timeout", "hard_timeout",
    "packet_count", "byte_count",
    "packet_count_per_second", "byte_count_per_second",
    "label",
]

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FlowCollector(SimpleSwitch13):
    def __init__(self, *args, **kwargs):
        super(FlowCollector, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.label = os.environ.get("FLOW_LABEL", "unknown")
        self.interval = int(os.environ.get("FLOW_STATS_INTERVAL", "10"))
        output_dir = os.environ.get("FLOW_OUTPUT_DIR", os.path.join(PROJECT_ROOT, "data", "captures"))
        os.makedirs(output_dir, exist_ok=True)
        session = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_path = os.path.join(output_dir, f"flow_stats_{self.label}_{session}.csv")
        with open(self.output_path, "w", newline="") as f:
            csv.writer(f).writerow(CSV_HEADER)
        self.flow_idle_timeout = int(os.environ.get("FLOW_IDLE_TIMEOUT", "20"))
        self.logger.info(">>> Flow collector ghi vao %s (label=%s, interval=%ss, idle_timeout=%ss)",
                          self.output_path, self.label, self.interval, self.flow_idle_timeout)
        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """Ghi de ban L2-only cua SimpleSwitch13: them match IP/L4 5-tuple
        de flow stats sau nay co ipv4_src/ipv4_dst/port... phuc vu thu thap.
        """
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst, src = eth.dst, eth.src
        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port
        out_port = self.mac_to_port[dpid].get(dst, ofproto.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD and eth.ethertype == ether_types.ETH_TYPE_IP:
            ip = pkt.get_protocol(ipv4.ipv4)
            match = None
            if ip.proto == in_proto.IPPROTO_ICMP:
                t = pkt.get_protocol(icmp.icmp)
                match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,
                                         ipv4_src=ip.src, ipv4_dst=ip.dst, ip_proto=ip.proto,
                                         icmpv4_code=t.code, icmpv4_type=t.type)
            elif ip.proto == in_proto.IPPROTO_TCP:
                t = pkt.get_protocol(tcp.tcp)
                match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,
                                         ipv4_src=ip.src, ipv4_dst=ip.dst, ip_proto=ip.proto,
                                         tcp_src=t.src_port, tcp_dst=t.dst_port)
            elif ip.proto == in_proto.IPPROTO_UDP:
                u = pkt.get_protocol(udp.udp)
                match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,
                                         ipv4_src=ip.src, ipv4_dst=ip.dst, ip_proto=ip.proto,
                                         udp_src=u.src_port, udp_dst=u.dst_port)

            if match is not None:
                if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                    self.add_flow(datapath, 1, match, actions, msg.buffer_id,
                                  idle_timeout=self.flow_idle_timeout)
                    return
                self.add_flow(datapath, 1, match, actions,
                              idle_timeout=self.flow_idle_timeout)

        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                   in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths.setdefault(datapath.id, datapath)
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)

    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                parser = dp.ofproto_parser
                dp.send_msg(parser.OFPFlowStatsRequest(dp))
            hub.sleep(self.interval)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        timestamp = datetime.now().timestamp()
        rows = []

        for stat in sorted(
            (f for f in ev.msg.body if f.priority == 1),
            key=lambda f: (f.match.get("eth_type", 0), f.match.get("ipv4_src", ""),
                           f.match.get("ipv4_dst", ""), f.match.get("ip_proto", 0)),
        ):
            match = stat.match
            if "ipv4_src" not in match:
                continue

            ip_proto = match.get("ip_proto", 0)
            icmp_code, icmp_type, port_src, port_dst = -1, -1, 0, 0
            if ip_proto == 1:
                icmp_code, icmp_type = match.get("icmpv4_code", -1), match.get("icmpv4_type", -1)
            elif ip_proto == 6:
                port_src, port_dst = match.get("tcp_src", 0), match.get("tcp_dst", 0)
            elif ip_proto == 17:
                port_src, port_dst = match.get("udp_src", 0), match.get("udp_dst", 0)

            flow_id = f"{match['ipv4_src']}-{port_src}-{match['ipv4_dst']}-{port_dst}-{ip_proto}"
            pkt_per_sec = stat.packet_count / stat.duration_sec if stat.duration_sec else 0
            byte_per_sec = stat.byte_count / stat.duration_sec if stat.duration_sec else 0

            rows.append([
                flow_id, timestamp, ev.msg.datapath.id,
                match["ipv4_src"], port_src, match["ipv4_dst"], port_dst, ip_proto,
                icmp_code, icmp_type,
                stat.duration_sec, stat.duration_nsec, stat.idle_timeout, stat.hard_timeout,
                stat.packet_count, stat.byte_count,
                round(pkt_per_sec, 4), round(byte_per_sec, 4),
                self.label,
            ])

        if rows:
            with open(self.output_path, "a", newline="") as f:
                csv.writer(f).writerows(rows)
