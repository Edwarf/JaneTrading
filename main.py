#!/usr/bin/env python3
# ~~~~~==============   HOW TO RUN   ==============~~~~~
# 1) Configure things in CONFIGURATION section
# 2) Change permissions: chmod +x bot.py
# 3) Run in loop: while true; do ./bot.py --test prod-like; sleep 1; done

import argparse
from pickle import NONE
import uuid
from collections import defaultdict, deque

from enum import Enum
from re import L
import time
import socket
import json

# ~~~~~============== CONFIGURATION  ==============~~~~~
# Replace "REPLACEME" with your team name!
team_name = "WHITETIPSHARKS"

# ~~~~~============== MAIN LOOP ==============~~~~~

# You should put your code here! We provide some starter code as an example,
# but feel free to change/remove/edit/update any of it as you'd like. If you
# have any questions about the starter code, or what to do next, please ask us!
#
# To help you get started, the sample code below tries to buy BOND for a low
# price, and it prints the current prices for VALE every second. The sample
# code is intended to be a working example, but it needs some improvement
# before it will start making good trades!


class MarketBook:
    market_book = defaultdict(lambda: {"buy": [], "sell": []})

    def add_to_book(self, trade):
        self.market_book[trade["symbol"]][trade["dir"].lower()].append(
            [trade["price"], trade["size"]])

    def update_book(self, message):
        self.market_book[message["symbol"]] = {
            "buy": message["buy"], "sell": message["sell"]}

    def check_if_offers(self, ticker, side):
        first, second = self.best_price_quant(ticker, side)
        return first is not None

    def best_price_quant(self, ticker, side):
        if self.market_book[ticker][side]:
            return self.market_book[ticker][side][0][0], self.market_book[ticker][side][0][1]
        else:
            if side == "buy":
                return Constants.BIG_ORDER, Constants.BIG_ORDER
            else:
                return 0, 0

    def best_price_both(self, ticker):
        return self.best_price_quant(ticker, "buy")[0], self.best_price_quant(ticker, "sell")[0]
class Utils:
    @staticmethod
    def best_price(message, side):
        if message[side]:
            return message[side][0][0]

    @staticmethod
    def bid_ask_info(message):
        return Utils.best_price(message, "buy"), Utils.best_price(message, "sell")

    @staticmethod
    def get_xlf_equivalents(market_book):
        bond_bid, bond_ask = market_book.best_price_both("BOND")
        gs_bid, gs_ask = market_book.best_price_both("GS")
        ms_bid, ms_ask = market_book.best_price_both("MS")
        wfc_bid, wfc_ask = market_book.best_price_both("WFC")
        xlf_equiv_bid = int((3*bond_bid + 2*gs_bid + 3*ms_bid + 2*wfc_bid)/10)
        xlf_equiv_ask = int((3*bond_ask + 2*bond_ask + 3*ms_ask + 2*wfc_ask)/10)

        return xlf_equiv_bid, xlf_equiv_ask

    @staticmethod
    def sell_xlf_equivalents(market_book, exchange):
        bond_bid, bond_ask = market_book.best_price_both("BOND")
        gs_bid, gs_ask = market_book.best_price_both("GS")
        ms_bid, ms_ask = market_book.best_price_both("MS")
        wfc_bid, wfc_ask = market_book.best_price_both("WFC")
        exchange.send_add_message(Ledger.current_id, "BOND", Dir.SELL, bond_bid, 3)
        exchange.send_add_message(Ledger.current_id, "GS", Dir.SELL, gs_bid, 2)
        exchange.send_add_message(Ledger.current_id, "MS", Dir.SELL, ms_bid, 3)
        exchange.send_add_message(Ledger.current_id, "WFC", Dir.SELL, wfc_bid, 2)

    @staticmethod
    def buy_xlf_equivalents(market_book, exchange):
        bond_bid, bond_ask = market_book.best_price_both("BOND")
        gs_bid, gs_ask = market_book.best_price_both("GS")
        ms_bid, ms_ask = market_book.best_price_both("MS")
        wfc_bid, wfc_ask = market_book.best_price_both("WFC")
        exchange.send_add_message(Ledger.current_id, "BOND", Dir.BUY, bond_ask, 3)
        exchange.send_add_message(Ledger.current_id, "GS", Dir.BUY, gs_ask, 2)
        exchange.send_add_message(Ledger.current_id, "MS", Dir.BUY, ms_ask, 3)
        exchange.send_add_message(Ledger.current_id, "WFC", Dir.BUY, wfc_ask, 2)

    @staticmethod
    def trade_fair_value(exchange, ticker, price, fair_value, volume):
        if price > fair_value:
            exchange.send_add_message(Ledger.current_id, ticker, Dir.SELL, price, volume)
            exchange.send_add_message(Ledger.current_id, ticker, Dir.BUY, fair_value, volume)
        elif price < fair_value:
            exchange.send_add_message(Ledger.current_id, ticker, Dir.BUY, price, volume)
            exchange.send_add_message(Ledger.current_id, ticker, Dir.SELL, fair_value, volume)



