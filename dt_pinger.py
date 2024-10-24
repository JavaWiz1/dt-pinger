import concurrent.futures
import json
import pathlib
import socket
import subprocess
import sys
from argparse import ArgumentParser
from dataclasses import dataclass, field
from datetime import datetime as dt
from importlib.metadata import version
from time import sleep
from typing import Dict, List, Union
import threading

import dt_tools.logger.logging_helper as lh
from dt_tools.console.console_helper import ColorFG
from dt_tools.console.console_helper import ConsoleHelper as console
from dt_tools.console.spinner import Spinner, SpinnerType
from dt_tools.os.os_helper import OSHelper as os_helper
from loguru import logger as LOGGER

PACKAGE_NAME = "dt-pinger"

lock = threading.Lock()


#========================================================================================================================    
class DEFAULTS:
    MAX_THREADS: int = 50
    NUM_REQUESTS: int = 4
    REQUEST_TIMEOUT_LINUX: int = 2
    REQUEST_TIMEOUT_WINDOWS: int = 2000
    DEBUG_FORMAT = '%(asctime)s %(levelname)s %(message)s'
    CONSOLE_FORMAT = '%(message)s'


#========================================================================================================================    
@dataclass
class PingResult():
    packets: list    = field(default_factory=list) # Sent, Received, Lost
    rtt: list        = field(default_factory=list) # Min, Max, Avg
    error: str = ''

    def __post_init__(self):
        self.rtt = [0,0,0]
        self.packets = [0,0,0]
    
    def to_dict(self) -> dict:
        packet_dict = {"sent": self.packets[0], "received": self.packets[1], "lost": self.packets[2]}
        rtt_dict = {"min": self.rtt[0], "max": self.rtt[1], "avg": self.rtt[2]}
        return { "packets": packet_dict, "rtt_ms": rtt_dict, "error": self.error}

