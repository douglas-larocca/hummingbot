import asyncio
import contextlib
import logging
import unittest
import time
from typing import List

from hummingbot.core.clock import Clock
from hummingbot.core.clock_mode import ClockMode
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.user_stream_tracker import UserStreamTrackerDataSourceType
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import OrderType, MarketEvent, BuyOrderCompletedEvent
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.market.binance_perpetual.binance_perpetual_market import BinancePerpetualMarket
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from .assets.test_keys import Keys

logging.basicConfig(level=METRICS_LOG_LEVEL)


class BinancePerpetualMarketUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFailure
    ]

    market: BinancePerpetualMarket
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls) -> None:
        cls.market: BinancePerpetualMarket = BinancePerpetualMarket(
            binance_api_key=Keys.get_binance_futures_api_key(),
            binance_api_secret=Keys.get_binance_futures_api_secret(),
            order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
            user_stream_tracker_data_source_type=UserStreamTrackerDataSourceType.EXCHANGE_API,
            trading_pairs=["ETHUSDT"]
        )
        cls.ev_loop = asyncio.get_event_loop()
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.clock.add_iterator(cls.market)
        cls._clock = cls.stack.enter_context(cls.clock)

    def setUp(self) -> None:
        self.market_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_buy_and_sell_order(self):
        order_id = self.market.buy(
            trading_pair="ETHUSDT",
            amount=0.01,
            order_type=OrderType.LIMIT,
            price=300
        )

        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual("ETH", order_completed_event.base_asset)
        self.assertEqual("USDT", order_completed_event.quote_asset)

        order_id = self.market.sell(
            trading_pair="ETHUSDT",
            amount=0.01,
            order_type=OrderType.LIMIT,
            price=500
        )
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual("ETH", order_completed_event.base_asset)
        self.assertEqual("USDT", order_completed_event.quote_asset)

    # def test_order_and_cancel(self):
    #     order_id = self.market.buy(
    #         trading_pair="ETHUSDT",
    #         amount=0.01,
    #         order_type=OrderType.LIMIT,
    #         price=300
    #     )
    #     print("BUY ORDER ID --- {order_id}")


def main():
    logging.getLogger("hummingbot.core.event.event_reporter").setLevel(logging.WARNING)
    unittest.main()


if __name__ == "__main__":
    main()