class Constants:
    WAIT_TIME = 1
    BIG_ORDER = 30*10*10


class Ledger:
    current_id = 0
    assets = defaultdict(lambda: 0)
    pending_orders = defaultdict(lambda: NONE)
    open_orders = defaultdict(lambda: NONE)
    times = []

    @staticmethod
    def addOpen(order_id, symbol, dir, price, size):
        Ledger.pending_orders[order_id] = {"symbol": symbol, "dir": dir, "price": price, "size": size}

    @staticmethod
    def confirmOrder(orderId):
        Ledger.open_orders[orderId] = Ledger.pending_orders[orderId]
        Ledger.times.append([orderId, time.time()])
        del Ledger.pending_orders[orderId]

    @staticmethod
    def failOrder(orderId):
        del Ledger.pending_orders[orderId]
    
    @staticmethod
    def outOrder(orderId):
        del Ledger.open_orders[orderId]


def main():
    args = parse_arguments()

    exchange = ExchangeConnection(args=args)

    # Store and print the "hello" message received from the exchange. This
    # contains useful information about your positions. Normally you start with
    # all positions at zero, but if you reconnect during a round, you might
    # have already bought/sold symbols and have non-zero positions.
    hello_message = exchange.read_message()
    print("First message from exchange:", hello_message)

    # Send an order for BOND at a good price, but it is low enough that it is
    # unlikely it will be traded against. Maybe there is a better price to
    # pick? Also, you will need to send more orders over time.
    exchange.send_add_message(order_id=1, symbol="BOND", dir=Dir.BUY, price=990, size=1)

    # Set up some variables to track the bid and ask price of a symbol. Right
    # now this doesn't track much information, but it's enough to get a sense
    # of the VALE market.
    vale_bid_price, vale_ask_price = None, None
    vale_last_print_time = time.time()


    # Here is the main loop of the program. It will continue to read and
    # process messages in a loop until a "close" message is received. You
    # should write to code handle more types of messages (and not just print
    # the message). Feel free to modify any of the starter code below.
    #
    # Note: a common mistake people make is to call write_message() at least
    # once for every read_message() response.
    #
    # Every message sent to the exchange generates at least one response
    # message. Sending a message in response to every exchange message will
    # cause a feedback loop where your bot's messages will quickly be
    # rate-limited and ignored. Please, don't do that!
    market_book = MarketBook()
    orderIdNum = 1
    
    trade_time = 0

    while True:
        message = exchange.read_message()

        # Some of the message types below happen infrequently and contain
        # important information to help you understand what your bot is doing,
        # so they are printed in full. We recommend not always printing every
        # message because it can be a lot of information to read. Instead, let
        # your code handle the messages and just print the information
        # important for you!

        # Guaranteed Actions

        #exchange.send_add_message(Ledger.current_id, "BOND", Dir.BUY, 999, 1)
        #exchange.send_add_message(Ledger.current_id, "BOND", Dir.SELL, 1001, 1)

        if message["type"] == "close":
            print("The round has ended")
            break
        elif message["type"] == "ack":
            Ledger.confirmOrder(message["order_id"])
        elif message["type"] == "error":
            Ledger.failOrder(message["order_id"])
            print(message)
        elif message["type"] == "out":
            Ledger.outOrder(message["order_id"])
        elif message["type"] == "reject":
            print(message)
        elif message["type"] == "fill":
            print(message)
        elif message["type"] == "book":
            market_book.update_book(message)

        if time.time() - trade_time > Constants.WAIT_TIME:
            # if message["symbol"] == "BOND":
            #     continue
            #     buyInfo = market_book.best_price_quant("BOND", "buy")
            #     if buyInfo is not None and buyInfo[0] < 1000:
            #          exchange.send_add_message(
            #             orderIdNum, "BOND", "BUY", buyInfo[0] + 1, buyInfo[1])
            #          time.sleep(Constants.WAIT_TIME)
            #     sellInfo = market_book.best_price_quant("BOND", "sell")
            #     if buyInfo is not None and sellInfo[0] > 1000:
            #          exchange.send_add_message(orderIdNum, "BOND", "SELL", buyInfo[0] - 1, buyInfo[1])
            #          time.sleep(Constants.WAIT_TIME)

        
            # Calculate XLF rates
            xlf_bid, xlf_ask = market_book.best_price_both("XLF")
            # Calculate market equivalent of XLF
            xlf_equiv_bid, xlf_equiv_ask = Utils.get_xlf_equivalents(market_book)
            # Trade on fair value
            Utils.trade_fair_value(exchange, "XLF", xlf_bid, xlf_equiv_bid, 1)

            trade_time = time.time()

            currentTime = time.time()
            for i, group in enumerate(Ledger.times):
                if currentTime - group[1] > 10 and group[0] in Ledger.open_orders:
                    print("Kill", group[1])
                    exchange.send_cancel_message(group[0])

                if currentTime - group[1] < 10:
                    Ledger.times = Ledger.times[i:]
                    break









