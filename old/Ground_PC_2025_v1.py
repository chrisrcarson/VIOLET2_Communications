#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Ground PC Software
# GNU Radio version: 3.8.2.0

from distutils.version import StrictVersion

if __name__ == '__main__':
    import ctypes
    import sys
    if sys.platform.startswith('linux'):
        try:
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except:
            print("Warning: failed to XInitThreads()")

import os
import sys
sys.path.append(os.environ.get('GRC_HIER_PATH', os.path.expanduser('~/.grc_gnuradio')))

from PyQt5 import Qt
from gnuradio import eng_notation
from gnuradio import qtgui
from gnuradio.filter import firdes
import sip
from gnuradio import analog
from gnuradio import blocks
from gnuradio import digital
from gnuradio import gr
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio.qtgui import Range, RangeWidget
from hdlc_framer_with_preamble import hdlc_framer_with_preamble  # grc-generated hier_block
from math import pi
from nrzs_line_coding import nrzs_line_coding  # grc-generated hier_block
from trxv_uplink_fsk_modulator import trxv_uplink_fsk_modulator  # grc-generated hier_block
from trxvu_bpsk_carrier_symbol_rec import trxvu_bpsk_carrier_symbol_rec  # grc-generated hier_block
from trxvu_bpsk_data_recovery import trxvu_bpsk_data_recovery  # grc-generated hier_block
import limesdr

from gnuradio import qtgui

