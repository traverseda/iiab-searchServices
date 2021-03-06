import os
import lcars.index
from lcars.settings import HUEY
from lcars.settings import settings
import logging
from huey.consumer import Consumer, Worker
from huey.consumer_options import ConsumerConfig, OptionParserHandler
from huey.utils import load_class
import collections

import logging
from rich.logging import RichHandler

workers = int(settings['lcars_tasks_workers'])

def main():
    os.nice(10)
    parser_handler = OptionParserHandler()
    parser = parser_handler.get_option_parser()
    options, args = parser.parse_args()
    options = {k: v for k, v in options.__dict__.items()
           if v is not None}
    defaultConf = {'workers': workers, 'worker_type': 'process'}
    config = ConsumerConfig(**collections.ChainMap(options,defaultConf))
    config.validate()

    huey_instance = load_class("lcars.settings.HUEY")

    logger = logging.getLogger('huey')
    config.setup_logger(logger)
    consumer =  huey_instance.create_consumer(**config.values)
    consumer.run()

if __name__ == '__main__':
    main()
