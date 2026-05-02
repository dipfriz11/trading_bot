import unittest

from trading_core.grid.grid_builder import GridBuilder
from trading_core.grid.grid_registry import GridRegistry
from trading_core.grid.grid_models import CustomGridLevelConfig, GridSession
from trading_core.grid.grid_service import GridService
from trading_core.grid.grid_sizer import GridSizer


class SpyRunner:
    def __init__(self):
        self.place_called = False
        self.modify_called = False

    def place_session_orders(self, session):
        self.place_called = True
        return session

    def modify_session_orders(self, session, new_levels):
        self.modify_called = True
        return session


class SpyRegistry(GridRegistry):
    def __init__(self):
        super().__init__()
        self.save_calls = 0

    def save_session(self, session):
        self.save_calls += 1
        super().save_session(session)


class TestGridServiceCustomPreview(unittest.TestCase):

    def setUp(self) -> None:
        self.builder = GridBuilder()
        self.runner = SpyRunner()
        self.registry = SpyRegistry()
        self.service = GridService(
            builder=self.builder,
            runner=self.runner,
            registry=self.registry,
            exchange=object(),
            sizer=GridSizer(),
        )

    def _sample_levels(self):
        return [
            CustomGridLevelConfig(
                index=1,
                price_mode="offset_from_reference",
                price_value=1.0,
                size_weight=1.0,
            ),
            CustomGridLevelConfig(
                index=2,
                price_mode="offset_from_previous",
                price_value=1.0,
                size_weight=2.0,
                use_reset_tp=True,
                reset_tp_percent=1.2,
                reset_tp_close_percent=45.0,
            ),
        ]

    def test_preview_returns_grid_session(self):
        session = self.service.build_custom_grid_preview(
            symbol="HIGHUSDT",
            position_side="LONG",
            reference_price=100.0,
            total_budget=50.0,
            custom_levels=self._sample_levels(),
        )
        self.assertIsInstance(session, GridSession)

    def test_preview_output_equals_direct_builder_output(self):
        custom_levels = self._sample_levels()
        preview = self.service.build_custom_grid_preview(
            symbol="HIGHUSDT",
            position_side="LONG",
            reference_price=100.0,
            total_budget=50.0,
            custom_levels=custom_levels,
        )
        direct = self.builder.build_custom_session(
            symbol="HIGHUSDT",
            position_side="LONG",
            reference_price=100.0,
            total_budget=50.0,
            custom_levels=custom_levels,
        )
        self.assertEqual(preview.symbol, direct.symbol)
        self.assertEqual(preview.position_side, direct.position_side)
        self.assertEqual(len(preview.levels), len(direct.levels))
        self.assertEqual(
            [
                (l.index, l.price, l.qty, l.use_reset_tp, l.reset_tp_percent, l.reset_tp_close_percent)
                for l in preview.levels
            ],
            [
                (l.index, l.price, l.qty, l.use_reset_tp, l.reset_tp_percent, l.reset_tp_close_percent)
                for l in direct.levels
            ],
        )

    def test_invalid_custom_config_bubbles_value_error(self):
        with self.assertRaises(ValueError):
            self.service.build_custom_grid_preview(
                symbol="HIGHUSDT",
                position_side="LONG",
                reference_price=100.0,
                total_budget=50.0,
                custom_levels=[
                    CustomGridLevelConfig(index=1, price_mode="fixed_price", price_value=99.0, size_weight=1.0),
                    CustomGridLevelConfig(index=3, price_mode="fixed_price", price_value=98.0, size_weight=1.0),
                ],
            )

    def test_preview_does_not_touch_live_state(self):
        self.service.build_custom_grid_preview(
            symbol="HIGHUSDT",
            position_side="LONG",
            reference_price=100.0,
            total_budget=50.0,
            custom_levels=self._sample_levels(),
        )
        self.assertFalse(self.runner.place_called)
        self.assertFalse(self.runner.modify_called)
        self.assertEqual(self.registry.save_calls, 0)
        self.assertIsNone(self.registry.get_session("HIGHUSDT", "LONG"))
        self.assertNotIn(("HIGHUSDT", "LONG"), self.service._grid_build_config)


if __name__ == "__main__":
    unittest.main()
