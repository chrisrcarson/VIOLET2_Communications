#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: LimeSDR Ground Software
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
import math
from gnuradio import blocks
from gnuradio import digital
from gnuradio import filter
from gnuradio import gr
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio.qtgui import Range, RangeWidget
from hdlc_framer_with_preamble import hdlc_framer_with_preamble  # grc-generated hier_block
from math import pi
from nrzs_line_coding import nrzs_line_coding  # grc-generated hier_block
import limesdr

from gnuradio import qtgui

class LimeSDR(gr.top_block, Qt.QWidget):

    def __init__(self, baud_rate=1200, dl_freq=145.91e6, rx_gain=56, sps=160, tx_gain=56, ul_freq=436830000):
        gr.top_block.__init__(self, "LimeSDR Ground Software")
        Qt.QWidget.__init__(self)
        self.setWindowTitle("LimeSDR Ground Software")
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

        self.settings = Qt.QSettings("GNU Radio", "LimeSDR")

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
        self._ul_freq_ui_tool_bar = Qt.QToolBar(self)
        self._ul_freq_ui_tool_bar.addWidget(Qt.QLabel('ul_freq_ui' + ": "))
        self._ul_freq_ui_line_edit = Qt.QLineEdit(str(self.ul_freq_ui))
        self._ul_freq_ui_tool_bar.addWidget(self._ul_freq_ui_line_edit)
        self._ul_freq_ui_line_edit.returnPressed.connect(
            lambda: self.set_ul_freq_ui(eng_notation.str_to_num(str(self._ul_freq_ui_line_edit.text()))))
        self.top_grid_layout.addWidget(self._ul_freq_ui_tool_bar)
        self._rx_gain_ui_range = Range(0, 60, 1, rx_gain, 200)
        self._rx_gain_ui_win = RangeWidget(self._rx_gain_ui_range, self.set_rx_gain_ui, "Recieve Gain (dB)", "counter_slider", float)
        self.top_grid_layout.addWidget(self._rx_gain_ui_win)
        self.root_raised_cosine_filter_1 = filter.fir_filter_fff(
            1,
            firdes.root_raised_cosine(
                1,
                sps,
                1,
                0.35,
                sps*7))
        self.root_raised_cosine_filter_0 = filter.interp_fir_filter_fff(
            sps,
            firdes.root_raised_cosine(
                sps,
                sps,
                1.0,
                0.35,
                sps*7))
        self.qtgui_waterfall_sink_x_1 = qtgui.waterfall_sink_f(
            1024, #size
            firdes.WIN_HAMMING, #wintype
            dl_freq, #fc
            10000, #bw
            "RX Out", #name
            1 #number of inputs
        )
        self.qtgui_waterfall_sink_x_1.set_update_time(0.10)
        self.qtgui_waterfall_sink_x_1.enable_grid(False)
        self.qtgui_waterfall_sink_x_1.enable_axis_labels(True)


        self.qtgui_waterfall_sink_x_1.set_plot_pos_half(not True)

        labels = ['', '', '', '', '',
                  '', '', '', '', '']
        colors = [0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_waterfall_sink_x_1.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_waterfall_sink_x_1.set_line_label(i, labels[i])
            self.qtgui_waterfall_sink_x_1.set_color_map(i, colors[i])
            self.qtgui_waterfall_sink_x_1.set_line_alpha(i, alphas[i])

        self.qtgui_waterfall_sink_x_1.set_intensity_range(-140, 10)

        self._qtgui_waterfall_sink_x_1_win = sip.wrapinstance(self.qtgui_waterfall_sink_x_1.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_waterfall_sink_x_1_win)
        self.qtgui_waterfall_sink_x_0_1 = qtgui.waterfall_sink_c(
            1024, #size
            firdes.WIN_BLACKMAN_hARRIS, #wintype
            ul_freq, #fc
            10000, #bw
            "TX Sink", #name
            1 #number of inputs
        )
        self.qtgui_waterfall_sink_x_0_1.set_update_time(0.10)
        self.qtgui_waterfall_sink_x_0_1.enable_grid(False)
        self.qtgui_waterfall_sink_x_0_1.enable_axis_labels(True)



        labels = ['', '', '', '', '',
                  '', '', '', '', '']
        colors = [0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_waterfall_sink_x_0_1.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_waterfall_sink_x_0_1.set_line_label(i, labels[i])
            self.qtgui_waterfall_sink_x_0_1.set_color_map(i, colors[i])
            self.qtgui_waterfall_sink_x_0_1.set_line_alpha(i, alphas[i])

        self.qtgui_waterfall_sink_x_0_1.set_intensity_range(-110, -20)

        self._qtgui_waterfall_sink_x_0_1_win = sip.wrapinstance(self.qtgui_waterfall_sink_x_0_1.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_waterfall_sink_x_0_1_win)
        self.qtgui_waterfall_sink_x_0_0 = qtgui.waterfall_sink_c(
            1024, #size
            firdes.WIN_BLACKMAN_hARRIS, #wintype
            dl_freq, #fc
            10000, #bw
            "RX Source", #name
            1 #number of inputs
        )
        self.qtgui_waterfall_sink_x_0_0.set_update_time(0.10)
        self.qtgui_waterfall_sink_x_0_0.enable_grid(False)
        self.qtgui_waterfall_sink_x_0_0.enable_axis_labels(True)



        labels = ['', '', '', '', '',
                  '', '', '', '', '']
        colors = [0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_waterfall_sink_x_0_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_waterfall_sink_x_0_0.set_line_label(i, labels[i])
            self.qtgui_waterfall_sink_x_0_0.set_color_map(i, colors[i])
            self.qtgui_waterfall_sink_x_0_0.set_line_alpha(i, alphas[i])

        self.qtgui_waterfall_sink_x_0_0.set_intensity_range(-140, 10)

        self._qtgui_waterfall_sink_x_0_0_win = sip.wrapinstance(self.qtgui_waterfall_sink_x_0_0.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_waterfall_sink_x_0_0_win)
        self.qtgui_freq_sink_x_0_1 = qtgui.freq_sink_c(
            1024, #size
            firdes.WIN_BLACKMAN_hARRIS, #wintype
            ul_freq, #fc
            10000, #bw
            "Transmitted Uplink Spectrum", #name
            1
        )
        self.qtgui_freq_sink_x_0_1.set_update_time(0.10)
        self.qtgui_freq_sink_x_0_1.set_y_axis(-140, 10)
        self.qtgui_freq_sink_x_0_1.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_0_1.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0_1.enable_autoscale(False)
        self.qtgui_freq_sink_x_0_1.enable_grid(False)
        self.qtgui_freq_sink_x_0_1.set_fft_average(0.05)
        self.qtgui_freq_sink_x_0_1.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0_1.enable_control_panel(False)



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
                self.qtgui_freq_sink_x_0_1.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0_1.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0_1.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0_1.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0_1.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_1_win = sip.wrapinstance(self.qtgui_freq_sink_x_0_1.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_freq_sink_x_0_1_win)
        self.qtgui_freq_sink_x_0_0_0_0 = qtgui.freq_sink_f(
            1024, #size
            firdes.WIN_BLACKMAN_hARRIS, #wintype
            dl_freq, #fc
            50000, #bw
            'Post RRC', #name
            1
        )
        self.qtgui_freq_sink_x_0_0_0_0.set_update_time(0.10)
        self.qtgui_freq_sink_x_0_0_0_0.set_y_axis(-100, 10)
        self.qtgui_freq_sink_x_0_0_0_0.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_0_0_0_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0_0_0_0.enable_autoscale(False)
        self.qtgui_freq_sink_x_0_0_0_0.enable_grid(False)
        self.qtgui_freq_sink_x_0_0_0_0.set_fft_average(1.0)
        self.qtgui_freq_sink_x_0_0_0_0.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0_0_0_0.enable_control_panel(False)


        self.qtgui_freq_sink_x_0_0_0_0.set_plot_pos_half(not True)

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
                self.qtgui_freq_sink_x_0_0_0_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0_0_0_0.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0_0_0_0.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0_0_0_0.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0_0_0_0.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_0_0_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0_0_0_0.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_freq_sink_x_0_0_0_0_win)
        self.qtgui_freq_sink_x_0_0_0 = qtgui.freq_sink_c(
            1024, #size
            firdes.WIN_BLACKMAN_hARRIS, #wintype
            dl_freq, #fc
            50000, #bw
            'RX source', #name
            1
        )
        self.qtgui_freq_sink_x_0_0_0.set_update_time(0.10)
        self.qtgui_freq_sink_x_0_0_0.set_y_axis(-100, 10)
        self.qtgui_freq_sink_x_0_0_0.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_0_0_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0_0_0.enable_autoscale(False)
        self.qtgui_freq_sink_x_0_0_0.enable_grid(False)
        self.qtgui_freq_sink_x_0_0_0.set_fft_average(1.0)
        self.qtgui_freq_sink_x_0_0_0.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0_0_0.enable_control_panel(False)



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
                self.qtgui_freq_sink_x_0_0_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0_0_0.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0_0_0.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0_0_0.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0_0_0.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_0_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0_0_0.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_freq_sink_x_0_0_0_win)
        self.qtgui_freq_sink_x_0_0 = qtgui.freq_sink_f(
            1024, #size
            firdes.WIN_BLACKMAN_hARRIS, #wintype
            dl_freq, #fc
            10000, #bw
            'RX FIN', #name
            1
        )
        self.qtgui_freq_sink_x_0_0.set_update_time(0.10)
        self.qtgui_freq_sink_x_0_0.set_y_axis(-60, 10)
        self.qtgui_freq_sink_x_0_0.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_0_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0_0.enable_autoscale(False)
        self.qtgui_freq_sink_x_0_0.enable_grid(False)
        self.qtgui_freq_sink_x_0_0.set_fft_average(1.0)
        self.qtgui_freq_sink_x_0_0.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0_0.enable_control_panel(False)


        self.qtgui_freq_sink_x_0_0.set_plot_pos_half(not True)

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
                self.qtgui_freq_sink_x_0_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0_0.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0_0.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0_0.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0_0.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0_0.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_freq_sink_x_0_0_win)
        self.nrzs_line_coding_0_0 = nrzs_line_coding()
        self.limesdr_source_0 = limesdr.source('0009083401881019', 0, '')


        self.limesdr_source_0.set_sample_rate(baud_rate*sps)


        self.limesdr_source_0.set_center_freq(dl_freq, 0)

        self.limesdr_source_0.set_bandwidth(1.5e6, 0)




        self.limesdr_source_0.set_gain(rx_gain, 0)


        self.limesdr_source_0.set_antenna(2, 0)


        self.limesdr_source_0.calibrate(2.5e6, 0)


        self.limesdr_source_0.set_nco(1,0)
        self.limesdr_sink_0_0 = limesdr.sink('0009083401881019', 0, '', '')


        self.limesdr_sink_0_0.set_sample_rate(samp_rate)


        self.limesdr_sink_0_0.set_center_freq(ul_freq, 0)

        self.limesdr_sink_0_0.set_bandwidth(5e6, 0)


        self.limesdr_sink_0_0.set_digital_filter(samp_rate, 0)


        self.limesdr_sink_0_0.set_gain(tx_gain_ui, 0)


        self.limesdr_sink_0_0.set_antenna(255, 0)


        self.limesdr_sink_0_0.calibrate(2.5e6, 0)
        self.hdlc_framer_with_preamble_0_0 = hdlc_framer_with_preamble(
            num_postamble_bytes=20,
            num_preamble_bytes=20,
        )
        self._dl_freq_ui_tool_bar = Qt.QToolBar(self)
        self._dl_freq_ui_tool_bar.addWidget(Qt.QLabel('dl_freq_ui' + ": "))
        self._dl_freq_ui_line_edit = Qt.QLineEdit(str(self.dl_freq_ui))
        self._dl_freq_ui_tool_bar.addWidget(self._dl_freq_ui_line_edit)
        self._dl_freq_ui_line_edit.returnPressed.connect(
            lambda: self.set_dl_freq_ui(eng_notation.str_to_num(str(self._dl_freq_ui_line_edit.text()))))
        self.top_grid_layout.addWidget(self._dl_freq_ui_tool_bar)
        self.digital_symbol_sync_xx_0 = digital.symbol_sync_ff(
            digital.TED_SIGNUM_TIMES_SLOPE_ML,
            sps,
            0.045,
            1.0,
            1.0,
            1.5,
            1,
            digital.constellation_bpsk().base(),
            digital.IR_MMSE_8TAP,
            128,
            [])
        self.digital_scrambler_bb_0_0 = digital.scrambler_bb(0x21, 0x00, 16)
        self.digital_hdlc_deframer_bp_0 = digital.hdlc_deframer_bp(116, 272)
        self.digital_diff_decoder_bb_0 = digital.diff_decoder_bb(2)
        self.digital_descrambler_bb_0 = digital.descrambler_bb(0x21, 0, 16)
        self.digital_correlate_access_code_tag_xx_0 = digital.correlate_access_code_tag_bb('01111110', 0, '')
        self.digital_chunks_to_symbols_xx_1 = digital.chunks_to_symbols_bf([-1.0, 1.0], 1)
        self.digital_binary_slicer_fb_0 = digital.binary_slicer_fb()
        self.blocks_tagged_stream_multiply_length_0 = blocks.tagged_stream_multiply_length(gr.sizeof_float*1, "packet_len", 160)
        self.blocks_socket_pdu_1 = blocks.socket_pdu('UDP_CLIENT', '127.0.0.1', '27000', 10000, False)
        self.blocks_socket_pdu_0_0_0 = blocks.socket_pdu('UDP_SERVER', '127.0.0.1', '27001', 1000, False)
        self.blocks_pdu_to_tagged_stream_0 = blocks.pdu_to_tagged_stream(blocks.byte_t, 'packet_len')
        self.blocks_not_xx_0_0 = blocks.not_bb()
        self.blocks_message_debug_1 = blocks.message_debug()
        self.blocks_message_debug_0 = blocks.message_debug()
        self.blocks_file_sink_0 = blocks.file_sink(gr.sizeof_char*1, '/home/eceuser/CubeSat-NB/VIOLET2_Communications/FSK/rx_fin_bits.hex', False)
        self.blocks_file_sink_0.set_unbuffered(False)
        self.blocks_char_to_float_0 = blocks.char_to_float(1, 1)
        self.blocks_and_const_xx_0_0 = blocks.and_const_bb(1)
        self.analog_simple_squelch_cc_0 = analog.simple_squelch_cc(squelch_ui, 1)
        self.analog_quadrature_demod_cf_0 = analog.quadrature_demod_cf(samp_rate/(2*math.pi*35000))
        self.analog_frequency_modulator_fc_0 = analog.frequency_modulator_fc(2.0*3.14159*35000.0/float(samp_rate))
        self.analog_agc_xx_0 = analog.agc_cc(1e-3, 1.0, 1.0)
        self.analog_agc_xx_0.set_max_gain(65536)



        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.blocks_socket_pdu_0_0_0, 'pdus'), (self.blocks_message_debug_0, 'print_pdu'))
        self.msg_connect((self.blocks_socket_pdu_0_0_0, 'pdus'), (self.hdlc_framer_with_preamble_0_0, 'in'))
        self.msg_connect((self.digital_hdlc_deframer_bp_0, 'out'), (self.blocks_message_debug_1, 'print_pdu'))
        self.msg_connect((self.digital_hdlc_deframer_bp_0, 'out'), (self.blocks_pdu_to_tagged_stream_0, 'pdus'))
        self.msg_connect((self.digital_hdlc_deframer_bp_0, 'out'), (self.blocks_socket_pdu_1, 'pdus'))
        self.connect((self.analog_agc_xx_0, 0), (self.analog_quadrature_demod_cf_0, 0))
        self.connect((self.analog_frequency_modulator_fc_0, 0), (self.limesdr_sink_0_0, 0))
        self.connect((self.analog_frequency_modulator_fc_0, 0), (self.qtgui_freq_sink_x_0_1, 0))
        self.connect((self.analog_frequency_modulator_fc_0, 0), (self.qtgui_waterfall_sink_x_0_1, 0))
        self.connect((self.analog_quadrature_demod_cf_0, 0), (self.root_raised_cosine_filter_1, 0))
        self.connect((self.analog_simple_squelch_cc_0, 0), (self.analog_agc_xx_0, 0))
        self.connect((self.blocks_and_const_xx_0_0, 0), (self.blocks_char_to_float_0, 0))
        self.connect((self.blocks_and_const_xx_0_0, 0), (self.digital_correlate_access_code_tag_xx_0, 0))
        self.connect((self.blocks_char_to_float_0, 0), (self.qtgui_freq_sink_x_0_0, 0))
        self.connect((self.blocks_char_to_float_0, 0), (self.qtgui_waterfall_sink_x_1, 0))
        self.connect((self.blocks_not_xx_0_0, 0), (self.blocks_and_const_xx_0_0, 0))
        self.connect((self.blocks_pdu_to_tagged_stream_0, 0), (self.blocks_file_sink_0, 0))
        self.connect((self.blocks_tagged_stream_multiply_length_0, 0), (self.analog_frequency_modulator_fc_0, 0))
        self.connect((self.digital_binary_slicer_fb_0, 0), (self.digital_diff_decoder_bb_0, 0))
        self.connect((self.digital_chunks_to_symbols_xx_1, 0), (self.root_raised_cosine_filter_0, 0))
        self.connect((self.digital_correlate_access_code_tag_xx_0, 0), (self.digital_hdlc_deframer_bp_0, 0))
        self.connect((self.digital_descrambler_bb_0, 0), (self.blocks_not_xx_0_0, 0))
        self.connect((self.digital_diff_decoder_bb_0, 0), (self.digital_descrambler_bb_0, 0))
        self.connect((self.digital_scrambler_bb_0_0, 0), (self.digital_chunks_to_symbols_xx_1, 0))
        self.connect((self.digital_symbol_sync_xx_0, 0), (self.digital_binary_slicer_fb_0, 0))
        self.connect((self.hdlc_framer_with_preamble_0_0, 0), (self.nrzs_line_coding_0_0, 0))
        self.connect((self.limesdr_source_0, 0), (self.analog_simple_squelch_cc_0, 0))
        self.connect((self.limesdr_source_0, 0), (self.qtgui_freq_sink_x_0_0_0, 0))
        self.connect((self.limesdr_source_0, 0), (self.qtgui_waterfall_sink_x_0_0, 0))
        self.connect((self.nrzs_line_coding_0_0, 0), (self.digital_scrambler_bb_0_0, 0))
        self.connect((self.root_raised_cosine_filter_0, 0), (self.blocks_tagged_stream_multiply_length_0, 0))
        self.connect((self.root_raised_cosine_filter_1, 0), (self.digital_symbol_sync_xx_0, 0))
        self.connect((self.root_raised_cosine_filter_1, 0), (self.qtgui_freq_sink_x_0_0_0_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "LimeSDR")
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
        self.qtgui_freq_sink_x_0_0.set_frequency_range(self.dl_freq, 10000)
        self.qtgui_freq_sink_x_0_0_0.set_frequency_range(self.dl_freq, 50000)
        self.qtgui_freq_sink_x_0_0_0_0.set_frequency_range(self.dl_freq, 50000)
        self.qtgui_waterfall_sink_x_0_0.set_frequency_range(self.dl_freq, 10000)
        self.qtgui_waterfall_sink_x_1.set_frequency_range(self.dl_freq, 10000)

    def get_rx_gain(self):
        return self.rx_gain

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain
        self.set_rx_gain_ui(self.rx_gain)
        self.limesdr_source_0.set_gain(self.rx_gain, 0)
        self.limesdr_source_0.set_gain(self.rx_gain, 1)

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.set_samp_rate(self.baud_rate*self.sps)
        self.root_raised_cosine_filter_0.set_taps(firdes.root_raised_cosine(self.sps, self.sps, 1.0, 0.35, self.sps*7))
        self.root_raised_cosine_filter_1.set_taps(firdes.root_raised_cosine(1, self.sps, 1, 0.35, self.sps*7))

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
        self.limesdr_sink_0_0.set_center_freq(self.ul_freq, 0)
        self.qtgui_freq_sink_x_0_1.set_frequency_range(self.ul_freq, 10000)
        self.qtgui_waterfall_sink_x_0_1.set_frequency_range(self.ul_freq, 10000)

    def get_ul_freq_ui(self):
        return self.ul_freq_ui

    def set_ul_freq_ui(self, ul_freq_ui):
        self.ul_freq_ui = ul_freq_ui
        Qt.QMetaObject.invokeMethod(self._ul_freq_ui_line_edit, "setText", Qt.Q_ARG("QString", eng_notation.num_to_str(self.ul_freq_ui)))

    def get_tx_gain_ui(self):
        return self.tx_gain_ui

    def set_tx_gain_ui(self, tx_gain_ui):
        self.tx_gain_ui = tx_gain_ui
        self.limesdr_sink_0_0.set_gain(self.tx_gain_ui, 0)

    def get_squelch_ui(self):
        return self.squelch_ui

    def set_squelch_ui(self, squelch_ui):
        self.squelch_ui = squelch_ui
        self.analog_simple_squelch_cc_0.set_threshold(self.squelch_ui)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.analog_frequency_modulator_fc_0.set_sensitivity(2.0*3.14159*35000.0/float(self.samp_rate))
        self.analog_quadrature_demod_cf_0.set_gain(self.samp_rate/(2*math.pi*35000))
        self.limesdr_sink_0_0.set_digital_filter(self.samp_rate, 0)
        self.limesdr_sink_0_0.set_digital_filter(self.samp_rate, 1)

    def get_rx_gain_ui(self):
        return self.rx_gain_ui

    def set_rx_gain_ui(self, rx_gain_ui):
        self.rx_gain_ui = rx_gain_ui

    def get_dl_freq_ui(self):
        return self.dl_freq_ui

    def set_dl_freq_ui(self, dl_freq_ui):
        self.dl_freq_ui = dl_freq_ui
        Qt.QMetaObject.invokeMethod(self._dl_freq_ui_line_edit, "setText", Qt.Q_ARG("QString", eng_notation.num_to_str(self.dl_freq_ui)))




def argument_parser():
    parser = ArgumentParser()
    parser.add_argument(
        "--baud-rate", dest="baud_rate", type=intx, default=1200,
        help="Set baud_rate [default=%(default)r]")
    parser.add_argument(
        "--dl-freq", dest="dl_freq", type=eng_float, default="145.91M",
        help="Set DL_Freq [default=%(default)r]")
    parser.add_argument(
        "--sps", dest="sps", type=intx, default=160,
        help="Set sps [default=%(default)r]")
    parser.add_argument(
        "--ul-freq", dest="ul_freq", type=eng_float, default="436.83M",
        help="Set UL_Freq [default=%(default)r]")
    return parser


def main(top_block_cls=LimeSDR, options=None):
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
