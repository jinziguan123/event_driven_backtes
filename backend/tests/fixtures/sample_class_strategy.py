class SampleClassStrategy:
    name = 'sample_class'

    def initialize(self, context):
        context['initialized'] = True

    def on_bar(self, context, bars):
        return {'type': 'BUY', 'bars': bars}

    def after_trading(self, context):
        context['after_trading'] = True