class Ground_PC_2025_v1(gr.top_block, Qt.QWidget):

    def __init__(self, baud_rate=9600, dl_freq=145.91e6, rx_gain=30, sps=20, tx_gain=60, ul_freq=436830000):
        gr.top_block.__init__(self, "Ground PC Software")
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Ground PC Software")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except:
            pass
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "Ground_PC_2025_v1")

        try:
            if StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
                self.restoreGeometry(self.settings.value("geometry").toByteArray())
            else:
                self.restoreGeometry(self.settings.value("geometry"))
        except:
            pass

        ##################################################
        # Parameters
        ##################################################
        self.baud_rate = baud_rate
        self.dl_freq = dl_freq
        self.rx_gain = rx_gain
        self.sps = sps
        self.tx_gain = tx_gain
        self.ul_freq = ul_freq

        ##################################################
        # Variables
        ##################################################
        self.ul_freq_ui = ul_freq_ui = ul_freq
        self.tx_gain_ui = tx_gain_ui = tx_gain
        self.squelch_ui = squelch_ui = -50
        self.samp_rate = samp_rate = baud_rate*sps
        self.rx_gain_ui = rx_gain_ui = rx_gain
        self.dl_freq_ui = dl_freq_ui = dl_freq

        ##################################################
        # Blocks
        ##################################################
        self._tx_gain_ui_range = Range(0, 60, 1, tx_gain, 200)
        self._tx_gain_ui_win = RangeWidget(self._tx_gain_ui_range, self.set_tx_gain_ui, "Transmit Gain (dB)", "counter_slider", float)
        self.top_grid_layout.addWidget(self._tx_gain_ui_win)
        self._squelch_ui_range = Range(-70, -30, 1, -50, 200)
        self._squelch_ui_win = RangeWidget(self._squelch_ui_range, self.set_squelch_ui, "squelch", "counter_slider", float)
        self.top_grid_layout.addWidget(self._squelch_ui_win)
        self._rx_gain_ui_range = Range(0, 60, 1, rx_gain, 200)
        self._rx_gain_ui_win = RangeWidget(self._rx_gain_ui_range, self.set_rx_gain_ui, "Recieve Gain (dB)", "counter_slider", float)
        self.top_grid_layout.addWidget(self._rx_gain_ui_win)
        self._ul_freq_ui_tool_bar = Qt.QToolBar(self)
        self._ul_freq_ui_tool_bar.addWidget(Qt.QLabel('ul_freq_ui' + ": "))
        self._ul_freq_ui_line_edit = Qt.QLineEdit(str(self.ul_freq_ui))
        self._ul_freq_ui_tool_bar.addWidget(self._ul_freq_ui_line_edit)
        self._ul_freq_ui_line_edit.returnPressed.connect(
            lambda: self.set_ul_freq_ui(eng_notation.str_to_num(str(self._ul_freq_ui_line_edit.text()))))
        self.top_grid_layout.addWidget(self._ul_freq_ui_tool_bar)
        self.trxvu_bpsk_data_recovery_0 = trxvu_bpsk_data_recovery()
        self.trxvu_bpsk_carrier_symbol_rec_0 = trxvu_bpsk_carrier_symbol_rec(
            sps=sps,
        )
        self.trxv_uplink_fsk_modulator_0 = trxv_uplink_fsk_modulator(
            samp_rate=samp_rate,
            sps=sps,
        )
        self.qtgui_waterfall_sink_x_0 = qtgui.waterfall_sink_c(
            1024, #size
            firdes.WIN_BLACKMAN_hARRIS, #wintype
            ul_freq, #fc
            10000, #bw
            "", #name
            1 #number of inputs
        )
        self.qtgui_waterfall_sink_x_0.set_update_time(0.10)
        self.qtgui_waterfall_sink_x_0.enable_grid(False)
        self.qtgui_waterfall_sink_x_0.enable_axis_labels(True)



        labels = ['', '', '', '', '',
                  '', '', '', '', '']
        colors = [0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_waterfall_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_waterfall_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_waterfall_sink_x_0.set_color_map(i, colors[i])
            self.qtgui_waterfall_sink_x_0.set_line_alpha(i, alphas[i])

        self.qtgui_waterfall_sink_x_0.set_intensity_range(-110, -20)

        self._qtgui_waterfall_sink_x_0_win = sip.wrapinstance(self.qtgui_waterfall_sink_x_0.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_waterfall_sink_x_0_win)
        self.qtgui_time_sink_x_0 = qtgui.time_sink_f(
            1024, #size
            samp_rate, #samp_rate
            "Baseband Waveform (In-Phase Component)", #name
            1 #number of inputs
        )
        self.qtgui_time_sink_x_0.set_update_time(0.10)
        self.qtgui_time_sink_x_0.set_y_axis(-1, 1)

        self.qtgui_time_sink_x_0.set_y_label('Amplitude', "")

        self.qtgui_time_sink_x_0.enable_tags(True)
        self.qtgui_time_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.qtgui_time_sink_x_0.enable_autoscale(False)
        self.qtgui_time_sink_x_0.enable_grid(False)
        self.qtgui_time_sink_x_0.enable_axis_labels(True)
        self.qtgui_time_sink_x_0.enable_control_panel(False)
        self.qtgui_time_sink_x_0.enable_stem_plot(False)


        labels = ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_time_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_time_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_time_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_time_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_time_sink_x_0.set_line_style(i, styles[i])
            self.qtgui_time_sink_x_0.set_line_marker(i, markers[i])
            self.qtgui_time_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_time_sink_x_0_win = sip.wrapinstance(self.qtgui_time_sink_x_0.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_time_sink_x_0_win)
        self.qtgui_freq_sink_x_1 = qtgui.freq_sink_c(
            1024, #size
            firdes.WIN_BLACKMAN_hARRIS, #wintype
            dl_freq, #fc
            samp_rate, #bw
            'RX', #name
            1
        )
        self.qtgui_freq_sink_x_1.set_update_time(0.10)
        self.qtgui_freq_sink_x_1.set_y_axis(-140, 10)
        self.qtgui_freq_sink_x_1.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_1.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_1.enable_autoscale(False)
        self.qtgui_freq_sink_x_1.enable_grid(False)
        self.qtgui_freq_sink_x_1.set_fft_average(1.0)
        self.qtgui_freq_sink_x_1.enable_axis_labels(True)
        self.qtgui_freq_sink_x_1.enable_control_panel(False)



        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_freq_sink_x_1.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_1.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_1.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_1.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_1.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_1_win = sip.wrapinstance(self.qtgui_freq_sink_x_1.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_freq_sink_x_1_win)
        self.qtgui_freq_sink_x_0 = qtgui.freq_sink_c(
            1024, #size
            firdes.WIN_BLACKMAN_hARRIS, #wintype
            ul_freq, #fc
            samp_rate, #bw
            "Transmitted Uplink Spectrum", #name
            1
        )
        self.qtgui_freq_sink_x_0.set_update_time(0.10)
        self.qtgui_freq_sink_x_0.set_y_axis(-140, 10)
        self.qtgui_freq_sink_x_0.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0.enable_autoscale(False)
        self.qtgui_freq_sink_x_0.enable_grid(False)
        self.qtgui_freq_sink_x_0.set_fft_average(1.0)
        self.qtgui_freq_sink_x_0.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0.enable_control_panel(False)



        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_freq_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_freq_sink_x_0_win)
        self.qtgui_const_sink_x_0 = qtgui.const_sink_c(
            256, #size
            "Received Signal Constellation", #name
            1 #number of inputs
        )
        self.qtgui_const_sink_x_0.set_update_time(0.025)
        self.qtgui_const_sink_x_0.set_y_axis(-1.5, 1.5)
        self.qtgui_const_sink_x_0.set_x_axis(-1.5, 1.5)
        self.qtgui_const_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.qtgui_const_sink_x_0.enable_autoscale(False)
        self.qtgui_const_sink_x_0.enable_grid(True)
        self.qtgui_const_sink_x_0.enable_axis_labels(True)


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "red", "red", "red",
            "red", "red", "red", "red", "red"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_const_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_const_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_const_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_const_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_const_sink_x_0.set_line_style(i, styles[i])
            self.qtgui_const_sink_x_0.set_line_marker(i, markers[i])
            self.qtgui_const_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_const_sink_x_0_win = sip.wrapinstance(self.qtgui_const_sink_x_0.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_const_sink_x_0_win)
        self.nrzs_line_coding_0 = nrzs_line_coding()
        self.limesdr_source_0 = limesdr.source('0009083401881019', 0, '')


        self.limesdr_source_0.set_sample_rate(samp_rate)


        self.limesdr_source_0.set_center_freq(dl_freq, 0)

        self.limesdr_source_0.set_bandwidth(1.5e6, 0)


        self.limesdr_source_0.set_digital_filter(samp_rate, 0)


        self.limesdr_source_0.set_gain(rx_gain_ui, 0)


        self.limesdr_source_0.set_antenna(2, 0)


        self.limesdr_source_0.calibrate(2.5e6, 0)
        self.limesdr_sink_0 = limesdr.sink('0009083401881019', 0, '', '')


        self.limesdr_sink_0.set_sample_rate(samp_rate)


        self.limesdr_sink_0.set_center_freq(ul_freq, 0)

        self.limesdr_sink_0.set_bandwidth(5e6, 0)


        self.limesdr_sink_0.set_digital_filter(samp_rate, 0)


        self.limesdr_sink_0.set_gain(tx_gain_ui, 0)


        self.limesdr_sink_0.set_antenna(255, 0)


        self.limesdr_sink_0.calibrate(2.5e6, 0)
        self.hdlc_framer_with_preamble_0 = hdlc_framer_with_preamble(
            num_postamble_bytes=10,
            num_preamble_bytes=20,
        )
        self._dl_freq_ui_tool_bar = Qt.QToolBar(self)
        self._dl_freq_ui_tool_bar.addWidget(Qt.QLabel('dl_freq_ui' + ": "))
        self._dl_freq_ui_line_edit = Qt.QLineEdit(str(self.dl_freq_ui))
        self._dl_freq_ui_tool_bar.addWidget(self._dl_freq_ui_line_edit)
        self._dl_freq_ui_line_edit.returnPressed.connect(
            lambda: self.set_dl_freq_ui(eng_notation.str_to_num(str(self._dl_freq_ui_line_edit.text()))))
        self.top_grid_layout.addWidget(self._dl_freq_ui_tool_bar)
        self.digital_scrambler_bb_0 = digital.scrambler_bb(0x21, 0x00, 16)
        self.digital_hdlc_deframer_bp_0 = digital.hdlc_deframer_bp(10, 250)
        self.blocks_socket_pdu_0_0 = blocks.socket_pdu('UDP_SERVER', '127.0.0.1', '27001', 1000, False)
        self.blocks_socket_pdu_0 = blocks.socket_pdu('UDP_CLIENT', '127.0.0.1', '27000', 10000, False)
        self.blocks_message_debug_1 = blocks.message_debug()
        self.blocks_message_debug_0 = blocks.message_debug()
        self.analog_simple_squelch_cc_1 = analog.simple_squelch_cc(squelch_ui, 1)



        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.blocks_socket_pdu_0, 'pdus'), (self.blocks_message_debug_1, 'print_pdu'))
        self.msg_connect((self.blocks_socket_pdu_0_0, 'pdus'), (self.blocks_message_debug_0, 'print_pdu'))
        self.msg_connect((self.blocks_socket_pdu_0_0, 'pdus'), (self.hdlc_framer_with_preamble_0, 'in'))
        self.msg_connect((self.digital_hdlc_deframer_bp_0, 'out'), (self.blocks_socket_pdu_0, 'pdus'))
        self.connect((self.analog_simple_squelch_cc_1, 0), (self.trxvu_bpsk_carrier_symbol_rec_0, 0))
        self.connect((self.digital_scrambler_bb_0, 0), (self.trxv_uplink_fsk_modulator_0, 0))
        self.connect((self.hdlc_framer_with_preamble_0, 0), (self.nrzs_line_coding_0, 0))
        self.connect((self.limesdr_source_0, 0), (self.analog_simple_squelch_cc_1, 0))
        self.connect((self.limesdr_source_0, 0), (self.qtgui_freq_sink_x_1, 0))
        self.connect((self.nrzs_line_coding_0, 0), (self.digital_scrambler_bb_0, 0))
        self.connect((self.trxv_uplink_fsk_modulator_0, 0), (self.limesdr_sink_0, 0))
        self.connect((self.trxv_uplink_fsk_modulator_0, 0), (self.qtgui_freq_sink_x_0, 0))
        self.connect((self.trxv_uplink_fsk_modulator_0, 0), (self.qtgui_waterfall_sink_x_0, 0))
        self.connect((self.trxvu_bpsk_carrier_symbol_rec_0, 0), (self.qtgui_const_sink_x_0, 0))
        self.connect((self.trxvu_bpsk_carrier_symbol_rec_0, 1), (self.qtgui_time_sink_x_0, 0))
        self.connect((self.trxvu_bpsk_carrier_symbol_rec_0, 0), (self.trxvu_bpsk_data_recovery_0, 0))
        self.connect((self.trxvu_bpsk_data_recovery_0, 0), (self.digital_hdlc_deframer_bp_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "Ground_PC_2025_v1")
        self.settings.setValue("geometry", self.saveGeometry())
        event.accept()

    def get_baud_rate(self):
        return self.baud_rate

    def set_baud_rate(self, baud_rate):
        self.baud_rate = baud_rate
        self.set_samp_rate(self.baud_rate*self.sps)

    def get_dl_freq(self):
        return self.dl_freq

    def set_dl_freq(self, dl_freq):
        self.dl_freq = dl_freq
        self.set_dl_freq_ui(self.dl_freq)
        self.limesdr_source_0.set_center_freq(self.dl_freq, 0)
        self.qtgui_freq_sink_x_1.set_frequency_range(self.dl_freq, self.samp_rate)

    def get_rx_gain(self):
        return self.rx_gain

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain
        self.set_rx_gain_ui(self.rx_gain)

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.set_samp_rate(self.baud_rate*self.sps)
        self.trxv_uplink_fsk_modulator_0.set_sps(self.sps)
        self.trxvu_bpsk_carrier_symbol_rec_0.set_sps(self.sps)

    def get_tx_gain(self):
        return self.tx_gain

    def set_tx_gain(self, tx_gain):
        self.tx_gain = tx_gain
        self.set_tx_gain_ui(self.tx_gain)

    def get_ul_freq(self):
        return self.ul_freq

    def set_ul_freq(self, ul_freq):
        self.ul_freq = ul_freq
        self.set_ul_freq_ui(self.ul_freq)
        self.limesdr_sink_0.set_center_freq(self.ul_freq, 0)
        self.qtgui_freq_sink_x_0.set_frequency_range(self.ul_freq, self.samp_rate)
        self.qtgui_waterfall_sink_x_0.set_frequency_range(self.ul_freq, 10000)

    def get_ul_freq_ui(self):
        return self.ul_freq_ui

    def set_ul_freq_ui(self, ul_freq_ui):
        self.ul_freq_ui = ul_freq_ui
        Qt.QMetaObject.invokeMethod(self._ul_freq_ui_line_edit, "setText", Qt.Q_ARG("QString", eng_notation.num_to_str(self.ul_freq_ui)))

    def get_tx_gain_ui(self):
        return self.tx_gain_ui

    def set_tx_gain_ui(self, tx_gain_ui):
        self.tx_gain_ui = tx_gain_ui
        self.limesdr_sink_0.set_gain(self.tx_gain_ui, 0)

    def get_squelch_ui(self):
        return self.squelch_ui

    def set_squelch_ui(self, squelch_ui):
        self.squelch_ui = squelch_ui
        self.analog_simple_squelch_cc_1.set_threshold(self.squelch_ui)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.limesdr_sink_0.set_digital_filter(self.samp_rate, 0)
        self.limesdr_sink_0.set_digital_filter(self.samp_rate, 1)
        self.limesdr_source_0.set_digital_filter(self.samp_rate, 0)
        self.limesdr_source_0.set_digital_filter(self.samp_rate, 1)
        self.qtgui_freq_sink_x_0.set_frequency_range(self.ul_freq, self.samp_rate)
        self.qtgui_freq_sink_x_1.set_frequency_range(self.dl_freq, self.samp_rate)
        self.qtgui_time_sink_x_0.set_samp_rate(self.samp_rate)
        self.trxv_uplink_fsk_modulator_0.set_samp_rate(self.samp_rate)

    def get_rx_gain_ui(self):
        return self.rx_gain_ui

    def set_rx_gain_ui(self, rx_gain_ui):
        self.rx_gain_ui = rx_gain_ui
        self.limesdr_source_0.set_gain(self.rx_gain_ui, 0)

    def get_dl_freq_ui(self):
        return self.dl_freq_ui

    def set_dl_freq_ui(self, dl_freq_ui):
        self.dl_freq_ui = dl_freq_ui
        Qt.QMetaObject.invokeMethod(self._dl_freq_ui_line_edit, "setText", Qt.Q_ARG("QString", eng_notation.num_to_str(self.dl_freq_ui)))




def argument_parser():
    parser = ArgumentParser()
    parser.add_argument(
        "--baud-rate", dest="baud_rate", type=intx, default=9600,
        help="Set baud_rate [default=%(default)r]")
    parser.add_argument(
        "--dl-freq", dest="dl_freq", type=eng_float, default="145.91M",
        help="Set DL_Freq [default=%(default)r]")
    parser.add_argument(
        "--sps", dest="sps", type=intx, default=20,
        help="Set sps [default=%(default)r]")
    parser.add_argument(
        "--ul-freq", dest="ul_freq", type=eng_float, default="436.83M",
        help="Set UL_Freq [default=%(default)r]")
    return parser


def main(top_block_cls=Ground_PC_2025_v1, options=None):
    if options is None:
        options = argument_parser().parse_args()

    if StrictVersion("4.5.0") <= StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
        style = gr.prefs().get_string('qtgui', 'style', 'raster')
        Qt.QApplication.setGraphicsSystem(style)
    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls(baud_rate=options.baud_rate, dl_freq=options.dl_freq, sps=options.sps, ul_freq=options.ul_freq)

    tb.start()

    tb.show()

    def sig_handler(sig=None, frame=None):
        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    def quitting():
        tb.stop()
        tb.wait()

    qapp.aboutToQuit.connect(quitting)
    qapp.exec_()

if __name__ == '__main__':
    main()
