#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: FSK_NO_GUI_V2
# GNU Radio version: 3.10.9.2

import os
import sys
sys.path.append(os.environ.get('GRC_HIER_PATH', os.path.expanduser('~/.grc_gnuradio')))

from gnuradio import analog
import math
from gnuradio import blocks
from gnuradio import blocks, gr
from gnuradio import digital
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import gr, pdu
from gnuradio import network
from hdlc_framer_with_preamble import hdlc_framer_with_preamble  # grc-generated hier_block
from math import pi
from nrzs_line_coding import nrzs_line_coding  # grc-generated hier_block
import limesdr




class FSK_NO_GUI_V2(gr.top_block):

    def __init__(self, baud_rate=1200, dl_freq=145.91e6, rx_gain=56, sps=160, tx_gain=56, ul_freq=436830000):
        gr.top_block.__init__(self, "FSK_NO_GUI_V2", catch_exceptions=True)

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
        self.samp_rate = samp_rate = baud_rate*sps

        ##################################################
        # Blocks
        ##################################################

        self.root_raised_cosine_filter_1 = filter.fir_filter_fff(
            1,
            firdes.root_raised_cosine(
                1,
                (sps*baud_rate),
                (2*baud_rate),
                0.5,
                (sps*7)))
        self.root_raised_cosine_filter_0 = filter.interp_fir_filter_fff(
            sps,
            firdes.root_raised_cosine(
                sps,
                sps,
                1.0,
                0.35,
                (sps*7)))
        self.pdu_pdu_to_tagged_stream_0 = pdu.pdu_to_tagged_stream(gr.types.byte_t, 'packet_len')
        self.nrzs_line_coding_0 = nrzs_line_coding()
        self.network_socket_pdu_1 = network.socket_pdu('UDP_CLIENT', '127.0.0.1', '27000', 10000, False)
        self.network_socket_pdu_0 = network.socket_pdu('UDP_SERVER', '127.0.0.1', '27001', 10000, False)
        self.limesdr_source_0 = limesdr.source('1D7522AE31A162', 0, '', False)


        self.limesdr_source_0.set_sample_rate(baud_rate*sps)


        self.limesdr_source_0.set_center_freq(dl_freq, 0)

        self.limesdr_source_0.set_bandwidth(1.5e6, 0)




        self.limesdr_source_0.set_gain(rx_gain, 0)


        self.limesdr_source_0.set_antenna(255, 0)


        self.limesdr_source_0.calibrate(2.5e6, 0)


        self.limesdr_source_0.set_nco(1,0)
        self.limesdr_sink_0 = limesdr.sink('1D7522AE31A162', 0, '', '')


        self.limesdr_sink_0.set_sample_rate(samp_rate)


        self.limesdr_sink_0.set_center_freq(dl_freq, 0)

        self.limesdr_sink_0.set_bandwidth(5e6, 0)


        self.limesdr_sink_0.set_digital_filter(samp_rate, 0)


        self.limesdr_sink_0.set_gain(tx_gain, 0)


        self.limesdr_sink_0.set_antenna(255, 0)


        self.limesdr_sink_0.calibrate(2.5e6, 0)
        self.hdlc_framer_with_preamble_0 = hdlc_framer_with_preamble(
            num_postamble_bytes=20,
            num_preamble_bytes=20,
        )
        self.digital_symbol_sync_xx_0 = digital.symbol_sync_ff(
            digital.TED_SIGNUM_TIMES_SLOPE_ML,
            sps,
            0.0628,
            1.0,
            1.0,
            1.5,
            1,
            digital.constellation_bpsk().base(),
            digital.IR_MMSE_8TAP,
            128,
            [])
        self.digital_scrambler_bb_0 = digital.scrambler_bb(0x21, 0x00, 16)
        self.digital_hdlc_deframer_bp_0 = digital.hdlc_deframer_bp(116, 272)
        self.digital_diff_decoder_bb_0 = digital.diff_decoder_bb(2, digital.DIFF_DIFFERENTIAL)
        self.digital_descrambler_bb_0 = digital.descrambler_bb(0x21, 0, 16)
        self.digital_chunks_to_symbols_xx_0 = digital.chunks_to_symbols_bf([-1.0, 1.0], 1)
        self.digital_binary_slicer_fb_0 = digital.binary_slicer_fb()
        self.blocks_tagged_stream_multiply_length_0 = blocks.tagged_stream_multiply_length(gr.sizeof_float*1, "packet_len", sps)
        self.blocks_not_xx_0_0 = blocks.not_bb()
        self.blocks_message_debug_1 = blocks.message_debug(True, gr.log_levels.info)
        self.blocks_message_debug_0 = blocks.message_debug(True, gr.log_levels.info)
        self.blocks_file_sink_0 = blocks.file_sink(gr.sizeof_char*1, 'tx_bits.hex', False)
        self.blocks_file_sink_0.set_unbuffered(False)
        self.blocks_and_const_xx_0_0 = blocks.and_const_bb(1)
        self.analog_simple_squelch_cc_0 = analog.simple_squelch_cc((-50), 1)
        self.analog_quadrature_demod_cf_0 = analog.quadrature_demod_cf((192000/(2*math.pi*35000)))
        self.analog_frequency_modulator_fc_0 = analog.frequency_modulator_fc((2.0*3.14159*35000/float(samp_rate)))
        self.analog_agc_xx_0 = analog.agc_cc((1e-6), 1.0, 1.0, 65536)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.digital_hdlc_deframer_bp_0, 'out'), (self.blocks_message_debug_1, 'print'))
        self.msg_connect((self.digital_hdlc_deframer_bp_0, 'out'), (self.network_socket_pdu_1, 'pdus'))
        self.msg_connect((self.digital_hdlc_deframer_bp_0, 'out'), (self.pdu_pdu_to_tagged_stream_0, 'pdus'))
        self.msg_connect((self.network_socket_pdu_0, 'pdus'), (self.blocks_message_debug_0, 'print'))
        self.msg_connect((self.network_socket_pdu_0, 'pdus'), (self.hdlc_framer_with_preamble_0, 'in'))
        self.connect((self.analog_agc_xx_0, 0), (self.analog_quadrature_demod_cf_0, 0))
        self.connect((self.analog_frequency_modulator_fc_0, 0), (self.limesdr_sink_0, 0))
        self.connect((self.analog_quadrature_demod_cf_0, 0), (self.root_raised_cosine_filter_1, 0))
        self.connect((self.analog_simple_squelch_cc_0, 0), (self.analog_agc_xx_0, 0))
        self.connect((self.blocks_and_const_xx_0_0, 0), (self.digital_hdlc_deframer_bp_0, 0))
        self.connect((self.blocks_not_xx_0_0, 0), (self.blocks_and_const_xx_0_0, 0))
        self.connect((self.blocks_tagged_stream_multiply_length_0, 0), (self.analog_frequency_modulator_fc_0, 0))
        self.connect((self.digital_binary_slicer_fb_0, 0), (self.digital_diff_decoder_bb_0, 0))
        self.connect((self.digital_chunks_to_symbols_xx_0, 0), (self.root_raised_cosine_filter_0, 0))
        self.connect((self.digital_descrambler_bb_0, 0), (self.blocks_not_xx_0_0, 0))
        self.connect((self.digital_diff_decoder_bb_0, 0), (self.digital_descrambler_bb_0, 0))
        self.connect((self.digital_scrambler_bb_0, 0), (self.digital_chunks_to_symbols_xx_0, 0))
        self.connect((self.digital_symbol_sync_xx_0, 0), (self.digital_binary_slicer_fb_0, 0))
        self.connect((self.hdlc_framer_with_preamble_0, 0), (self.nrzs_line_coding_0, 0))
        self.connect((self.limesdr_source_0, 0), (self.analog_simple_squelch_cc_0, 0))
        self.connect((self.nrzs_line_coding_0, 0), (self.digital_scrambler_bb_0, 0))
        self.connect((self.pdu_pdu_to_tagged_stream_0, 0), (self.blocks_file_sink_0, 0))
        self.connect((self.root_raised_cosine_filter_0, 0), (self.blocks_tagged_stream_multiply_length_0, 0))
        self.connect((self.root_raised_cosine_filter_1, 0), (self.digital_symbol_sync_xx_0, 0))


    def get_baud_rate(self):
        return self.baud_rate

    def set_baud_rate(self, baud_rate):
        self.baud_rate = baud_rate
        self.set_samp_rate(self.baud_rate*self.sps)
        self.root_raised_cosine_filter_1.set_taps(firdes.root_raised_cosine(1, (self.sps*self.baud_rate), (2*self.baud_rate), 0.5, (self.sps*7)))

    def get_dl_freq(self):
        return self.dl_freq

    def set_dl_freq(self, dl_freq):
        self.dl_freq = dl_freq
        self.limesdr_sink_0.set_center_freq(self.dl_freq, 0)
        self.limesdr_source_0.set_center_freq(self.dl_freq, 0)

    def get_rx_gain(self):
        return self.rx_gain

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain
        self.limesdr_source_0.set_gain(self.rx_gain, 0)
        self.limesdr_source_0.set_gain(self.rx_gain, 1)

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.set_samp_rate(self.baud_rate*self.sps)
        self.blocks_tagged_stream_multiply_length_0.set_scalar(self.sps)
        self.digital_symbol_sync_xx_0.set_sps(self.sps)
        self.root_raised_cosine_filter_0.set_taps(firdes.root_raised_cosine(self.sps, self.sps, 1.0, 0.35, (self.sps*7)))
        self.root_raised_cosine_filter_1.set_taps(firdes.root_raised_cosine(1, (self.sps*self.baud_rate), (2*self.baud_rate), 0.5, (self.sps*7)))

    def get_tx_gain(self):
        return self.tx_gain

    def set_tx_gain(self, tx_gain):
        self.tx_gain = tx_gain
        self.limesdr_sink_0.set_gain(self.tx_gain, 0)

    def get_ul_freq(self):
        return self.ul_freq

    def set_ul_freq(self, ul_freq):
        self.ul_freq = ul_freq

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.analog_frequency_modulator_fc_0.set_sensitivity((2.0*3.14159*35000/float(self.samp_rate)))
        self.limesdr_sink_0.set_digital_filter(self.samp_rate, 0)
        self.limesdr_sink_0.set_digital_filter(self.samp_rate, 1)



def argument_parser():
    parser = ArgumentParser()
    parser.add_argument(
        "--baud-rate", dest="baud_rate", type=intx, default=1200,
        help="Set baud_rate [default=%(default)r]")
    parser.add_argument(
        "--dl-freq", dest="dl_freq", type=eng_float, default=eng_notation.num_to_str(float(145.91e6)),
        help="Set DL_Freq [default=%(default)r]")
    parser.add_argument(
        "--sps", dest="sps", type=intx, default=160,
        help="Set sps [default=%(default)r]")
    parser.add_argument(
        "--ul-freq", dest="ul_freq", type=eng_float, default=eng_notation.num_to_str(float(436830000)),
        help="Set UL_Freq [default=%(default)r]")
    return parser


def main(top_block_cls=FSK_NO_GUI_V2, options=None):
    if options is None:
        options = argument_parser().parse_args()
    tb = top_block_cls(baud_rate=options.baud_rate, dl_freq=options.dl_freq, sps=options.sps, ul_freq=options.ul_freq)

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()

    try:
        input('Press Enter to quit: ')
    except EOFError:
        pass
    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
