#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Doppler Sonar
# Author: Marcus Müller
# Copyright: 2023 Marcus Mülelr
# Description: Doppler sonar
# GNU Radio version: 3.10.9.2

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import analog
from gnuradio import audio
from gnuradio import blocks
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from math import pi
import sip



class doppler_sonar(gr.top_block, Qt.QWidget):

    def __init__(self, max_abs_speed=20, samp_rate=int(48e3)):
        gr.top_block.__init__(self, "Doppler Sonar", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Doppler Sonar")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
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
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "doppler_sonar")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)

        ##################################################
        # Parameters
        ##################################################
        self.max_abs_speed = max_abs_speed
        self.samp_rate = samp_rate

        ##################################################
        # Variables
        ##################################################
        self.v_sound = v_sound = 300
        self.f_0 = f_0 = 12e3
        self.doppler_max = doppler_max = max_abs_speed / v_sound * f_0
        self.transmit_gain = transmit_gain = -50
        self.bpf_taps = bpf_taps = firdes.complex_band_pass(1, samp_rate, f_0 - 2*doppler_max, f_0 + 2*doppler_max, 2*doppler_max, window.WIN_BLACKMAN, 6.76)

        ##################################################
        # Blocks
        ##################################################

        self._transmit_gain_range = qtgui.Range(-80, 0, 1, -50, 200)
        self._transmit_gain_win = qtgui.RangeWidget(self._transmit_gain_range, self.set_transmit_gain, "Output Gain [dB]", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._transmit_gain_win, 10, 0, 1, 4)
        for r in range(10, 11):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._f_0_range = qtgui.Range(50, samp_rate/2, 10, 12e3, 200)
        self._f_0_win = qtgui.RangeWidget(self._f_0_range, self.set_f_0, "Transmit Frequency [Hz]", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._f_0_win, 10, 4, 1, 4)
        for r in range(10, 11):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(4, 8):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_time_sink_x_0 = qtgui.time_sink_f(
            (samp_rate//16), #size
            samp_rate, #samp_rate
            "Frequency Estimate", #name
            2, #number of inputs
            None # parent
        )
        self.qtgui_time_sink_x_0.set_update_time(1/60)
        self.qtgui_time_sink_x_0.set_y_axis(max(0, f_0- 2*doppler_max), min(f_0 + 2*doppler_max, samp_rate/2))

        self.qtgui_time_sink_x_0.set_y_label('Amplitude', "")

        self.qtgui_time_sink_x_0.enable_tags(True)
        self.qtgui_time_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.qtgui_time_sink_x_0.enable_autoscale(False)
        self.qtgui_time_sink_x_0.enable_grid(False)
        self.qtgui_time_sink_x_0.enable_axis_labels(True)
        self.qtgui_time_sink_x_0.enable_control_panel(False)
        self.qtgui_time_sink_x_0.enable_stem_plot(False)


        labels = ['Reference', 'Received', 'Signal 3', 'Signal 4', 'Signal 5',
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


        for i in range(2):
            if len(labels[i]) == 0:
                self.qtgui_time_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_time_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_time_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_time_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_time_sink_x_0.set_line_style(i, styles[i])
            self.qtgui_time_sink_x_0.set_line_marker(i, markers[i])
            self.qtgui_time_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_time_sink_x_0_win = sip.wrapinstance(self.qtgui_time_sink_x_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_time_sink_x_0_win, 0, 4, 8, 4)
        for r in range(0, 8):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(4, 8):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_number_sink_0 = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_HORIZ,
            1,
            None # parent
        )
        self.qtgui_number_sink_0.set_update_time(0.10)
        self.qtgui_number_sink_0.set_title("Δf")

        labels = [" ", '', '', '', '',
            '', '', '', '', '']
        units = ["Hz", '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "white"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.qtgui_number_sink_0.set_min(i, -doppler_max)
            self.qtgui_number_sink_0.set_max(i, doppler_max)
            self.qtgui_number_sink_0.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.qtgui_number_sink_0.set_label(i, "Data {0}".format(i))
            else:
                self.qtgui_number_sink_0.set_label(i, labels[i])
            self.qtgui_number_sink_0.set_unit(i, units[i])
            self.qtgui_number_sink_0.set_factor(i, factor[i])

        self.qtgui_number_sink_0.enable_autoscale(False)
        self._qtgui_number_sink_0_win = sip.wrapinstance(self.qtgui_number_sink_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_number_sink_0_win, 8, 0, 1, 4)
        for r in range(8, 9):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_freq_sink_x_0 = qtgui.freq_sink_f(
            1024, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            samp_rate, #bw
            "Spectra", #name
            2,
            None # parent
        )
        self.qtgui_freq_sink_x_0.set_update_time((1/60))
        self.qtgui_freq_sink_x_0.set_y_axis((-(1.76 + 6.02*22)), 0)
        self.qtgui_freq_sink_x_0.set_y_label('Amplitude', 'dB Full Scale')
        self.qtgui_freq_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0.enable_autoscale(False)
        self.qtgui_freq_sink_x_0.enable_grid(False)
        self.qtgui_freq_sink_x_0.set_fft_average(1.0)
        self.qtgui_freq_sink_x_0.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0.enable_control_panel(False)
        self.qtgui_freq_sink_x_0.set_fft_window_normalized(False)

        self.qtgui_freq_sink_x_0.disable_legend()

        self.qtgui_freq_sink_x_0.set_plot_pos_half(not False)

        labels = ['Reference', 'Received', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(2):
            if len(labels[i]) == 0:
                self.qtgui_freq_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_freq_sink_x_0_win, 0, 0, 8, 4)
        for r in range(0, 8):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.fir_filter_xxx_0 = filter.fir_filter_fcc(1, bpf_taps)
        self.fir_filter_xxx_0.declare_sample_delay(0)
        self.blocks_sub_xx_0 = blocks.sub_ff(1)
        self.blocks_multiply_const_vxx_1_0_0 = blocks.multiply_const_ff((samp_rate/(2*pi)))
        self.blocks_multiply_const_vxx_1_0 = blocks.multiply_const_ff((samp_rate/(2*pi)))
        self.blocks_multiply_const_vxx_0 = blocks.multiply_const_ff((10**(transmit_gain/20)))
        self.blocks_moving_average_xx_0_0 = blocks.moving_average_ff((samp_rate//10), (1/(samp_rate//10)), 4000, 1)
        self.blocks_moving_average_xx_0 = blocks.moving_average_ff((samp_rate//10), (1/(samp_rate//10)), 4000, 1)
        self.blocks_complex_to_float_0_0 = blocks.complex_to_float(1)
        self.blocks_complex_to_float_0 = blocks.complex_to_float(1)
        self.audio_source_0 = audio.source(samp_rate, '', True)
        self.audio_sink_0 = audio.sink(samp_rate, '', True)
        self.analog_sig_source_x_0 = analog.sig_source_c(samp_rate, analog.GR_COS_WAVE, f_0, 1, 0, 0)
        self.analog_pll_freqdet_cf_0_0_0 = analog.pll_freqdet_cf(0.01, ((f_0 + doppler_max) / (samp_rate/(2*pi))), ((f_0 - doppler_max) / (samp_rate/(2*pi))))
        self.analog_pll_freqdet_cf_0_0 = analog.pll_freqdet_cf(0.01, ((f_0 + doppler_max)  /(samp_rate/(2*pi))), ((f_0 - doppler_max) / (samp_rate/(2*pi))))


        ##################################################
        # Connections
        ##################################################
        self.connect((self.analog_pll_freqdet_cf_0_0, 0), (self.blocks_moving_average_xx_0_0, 0))
        self.connect((self.analog_pll_freqdet_cf_0_0_0, 0), (self.blocks_moving_average_xx_0, 0))
        self.connect((self.analog_sig_source_x_0, 0), (self.analog_pll_freqdet_cf_0_0, 0))
        self.connect((self.analog_sig_source_x_0, 0), (self.blocks_complex_to_float_0, 0))
        self.connect((self.audio_source_0, 0), (self.fir_filter_xxx_0, 0))
        self.connect((self.blocks_complex_to_float_0, 0), (self.blocks_multiply_const_vxx_0, 0))
        self.connect((self.blocks_complex_to_float_0, 0), (self.qtgui_freq_sink_x_0, 0))
        self.connect((self.blocks_complex_to_float_0_0, 0), (self.qtgui_freq_sink_x_0, 1))
        self.connect((self.blocks_moving_average_xx_0, 0), (self.blocks_multiply_const_vxx_1_0_0, 0))
        self.connect((self.blocks_moving_average_xx_0_0, 0), (self.blocks_multiply_const_vxx_1_0, 0))
        self.connect((self.blocks_multiply_const_vxx_0, 0), (self.audio_sink_0, 0))
        self.connect((self.blocks_multiply_const_vxx_1_0, 0), (self.blocks_sub_xx_0, 0))
        self.connect((self.blocks_multiply_const_vxx_1_0, 0), (self.qtgui_time_sink_x_0, 0))
        self.connect((self.blocks_multiply_const_vxx_1_0_0, 0), (self.blocks_sub_xx_0, 1))
        self.connect((self.blocks_multiply_const_vxx_1_0_0, 0), (self.qtgui_time_sink_x_0, 1))
        self.connect((self.blocks_sub_xx_0, 0), (self.qtgui_number_sink_0, 0))
        self.connect((self.fir_filter_xxx_0, 0), (self.analog_pll_freqdet_cf_0_0_0, 0))
        self.connect((self.fir_filter_xxx_0, 0), (self.blocks_complex_to_float_0_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "doppler_sonar")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_max_abs_speed(self):
        return self.max_abs_speed

    def set_max_abs_speed(self, max_abs_speed):
        self.max_abs_speed = max_abs_speed
        self.set_doppler_max(self.max_abs_speed / self.v_sound * self.f_0)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.set_bpf_taps(firdes.complex_band_pass(1, self.samp_rate, self.f_0 - 2*self.doppler_max, self.f_0 + 2*self.doppler_max, 2*self.doppler_max, window.WIN_BLACKMAN, 6.76))
        self.analog_pll_freqdet_cf_0_0.set_max_freq(((self.f_0 + self.doppler_max)  /(self.samp_rate/(2*pi))))
        self.analog_pll_freqdet_cf_0_0.set_min_freq(((self.f_0 - self.doppler_max) / (self.samp_rate/(2*pi))))
        self.analog_pll_freqdet_cf_0_0_0.set_max_freq(((self.f_0 + self.doppler_max) / (self.samp_rate/(2*pi))))
        self.analog_pll_freqdet_cf_0_0_0.set_min_freq(((self.f_0 - self.doppler_max) / (self.samp_rate/(2*pi))))
        self.analog_sig_source_x_0.set_sampling_freq(self.samp_rate)
        self.blocks_moving_average_xx_0.set_length_and_scale((self.samp_rate//10), (1/(self.samp_rate//10)))
        self.blocks_moving_average_xx_0_0.set_length_and_scale((self.samp_rate//10), (1/(self.samp_rate//10)))
        self.blocks_multiply_const_vxx_1_0.set_k((self.samp_rate/(2*pi)))
        self.blocks_multiply_const_vxx_1_0_0.set_k((self.samp_rate/(2*pi)))
        self.qtgui_freq_sink_x_0.set_frequency_range(0, self.samp_rate)
        self.qtgui_time_sink_x_0.set_y_axis(max(0, self.f_0- 2*self.doppler_max), min(self.f_0 + 2*self.doppler_max, self.samp_rate/2))
        self.qtgui_time_sink_x_0.set_samp_rate(self.samp_rate)

    def get_v_sound(self):
        return self.v_sound

    def set_v_sound(self, v_sound):
        self.v_sound = v_sound
        self.set_doppler_max(self.max_abs_speed / self.v_sound * self.f_0)

    def get_f_0(self):
        return self.f_0

    def set_f_0(self, f_0):
        self.f_0 = f_0
        self.set_bpf_taps(firdes.complex_band_pass(1, self.samp_rate, self.f_0 - 2*self.doppler_max, self.f_0 + 2*self.doppler_max, 2*self.doppler_max, window.WIN_BLACKMAN, 6.76))
        self.set_doppler_max(self.max_abs_speed / self.v_sound * self.f_0)
        self.analog_pll_freqdet_cf_0_0.set_max_freq(((self.f_0 + self.doppler_max)  /(self.samp_rate/(2*pi))))
        self.analog_pll_freqdet_cf_0_0.set_min_freq(((self.f_0 - self.doppler_max) / (self.samp_rate/(2*pi))))
        self.analog_pll_freqdet_cf_0_0_0.set_max_freq(((self.f_0 + self.doppler_max) / (self.samp_rate/(2*pi))))
        self.analog_pll_freqdet_cf_0_0_0.set_min_freq(((self.f_0 - self.doppler_max) / (self.samp_rate/(2*pi))))
        self.analog_sig_source_x_0.set_frequency(self.f_0)
        self.qtgui_time_sink_x_0.set_y_axis(max(0, self.f_0- 2*self.doppler_max), min(self.f_0 + 2*self.doppler_max, self.samp_rate/2))

    def get_doppler_max(self):
        return self.doppler_max

    def set_doppler_max(self, doppler_max):
        self.doppler_max = doppler_max
        self.set_bpf_taps(firdes.complex_band_pass(1, self.samp_rate, self.f_0 - 2*self.doppler_max, self.f_0 + 2*self.doppler_max, 2*self.doppler_max, window.WIN_BLACKMAN, 6.76))
        self.analog_pll_freqdet_cf_0_0.set_max_freq(((self.f_0 + self.doppler_max)  /(self.samp_rate/(2*pi))))
        self.analog_pll_freqdet_cf_0_0.set_min_freq(((self.f_0 - self.doppler_max) / (self.samp_rate/(2*pi))))
        self.analog_pll_freqdet_cf_0_0_0.set_max_freq(((self.f_0 + self.doppler_max) / (self.samp_rate/(2*pi))))
        self.analog_pll_freqdet_cf_0_0_0.set_min_freq(((self.f_0 - self.doppler_max) / (self.samp_rate/(2*pi))))
        self.qtgui_time_sink_x_0.set_y_axis(max(0, self.f_0- 2*self.doppler_max), min(self.f_0 + 2*self.doppler_max, self.samp_rate/2))

    def get_transmit_gain(self):
        return self.transmit_gain

    def set_transmit_gain(self, transmit_gain):
        self.transmit_gain = transmit_gain
        self.blocks_multiply_const_vxx_0.set_k((10**(self.transmit_gain/20)))

    def get_bpf_taps(self):
        return self.bpf_taps

    def set_bpf_taps(self, bpf_taps):
        self.bpf_taps = bpf_taps
        self.fir_filter_xxx_0.set_taps(self.bpf_taps)



def argument_parser():
    description = 'Doppler sonar'
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "--max-abs-speed", dest="max_abs_speed", type=eng_float, default=eng_notation.num_to_str(float(20)),
        help="Set Maximum Abs. Speed [default=%(default)r]")
    parser.add_argument(
        "-r", "--samp-rate", dest="samp_rate", type=intx, default=int(48e3),
        help="Set Sampling Rate [default=%(default)r]")
    return parser


def main(top_block_cls=doppler_sonar, options=None):
    if options is None:
        options = argument_parser().parse_args()

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls(max_abs_speed=options.max_abs_speed, samp_rate=options.samp_rate)

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

if __name__ == '__main__':
    main()