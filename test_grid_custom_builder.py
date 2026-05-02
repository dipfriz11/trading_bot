import unittest

from trading_core.grid.grid_builder import GridBuilder
from trading_core.grid.grid_models import CustomGridLevelConfig


class TestGridCustomBuilder(unittest.TestCase):

    def setUp(self) -> None:
        self.builder = GridBuilder()

    def test_index_zero_raises(self):
        with self.assertRaises(ValueError):
            CustomGridLevelConfig(
                index=0,
                price_mode="fixed_price",
                price_value=99.0,
                size_weight=1.0,
            )

    def test_non_contiguous_indexes_raise(self):
        with self.assertRaises(ValueError):
            self.builder.build_custom_session(
                symbol="HIGHUSDT",
                position_side="LONG",
                reference_price=100.0,
                total_budget=50.0,
                custom_levels=[
                    CustomGridLevelConfig(
                        index=1,
                        price_mode="fixed_price",
                        price_value=99.0,
                        size_weight=1.0,
                    ),
                    CustomGridLevelConfig(
                        index=3,
                        price_mode="fixed_price",
                        price_value=98.0,
                        size_weight=1.0,
                    ),
                ],
            )

    def test_long_reference_then_previous_offsets(self):
        session = self.builder.build_custom_session(
            symbol="HIGHUSDT",
            position_side="LONG",
            reference_price=100.0,
            total_budget=50.0,
            custom_levels=[
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
                    size_weight=1.0,
                ),
            ],
        )
        self.assertAlmostEqual(session.levels[0].price, 99.0)
        self.assertAlmostEqual(session.levels[1].price, 98.01)

    def test_short_offsets_go_up(self):
        session = self.builder.build_custom_session(
            symbol="HIGHUSDT",
            position_side="SHORT",
            reference_price=100.0,
            total_budget=50.0,
            custom_levels=[
                CustomGridLevelConfig(
                    index=1,
                    price_mode="offset_from_reference",
                    price_value=1.0,
                    size_weight=1.0,
                ),
                CustomGridLevelConfig(
                    index=2,
                    price_mode="offset_from_previous",
                    price_value=2.0,
                    size_weight=1.0,
                ),
            ],
        )
        self.assertAlmostEqual(session.levels[0].price, 101.0)
        self.assertAlmostEqual(session.levels[1].price, 103.02)

    def test_fixed_price_works(self):
        session = self.builder.build_custom_session(
            symbol="HIGHUSDT",
            position_side="LONG",
            reference_price=100.0,
            total_budget=50.0,
            custom_levels=[
                CustomGridLevelConfig(
                    index=1,
                    price_mode="fixed_price",
                    price_value=97.5,
                    size_weight=1.0,
                ),
            ],
        )
        self.assertAlmostEqual(session.levels[0].price, 97.5)

    def test_size_weight_distributes_total_budget_proportionally(self):
        session = self.builder.build_custom_session(
            symbol="HIGHUSDT",
            position_side="LONG",
            reference_price=100.0,
            total_budget=50.0,
            custom_levels=[
                CustomGridLevelConfig(
                    index=1,
                    price_mode="fixed_price",
                    price_value=100.0,
                    size_weight=1.0,
                ),
                CustomGridLevelConfig(
                    index=2,
                    price_mode="fixed_price",
                    price_value=100.0,
                    size_weight=2.0,
                ),
            ],
        )
        self.assertAlmostEqual(session.levels[0].qty, (50.0 * 1.0 / 3.0) / 100.0)
        self.assertAlmostEqual(session.levels[1].qty, (50.0 * 2.0 / 3.0) / 100.0)

    def test_reset_tp_params_are_mapped_to_grid_level(self):
        session = self.builder.build_custom_session(
            symbol="HIGHUSDT",
            position_side="LONG",
            reference_price=100.0,
            total_budget=50.0,
            custom_levels=[
                CustomGridLevelConfig(
                    index=1,
                    price_mode="fixed_price",
                    price_value=99.0,
                    size_weight=1.0,
                    use_reset_tp=True,
                    reset_tp_percent=1.2,
                    reset_tp_close_percent=45.0,
                ),
            ],
        )
        level = session.levels[0]
        self.assertTrue(level.use_reset_tp)
        self.assertEqual(level.reset_tp_percent, 1.2)
        self.assertEqual(level.reset_tp_close_percent, 45.0)

    def test_invalid_first_level_offset_from_previous(self):
        with self.assertRaises(ValueError):
            self.builder.build_custom_session(
                symbol="HIGHUSDT",
                position_side="LONG",
                reference_price=100.0,
                total_budget=50.0,
                custom_levels=[
                    CustomGridLevelConfig(
                        index=1,
                        price_mode="offset_from_previous",
                        price_value=1.0,
                        size_weight=1.0,
                    ),
                ],
            )

    def test_invalid_non_first_offset_from_reference(self):
        with self.assertRaises(ValueError):
            self.builder.build_custom_session(
                symbol="HIGHUSDT",
                position_side="LONG",
                reference_price=100.0,
                total_budget=50.0,
                custom_levels=[
                    CustomGridLevelConfig(index=1, price_mode="fixed_price", price_value=99.0, size_weight=1.0),
                    CustomGridLevelConfig(index=2, price_mode="offset_from_reference", price_value=1.0, size_weight=1.0),
                ],
            )

    def test_total_budget_must_be_positive(self):
        with self.assertRaises(ValueError):
            self.builder.build_custom_session(
                symbol="HIGHUSDT",
                position_side="LONG",
                reference_price=100.0,
                total_budget=0.0,
                custom_levels=[
                    CustomGridLevelConfig(
                        index=1,
                        price_mode="fixed_price",
                        price_value=99.0,
                        size_weight=1.0,
                    ),
                ],
            )


if __name__ == "__main__":
    unittest.main()
