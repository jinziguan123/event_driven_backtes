name = 'sample_script'


def initialize(context):
    context['initialized'] = True


def handle_bar(context, bars):
    return {'type': 'SELL', 'bars': bars}


def after_trading(context):
    context['after_trading'] = True
