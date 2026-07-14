#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph — cleaned for real USRP hardware.
# Title: USRP realtime IQ capture
# Requires: gnuradio 3.10+, uhd, PyQt5
#
# Example:
#   python3 usrp_rt_capture.py --device-ip 192.168.101.100 --center-freq 920M
#   python3 usrp_rt_capture.py --enable-zmq --zmq-address tcp://*:5555

from gnuradio import qtgui
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float
from gnuradio import uhd
from gnuradio import zeromq
import sip


class UsrpRtCapture(gr.top_block, Qt.QWidget):
    def __init__(
        self,
        device_ip="192.168.101.100",
        center_freq=920e6,
        sample_rate=1e6,
        receive_gain=10,
        serial="",
        enable_zmq=False,
        zmq_address="tcp://*:5555",
        antenna="RX2",
    ):
        gr.top_block.__init__(self, "USRP实时数据流采集", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle(f"USRP实时数据流采集 - {device_ip}")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme("gnuradio-grc"))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)

        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)

        self.settings = Qt.QSettings("GNU Radio", "usrp_rt_capture")
        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)

        self.samp_rate = float(sample_rate)
        self.receive_gain = float(receive_gain)
        self.center_freq = float(center_freq)
        self.device_ip = device_ip
        self.serial = serial or ""
        self.enable_zmq = bool(enable_zmq)
        self.zmq_address = zmq_address
        self.antenna = antenna
        self.channels = [0]

        device_args = f"addr={self.device_ip}"
        if self.serial:
            device_args += f",serial={self.serial}"

        self.uhd_usrp_source_0_0 = uhd.usrp_source(
            device_args,
            uhd.stream_args(
                cpu_format="fc32",
                otw_format="sc16",
                args="",
                channels=self.channels,
            ),
        )
        self.uhd_usrp_source_0_0.set_samp_rate(self.samp_rate)
        self.uhd_usrp_source_0_0.set_time_unknown_pps(uhd.time_spec(0))
        self.uhd_usrp_source_0_0.set_center_freq(self.center_freq, 0)
        self.uhd_usrp_source_0_0.set_antenna(self.antenna, 0)
        self.uhd_usrp_source_0_0.set_gain(self.receive_gain, 0)

        self.qtgui_sink_x_0_0 = qtgui.sink_c(
            1024,
            window.WIN_BLACKMAN_hARRIS,
            self.center_freq,
            self.samp_rate,
            f"USRP {self.device_ip} - {self.center_freq/1e6:.1f} MHz",
            True,
            True,
            True,
            True,
            None,
        )
        self.qtgui_sink_x_0_0.set_update_time(1.0 / 10)
        self._qtgui_sink_x_0_0_win = sip.wrapinstance(self.qtgui_sink_x_0_0.qwidget(), Qt.QWidget)
        self.qtgui_sink_x_0_0.enable_rf_freq(True)
        self.top_layout.addWidget(self._qtgui_sink_x_0_0_win)

        self.zeromq_pub_sink_0 = None
        if self.enable_zmq:
            self.zeromq_pub_sink_0 = zeromq.pub_sink(
                itemsize=gr.sizeof_gr_complex,
                vlen=1,
                address=self.zmq_address,
                timeout=100,
                pass_tags=False,
                hwm=-1,
                key="",
            )
            print(f"  ZMQ publish enabled: {self.zmq_address}")

        self.connect((self.uhd_usrp_source_0_0, 0), (self.qtgui_sink_x_0_0, 0))
        if self.enable_zmq and self.zeromq_pub_sink_0:
            self.connect((self.uhd_usrp_source_0_0, 0), (self.zeromq_pub_sink_0, 0))

        print("USRP realtime capture started:")
        print(f"  device: {device_args}")
        print(f"  center: {self.center_freq/1e6:.3f} MHz")
        print(f"  rate:   {self.samp_rate/1e6:.3f} MS/s")
        print(f"  gain:   {self.receive_gain} dB  antenna={self.antenna}")

    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "usrp_rt_capture")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()
        event.accept()

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = float(samp_rate)
        self.qtgui_sink_x_0_0.set_frequency_range(self.center_freq, self.samp_rate)
        self.uhd_usrp_source_0_0.set_samp_rate(self.samp_rate)

    def get_receive_gain(self):
        return self.receive_gain

    def set_receive_gain(self, receive_gain):
        self.receive_gain = float(receive_gain)
        for ch in self.channels:
            self.uhd_usrp_source_0_0.set_gain(self.receive_gain, ch)

    def get_center_freq(self):
        return self.center_freq

    def set_center_freq(self, center_freq):
        self.center_freq = float(center_freq)
        for ch in self.channels:
            self.uhd_usrp_source_0_0.set_center_freq(self.center_freq, ch)
        self.qtgui_sink_x_0_0.set_frequency_range(self.center_freq, self.samp_rate)


def main(top_block_cls=UsrpRtCapture, options=None):
    parser = ArgumentParser(description="USRP realtime IQ capture")
    parser.add_argument("--device-ip", default="192.168.101.100")
    parser.add_argument("--center-freq", type=eng_float, default=920e6)
    parser.add_argument("--sample-rate", type=eng_float, default=1e6)
    parser.add_argument("--receive-gain", type=float, default=10)
    parser.add_argument("--serial", default="", help="Optional serial; leave empty for network USRP")
    parser.add_argument("--antenna", default="RX2")
    parser.add_argument("--enable-zmq", action="store_true")
    parser.add_argument("--zmq-address", default="tcp://*:5555")
    args = parser.parse_args()

    qapp = Qt.QApplication(sys.argv)
    tb = top_block_cls(
        device_ip=args.device_ip,
        center_freq=args.center_freq,
        sample_rate=args.sample_rate,
        receive_gain=args.receive_gain,
        serial=args.serial,
        enable_zmq=args.enable_zmq,
        zmq_address=args.zmq_address,
        antenna=args.antenna,
    )
    tb.start()
    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)
    qapp.exec_()


if __name__ == "__main__":
    main()
