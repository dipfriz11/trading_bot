import sys
import os
import tempfile
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from trading_core.position_manager import PositionManager, CycleConfig
from storage.sqlite_storage import SQLiteStorage


def make_config(target_profit=0.003):
    return CycleConfig(
        base_size=10.0,
        hedge_ratio=0.5,
        major_multiplier=2.0,
        minor_multiplier=0.5,
        target_profit=target_profit,
        auto_close=True,
        repeat_mode="ignore",
        max_cycles=5,
        max_total_exposure=None,
        leverage=10,
    )


class TestPerSymbolIsolation(unittest.TestCase):

    def test_profit_manager_per_symbol_isolation(self):
        """cycle_target_profit двух символов независимы"""
        m1 = PositionManager(make_config())
        m2 = PositionManager(make_config())

        m1.cycle_target_profit = 0.001
        m2.cycle_target_profit = 0.999

        self.assertEqual(m1.cycle_target_profit, 0.001)
        self.assertEqual(m2.cycle_target_profit, 0.999)

        m1.cycle_target_profit = 0.005
        self.assertEqual(m2.cycle_target_profit, 0.999,
                         "изменение m1 не должно влиять на m2")

    def test_profit_managers_are_independent_objects(self):
        """у каждого PositionManager свой ProfitManager"""
        m1 = PositionManager(make_config())
        m2 = PositionManager(make_config())
        self.assertIsNot(m1.profit_manager, m2.profit_manager)

    def test_target_profit_not_overwritten_by_another_symbol(self):
        """reset одного символа не трогает второй"""
        m1 = PositionManager(make_config())
        m2 = PositionManager(make_config())

        m1.cycle_target_profit = 0.002
        m2.cycle_target_profit = 0.007

        m1.reset_cycle()

        self.assertEqual(m1.cycle_target_profit, 0.0,
                         "после reset m1.cycle_target_profit должен быть 0.0")
        self.assertEqual(m2.cycle_target_profit, 0.007,
                         "m2 не должен быть затронут")

    def test_reset_cycle_zeroes_target_profit(self):
        """reset_cycle всегда сбрасывает cycle_target_profit в 0.0"""
        m = PositionManager(make_config())
        m.cycle_target_profit = 0.005
        m.reset_cycle()
        self.assertEqual(m.cycle_target_profit, 0.0)


class TestSQLiteRestore(unittest.TestCase):

    def setUp(self):
        self._db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._db_file.close()
        self.storage = SQLiteStorage(self._db_file.name)

    def tearDown(self):
        os.unlink(self._db_file.name)

    def _base_state(self, **overrides):
        state = {
            "cycle_active": True,
            "bias": "UP",
            "long_size": 10.0,
            "short_size": 5.0,
            "cycle_number": 1,
            "blocked": False,
            "last_signal": "buy",
            "last_signal_time": 0.0,
            "cycle_target_profit": 0.003,
        }
        state.update(overrides)
        return state

    def test_profit_manager_restore_after_restart_keeps_symbol_target_profit(self):
        """cycle_target_profit сохраняется и восстанавливается"""
        self.storage.save_state("ETHUSDT", self._base_state(cycle_target_profit=0.003))
        loaded = self.storage.load_all_states()
        self.assertEqual(loaded["ETHUSDT"]["cycle_target_profit"], 0.003)

    def test_two_symbols_restore_independently(self):
        """два символа восстанавливаются с независимыми значениями"""
        self.storage.save_state("ETHUSDT", self._base_state(cycle_target_profit=0.001))
        self.storage.save_state("XRPUSDT", self._base_state(cycle_target_profit=0.007))

        loaded = self.storage.load_all_states()

        self.assertEqual(loaded["ETHUSDT"]["cycle_target_profit"], 0.001)
        self.assertEqual(loaded["XRPUSDT"]["cycle_target_profit"], 0.007)

    def test_null_cycle_target_profit_handled_safely(self):
        """NULL в базе не вызывает TypeError"""
        self.storage.save_state("DAMUSDT", self._base_state(cycle_target_profit=None))
        loaded = self.storage.load_all_states()
        val = loaded["DAMUSDT"]["cycle_target_profit"]
        self.assertIn(val, [None, 0.0])


class TestExecutionUsesCorrectSymbolTarget(unittest.TestCase):

    def _make_pos(self, side, entry, mark, qty):
        return {
            "positionSide": side,
            "positionAmt": str(qty),
            "entryPrice": str(entry),
            "markPrice": str(mark),
        }

    def test_execution_uses_correct_symbol_target_profit(self):
        """
        Два символа с разными target_profit.
        Один должен закрыться (net >= target), второй нет.
        """
        from profit_manager import ProfitManager

        pm1 = ProfitManager(taker_fee=0.0004)
        pm2 = ProfitManager(taker_fee=0.0004)

        long1  = self._make_pos("LONG",  entry=100.0, mark=100.5, qty=10.0)
        short1 = self._make_pos("SHORT", entry=100.0, mark=99.5,  qty=-10.0)

        long2  = self._make_pos("LONG",  entry=100.0, mark=100.5, qty=10.0)
        short2 = self._make_pos("SHORT", entry=100.0, mark=99.5,  qty=-10.0)

        target_eth = 0.001   # низкий → закроется
        target_xrp = 100.0   # высокий → не закроется

        result_eth = pm1.should_close("ETHUSDT", long1, short1, target_eth)
        result_xrp = pm2.should_close("XRPUSDT", long2, short2, target_xrp)

        self.assertTrue(result_eth,  "ETHUSDT должен закрыться (net > target)")
        self.assertFalse(result_xrp, "XRPUSDT не должен закрыться (net < target)")

    def test_should_close_uses_argument_not_internal_state(self):
        """should_close использует переданный target_profit, а не внутреннее состояние"""
        from profit_manager import ProfitManager

        pm = ProfitManager(taker_fee=0.0004)
        long_pos  = self._make_pos("LONG",  entry=100.0, mark=100.1, qty=10.0)
        short_pos = self._make_pos("SHORT", entry=100.0, mark=99.9,  qty=-10.0)

        self.assertTrue(pm.should_close("SYM", long_pos, short_pos, target_profit=0.0001))
        self.assertFalse(pm.should_close("SYM", long_pos, short_pos, target_profit=999.0))


if __name__ == "__main__":
    unittest.main()
