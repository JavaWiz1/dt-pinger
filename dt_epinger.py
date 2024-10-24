import pathlib
from argparse import ArgumentParser
from datetime import datetime as dt
from importlib.metadata import version

import dt_tools.logger.logging_helper as lh
from dt_tools.console.console_helper import ConsoleHelper as console
from dt_tools.os.os_helper import OSHelper
from loguru import logger as LOGGER

from dt_pinger import Pinger

PACKAGE_NAME = "dt-pinger"

class DEFAULTS:
    MAX_THREADS: int = 50
    NUM_REQUESTS: int = 4
    REQUEST_TIMEOUT_LINUX: int = 2
    REQUEST_TIMEOUT_WINDOWS: int = 2000
    DEBUG_FORMAT = '%(asctime)s %(levelname)s %(message)s'
    CONSOLE_FORMAT = '%(message)s'

class ePinger(Pinger):
    pass


def pgm_version() -> str:
    '''Retrieve project version from distribution metadata, toml or most recently update python code file'''
    ver = None
    try:
        # __version__ = pkg_resources.get_distribution(PACKAGE_NAME).version
        ver = version(PACKAGE_NAME)
    except:  # noqa: E722
        pass
    if ver is None:
        file_list = list(pathlib.Path(__file__).parent.glob("**/pyproject.toml"))
        if len(file_list) == 1:
            # Retrieve version from .toml file
            buff = file_list[0].read_text(encoding='utf-8').splitlines()
            ver_line = [x for x in buff if x.startswith('version')]
            if len(ver_line) == 1:
                ver = ver_line[0].split('=')[1].replace('"','').replace("'",'').strip()
        if ver is None:
            # version based on the mod timestamp of the most current updated python code file
            file_list = list(pathlib.Path(__file__).parent.glob("**/*.py"))
            ver_date = dt(2000,1,1,0,0,0,0)
            for file_nm in file_list:
                ver_date = max(ver_date, dt.fromtimestamp(file_nm.stat().st_mtime))
            ver = f'{ver_date.year}.{ver_date.month}.{ver_date.day}'    
    return ver

def abort_msg(parser: ArgumentParser, msg: str):
    parser.print_usage()
    console.print(msg)


def main() -> int:
    wait_token = 'milliseconds' if OSHelper.is_windows() else 'seconds'
    wait_time = DEFAULTS.REQUEST_TIMEOUT_WINDOWS if OSHelper.is_windows() else DEFAULTS.REQUEST_TIMEOUT_LINUX
    description  = 'Ping one or more hosts, output packet and rtt data in json, csv or text format.'
    epilog = 'Either host OR -i/--input parameter is REQUIRED.'
    parser = ArgumentParser(prog=PACKAGE_NAME, description=description, epilog=epilog)
    parser.add_argument('-i', '--input', type=str, help='Input file with hostnames 1 per line',
                                        metavar='FILENAME')
    parser.add_argument('-o', '--output', choices=['raw', 'csv', 'json', 'jsonf', 'text'], default='text',
                                        help='Output format (default text)')
    parser.add_argument('-c', '--count', type=int, default=DEFAULTS.NUM_REQUESTS, 
                                        help=f'number of requests to send (default {DEFAULTS.NUM_REQUESTS})')
    parser.add_argument('-w', '--wait', type=int, default=wait_time, 
                                        help=f'{wait_token} to wait before timeout (default {wait_time})')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Enable debug logging')
    parser.add_argument('host', nargs='*', help='List of one or more hosts to ping')
    args = parser.parse_args()

    if args.verbose:
        log_level = "DEBUG"
    else:
        log_level = "INFO"
    lh.configure_logger(log_level=log_level)
    
    # Validate parameters
    if len(args.host) == 0 and args.input is None:
        abort_msg(parser, 'Must supply either host(s) or --input arguments.')
        return -1

    LOGGER.info('='*80)
    LOGGER.info(f'{PACKAGE_NAME} v{pgm_version()}')
    LOGGER.info('='*80)
    if len(args.host) > 0:
        host_list = args.host
    else:
        host_file = pathlib.Path(args.input)
        if not host_file.exists():
            abort_msg(parser, f'{args.input} file does NOT exist.')
            return -2
        hosts = host_file.read_text(encoding='UTF-8').splitlines()
        host_list = [ x.strip() for x in hosts if len(x.strip()) > 0 and not x.strip().startswith('#') ]
        LOGGER.debug(f'Loaded {len(host_list)} hosts from: {args.input}')

    # Setup and ping
    pinger = Pinger(host_list)
    pinger.num_requests = args.count
    pinger.request_timeout = args.wait
    pinger.ping_targets()
    pinger.output_results(args.output)

    LOGGER.info('')
    LOGGER.info(f'{len(pinger.results)} hosts processed in {pinger.elapsed_seconds}.')
    return 0


if __name__ == "__main__":
    main()
