from autotrade.core.interfaces import Strategy
class TestTemp(Strategy):
    name='test_temp_strat'
    def generate_signals(self, df): return []