# ~~~~~============== PROVIDED CODE ==============~~~~~

# You probably don't need to edit anything below this line, but feel free to
# ask if you have any questions about what it is doing or how it works. If you
# do need to change anything below this line, please feel free to


class Dir(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExchangeConnection:
    def __init__(self, args):
        self.message_timestamps = deque(maxlen=500)
        self.exchange_hostname = args.exchange_hostname
        self.port = args.port
        self.exchange_socket = self._connect(add_socket_timeout=args.add_socket_timeout)

        self._write_message({"type": "hello", "team": team_name.upper()})

    def read_message(self):
        """Read a single message from the exchange"""
        message = json.loads(self.exchange_socket.readline())
        if "dir" in message:
            message["dir"] = Dir(message["dir"])
        return message

    def send_add_message(
        self, order_id: int, symbol: str, dir: Dir, price: int, size: int
    ):
        Ledger.addOpen(order_id, symbol, dir, price, size)
        """Add a new order"""
        self._write_message(
            {
                "type": "add",
                "order_id": order_id,
                "symbol": symbol,
                "dir": dir,
                "price": price,
                "size": size,
            }
        )

    def send_convert_message(self, order_id: int, symbol: str, dir: Dir, size: int):
        """Convert between related symbols"""
        self._write_message(
            {
                "type": "convert",
                "order_id": order_id,
                "symbol": symbol,
                "dir": dir,
                "size": size,
            }
        )

    def send_cancel_message(self, order_id: int):
        """Cancel an existing order"""
        self._write_message({"type": "cancel", "order_id": order_id})

    def _connect(self, add_socket_timeout):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if add_socket_timeout:
            # Automatically raise an exception if no data has been recieved for
            # multiple seconds. This should not be enabled on an "empty" test
            # exchange.
            s.settimeout(5)
        s.connect((self.exchange_hostname, self.port))
        return s.makefile("rw", 1)

    def _write_message(self, message):
        Ledger.current_id += 1        
        json.dump(message, self.exchange_socket)
        self.exchange_socket.write("\n")

        now = time.time()
        self.message_timestamps.append(now)
        if len(
            self.message_timestamps
        ) == self.message_timestamps.maxlen and self.message_timestamps[0] > (now - 1):
            print(
                "WARNING: You are sending messages too frequently. The exchange will start ignoring your messages. Make sure you are not sending a message in response to every exchange message."
            )


def parse_arguments():
    test_exchange_port_offsets = {"prod-like": 0, "slower": 1, "empty": 2}

    parser = argparse.ArgumentParser(description="Trade on an ETC exchange!")
    exchange_address_group = parser.add_mutually_exclusive_group(required=True)
    exchange_address_group.add_argument(
        "--production", action="store_true", help="Connect to the production exchange."
    )
    exchange_address_group.add_argument(
        "--test",
        type=str,
        choices=test_exchange_port_offsets.keys(),
        help="Connect to a test exchange.",
    )

    # Connect to a specific host. This is only intended to be used for debugging.
    exchange_address_group.add_argument(
        "--specific-address", type=str, metavar="HOST:PORT", help=argparse.SUPPRESS
    )

    args = parser.parse_args()
    args.add_socket_timeout = True

    if args.production:
        args.exchange_hostname = "production"
        args.port = 25000
    elif args.test:
        args.exchange_hostname = "test-exch-" + team_name
        args.port = 25000 + test_exchange_port_offsets[args.test]
        if args.test == "empty":
            args.add_socket_timeout = False
    elif args.specific_address:
        args.exchange_hostname, port = args.specific_address.split(":")
        args.port = int(port)

    return args


if __name__ == "__main__":
    # Check that [team_name] has been updated.
    assert (
        team_name != "REPLACEME"
    ), "Please put your team name in the variable [team_name]."

    main()


