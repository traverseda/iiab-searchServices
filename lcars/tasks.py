import lcars.index
from lcars.settings import HUEY
import logging
from huey.consumer import Consumer
from huey.consumer_options import ConsumerConfig, OptionParserHandler
from huey.utils import load_class
import collections

def main():
    huey_instance = load_class("lcars.settings.HUEY")

    consumer =  huey_instance.create_consumer()
    parser_handler = OptionParserHandler()
    parser = parser_handler.get_option_parser()
    options, args = parser.parse_args()
    options = {k: v for k, v in options.__dict__.items()
           if v is not None}
    defaultConf = {'workers': 10, 'worker_type': 'process'}
    config = ConsumerConfig(**collections.ChainMap(options,defaultConf))
    config.validate()

    logger = logging.getLogger('huey')
    config.setup_logger(logger)
    consumer.run()

if __name__ == '__main__':
    main()