#========================================================================================================================    
class Pinger():
    '''
    Given a host (or list of hosts), ping and capture net stats for each target.
    
    ex.
        pinger = Pinger('google.com')
        pinger.ping_targets()
        print(pinger.results)
    or
        pinger = Pinger('google.com', 'myLaptop', 'msn.com')
        pinger.ping_targets()
        print(pinger.results)    
    '''
    def __init__(self, target: Union[str, List]):
        self._source_host: str = socket.gethostname()
        self._target_dict: dict = {}
        if isinstance(target, str):
            target = [ target ]
        self._target_dict = dict.fromkeys(target, PingResult())
        self._num_requests: int  = DEFAULTS.NUM_REQUESTS
        self._request_timeout: int = DEFAULTS.REQUEST_TIMEOUT_WINDOWS if os_helper.is_windows() else DEFAULTS.REQUEST_TIMEOUT_LINUX
        self._start_time: dt = None
        self._end_time: dt = None
        self._number_complete: int = 0

    # == Public Properties ==========================================================================
    @property
    def source_host(self) -> str:
        return self._source_host
        
    @property
    def elapsed_seconds(self) -> str:
        if self._start_time is None or self._end_time is None:
            return 'undetermined elasped time'
        return f'{(self._end_time - self._start_time).total_seconds():.1f} seconds'
    
    @property
    def num_requests(self) -> int:
        return self._num_requests

    @num_requests.setter
    def num_requests(self, count: int):
        if count < 1 or count > 100:
            self._num_requests = DEFAULTS.NUM_REQUESTS
        else:
            self._num_requests = count
    
    @property
    def request_timeout(self) -> int:
        return self._request_timeout
    
    @request_timeout.setter
    def request_timeout(self, value: int):
        if value < 0:
            self._request_timeout = DEFAULTS.REQUEST_TIMEOUT_WINDOWS if os_helper.is_windows() else DEFAULTS.REQUEST_TIMEOUT_LINUX
        else:
            self._request_timeout = value

    @property
    def results(self) -> Dict[str, PingResult]:
        '''Dictionary of ping results.  Key is the target hostname.'''
        return self._target_dict
    
    # == Public Functions ==========================================================================
    def increment_complete(self):
        with lock:
            self._number_complete += 1

    def to_dict(self) -> Dict:
        '''Return ping results as a dictionary'''
        result_dict = {}
        for host, entry in self._target_dict.items():
            result_dict[host] = entry.to_dict()
        return result_dict

    def ping_targets(self):
        '''Ping each target and gather statistics.'''
        total_hosts = len(self._target_dict)
        num_workers = min(DEFAULTS.MAX_THREADS, total_hosts)
        timeout_type = 'ms' if os_helper.is_windows() else 'secs'
        console.print('')
        console.print_line_seperator('Runtime parameters', 40)
        console.print(f'  Source host    : {self.source_host}')
        console.print(f'  Target hosts   : {total_hosts:5d}')
        console.print(f'  Worker threads : {num_workers:5d}')
        console.print(f'  Req per host   : {self.num_requests:5d}')
        console.print(f'  Wait timeout   : {self.request_timeout:5d} ({timeout_type})')
        console.print('')

        spinner = Spinner('Processing', SpinnerType.DOTS, show_elapsed=True)
        spinner.start_spinner()
        # console.print('Processing .', eol='', to_stderr=True)
        self._start_time = dt.now()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            executor.map(self._capture_target, self._target_dict.keys())
        spinner.stop_spinner()
        self._end_time = dt.now()
        console.print(' Done.', to_stderr=True)
        sleep(1.5)
        console.clear_line()
        console.cursor_up()
        
        LOGGER.debug(f'results: {self._target_dict}')

    def output_results(self, output_type: str = 'text'):
        if 'json' in output_type:
            self._output_json(output_type)
        elif output_type == 'raw':
            self._output_raw()
        elif output_type == 'csv':
            self._output_csv()
        elif output_type == 'text':
            # default to text
            self._output_text()
        else:
            LOGGER.error(f'ERROR: Unknown output type [{output_type}]')
            LOGGER.error('  must be one of: csv, json, jsonf or text')

    # == Private Properties ========================================================================
    @property
    def _ping_cmd(self) -> str:
        if os_helper.is_windows():
            return f'ping -n {self.num_requests} -w {self.request_timeout}'
        return f'ping -c {self.num_requests} -W {self.request_timeout}'

    # == Private Functions =========================================================================
    def _capture_target(self, target: str):
        result = self._ping_it(target)
        self._target_dict[target] = result
        
        # console.print('.', eol='', to_stderr=True)
        # eprint('.', end='', flush=True)

    def _ping_it(self, target_host: str) -> PingResult:
        LOGGER.debug('-'*80)
        cmd = f'{self._ping_cmd} {target_host}'
        LOGGER.debug(f'command: {cmd}')

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        p_stdout, p_stderr = process.communicate()
        p_rc = process.returncode
        p_stdout, p_stderr = p_stdout.decode('utf-8'), p_stderr.decode('utf-8')
        LOGGER.debug(f'[{target_host:15}] p_rc: {p_rc} len(p_stdout): {len(p_stdout)}  len(p_stderr): {len(p_stderr)}')
        ping_result = PingResult()
        if p_rc != 0:
            # Bad response, use stderr if there is output
            ping_result.error = p_stderr.strip() if len(p_stderr) > 0 else None
            if ping_result.error is None:
                ping_result.error = f'({p_rc})'
                lines = p_stdout.splitlines()                    
                if len(lines) == 1:
                    # Use stdout if there is only 1 line
                    ping_result.error += f' {lines[0]}'
                elif p_rc == 1:
                    # Likely target is offline
                    ping_result.error += ' offline?'
        else:
            # Good response, parse output
            lines = p_stdout.split("\n") 
            for line in lines:
                token = line.lstrip()
                if os_helper.is_windows():
                    if token.startswith('Minimum'):
                        rtt_line = token.strip().split(' ')
                        LOGGER.debug(f'[{target_host:15}] -- rtt ----------------------')
                        LOGGER.debug(f'[{target_host:15}] line:     {token}')
                        LOGGER.debug(f'[{target_host:15}] rtt_line: {rtt_line}')
                        ping_result.rtt = [ int(rtt_line[2][:-3]), int(rtt_line[5][:-3]), int(rtt_line[8][:-2]) ]
                        LOGGER.debug(f'[{target_host:15}] rtt_values: {ping_result.rtt}')
                    elif token.startswith('Packets:'):
                        packet_line = token.strip().split(' ')
                        LOGGER.debug(f'[{target_host:15}] -- packet -------------------')
                        LOGGER.debug(f'[{target_host:15}] line:        {token}')
                        LOGGER.debug(f'[{target_host:15}] packet_line: {packet_line}')
                        ping_result.packets = [ int(packet_line[3][:-1]), int(packet_line[6][:-1]), int(packet_line[9]) ]
                        LOGGER.debug(f'[{target_host:15}] packet_values: {ping_result.packets}')
                        pass
                else:
                    if 'rtt min' in token:
                        rtt_values = token.split(' ')[3].split('/') # Min, Avg, Max
                        LOGGER.debug(f'[{target_host:15}] -- rtt ----------------------')
                        LOGGER.debug(f'[{target_host:15}] rtt_line:   {token}')
                        LOGGER.debug(f'[{target_host:15}] rtt_values: {rtt_values}')
                        ping_result.rtt = [ int(float(rtt_values[0])), int(float(rtt_values[2])), int(float(rtt_values[1]))]
                    elif 'packets transmitted,' in token:
                        packet_line = token.split(' ')
                        LOGGER.debug(f'[{target_host:15}] -- packet -------------------')
                        LOGGER.debug(f'[{target_host:15}] packet_line:   {token}')
                        LOGGER.debug(f'[{target_host:15}] packet_values: {packet_line}')
                        ping_result.packets = [ int(packet_line[0]), int(packet_line[3]), int(packet_line[5][:-1])]

        return ping_result
    
    def _output_json(self, json_type: str ):
        LOGGER.debug('Output to JSON')
        if json_type == 'json':
            console.print(json.dumps(self.to_dict()))
        else:
            console.print(json.dumps(self.to_dict(), indent=2))

    def _output_raw(self):
        LOGGER.debug('Output to RAW Dictionary')
        console.print(self.to_dict())

    def _output_csv(self):
        LOGGER.debug('Output to CSV')
        timestamp = dt.now().strftime('%m/%d/%Y %H:%M:%S')
        print('timestamp,source,target,pkt_sent,pkt_recv,pkt_lost,rtt_min,rtt_max,rtt_avg,error')
        for target_host, r_entry in self.results.items():
            print(f'{timestamp},{self.source_host},{target_host}, ' +
                                                    f'{r_entry.packets[0]},' + 
                                                    f'{r_entry.packets[1]},' +  
                                                    f'{r_entry.packets[2]},' + 
                                                    f'{r_entry.rtt[0]},' + 
                                                    f'{r_entry.rtt[1]},' + 
                                                    f'{r_entry.rtt[2]},' + 
                                                    f'{r_entry.error}')

    def _output_text(self):
        LOGGER.debug('Output to Text')
        console.print('                                          Packets         RTT (ms)')
        console.print_line_seperator('Source          Target                Sent Recv Lost   Min  Max  Avg  Error Msg')
        # console.print('--------------- --------------------  ---- ---- ----  ---- ---- ----  --------------------------------------')
        for target_host, r_entry in self.results.items():
            console.print(f'{self.source_host:15} {target_host:20}  ' +
                          f'{r_entry.packets[0]:4d} ' +
                          f'{r_entry.packets[1]:4d} ' +
                          f'{r_entry.packets[2]:4d}  ' +
                          f'{r_entry.rtt[0]:4d} ' +
                          f'{r_entry.rtt[1]:4d} ' +
                          f'{r_entry.rtt[2]:4d}  ' +
                          f'{console.cwrap(r_entry.error, ColorFG.RED)}')


# == Module Functions ============================================================================
def abort_msg(parser: ArgumentParser, msg: str):
    parser.print_usage()
    LOGGER.error(msg)
    # console.print(console.cwrap(msg, ColorFG.RED))

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

# ===================================================================================================================
def main() -> int:
    wait_token = 'milliseconds' if os_helper.is_windows() else 'seconds'
    wait_time = DEFAULTS.REQUEST_TIMEOUT_WINDOWS if os_helper.is_windows() else DEFAULTS.REQUEST_TIMEOUT_LINUX
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

    # Setup logger
    log_level = "DEBUG" if args.verbose else "INFO"
    lh.configure_logger(log_level=log_level)

    # Validate parameters
    if len(args.host) == 0 and args.input is None:
        abort_msg(parser, 'Must supply either host(s) or --input arguments.')
        return -1

    console.print_line_seperator(' ', 80)
    console.print_line_seperator(f'{PACKAGE_NAME} v{pgm_version()}', 80)
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
    sys.exit(main())