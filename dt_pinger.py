import concurrent.futures
import json
import logging
import pathlib
import platform
import socket
import subprocess
import sys
from argparse import ArgumentParser
from dataclasses import dataclass, field
from datetime import datetime as dt
from time import sleep
from typing import Dict, List, Union

LOGGER = logging.getLogger('pinger')

#========================================================================================================================    
class DEFAULTS:
    MAX_THREADS: int = 50
    NUM_REQUESTS: int = 4
    REQUEST_TIMEOUT_LINUX: int = 2
    REQUEST_TIMEOUT_WINDOWS: int = 2000
    DEBUG_FORMAT = '%(asctime)s %(levelname)s %(message)s'
    CONSOLE_FORMAT = '%(message)s'

ESC='\u001b'    
CURSOR_CLEAR_LINE = f'{ESC}[2K'
CURSOR_UP         = f'{ESC}[1A'

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
        self._request_timeout: int = DEFAULTS.REQUEST_TIMEOUT_WINDOWS if is_windows() else DEFAULTS.REQUEST_TIMEOUT_LINUX
        self._start_time: dt = None
        self._end_time: dt = None

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
            self._request_timeout = DEFAULTS.REQUEST_TIMEOUT_WINDOWS if is_windows() else DEFAULTS.REQUEST_TIMEOUT_LINUX
        else:
            self._request_timeout = value

    @property
    def results(self) -> Dict[str, PingResult]:
        '''Dictionary of ping results.  Key is the target hostname.'''
        return self._target_dict
    
    # == Public Functions ==========================================================================
    def to_dict(self) -> Dict:
        '''Return ping results as a dictionary'''
        result_dict = {}
        for host, entry in self._target_dict.items():
            result_dict[host] = entry.to_dict()
        return result_dict

    def ping_targets(self):
        '''Ping each target and gather statistics.'''
        num_workers = min(DEFAULTS.MAX_THREADS, len(self._target_dict))
        timeout_type = 'ms' if is_windows() else 'secs'
        LOGGER.info('')
        LOGGER.info('-'*40)
        LOGGER.info('dt-pinger parameters')
        LOGGER.info('-'*40)
        LOGGER.info(f'  Source host    : {self.source_host}')
        LOGGER.info(f'  Target hosts   : {len(self._target_dict):5d}')
        LOGGER.info(f'  Worker threads : {num_workers:5d}')
        LOGGER.info(f'  Req per host   : {self.num_requests:5d}')
        LOGGER.info(f'  Wait timeout   : {self.request_timeout:5d} ({timeout_type})')
        LOGGER.info('')

        eprint('Processing .', end='', flush=True)
        self._start_time = dt.now()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            executor.map(self._capture_target, self._target_dict.keys())
        self._end_time = dt.now()
        eprint(' Done.', end='', flush=True)
        sleep(1.5)
        eprint(CURSOR_CLEAR_LINE)
        eprint(CURSOR_UP, end='', flush=True)
        
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
        if is_windows():
            return f'ping -n {self.num_requests} -w {self.request_timeout}'
        return f'ping -c {self.num_requests} -W {self.request_timeout}'

    # == Private Functions =========================================================================
    def _capture_target(self, target: str):
        result = self._ping_it(target)
        self._target_dict[target] = result
        eprint('.', end='', flush=True)

    def _ping_it(self, target_host: str) -> PingResult:
        cmd = f'{self._ping_cmd} {target_host}'
        ping_result = PingResult()

        LOGGER.debug('-'*80)
        LOGGER.debug(f'command: {cmd}')
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        p_stdout, p_stderr = process.communicate()
        p_rc = process.returncode
        p_stdout, p_stderr = p_stdout.decode('utf-8'), p_stderr.decode('utf-8')
        LOGGER.debug(f'[{target_host:15}] p_rc: {p_rc} len(p_stdout): {len(p_stdout)}  len(p_stderr): {len(p_stderr)}')
        if p_rc != 0:
            ping_result.error = p_stderr.strip() if len(p_stderr) > 0 else None
            if ping_result.error is None:
                ping_result.error = f'({p_rc})'
                if p_rc == 1:
                    ping_result.error += ' offline?'
        else: 
            lines = p_stdout.split("\n") 
            for line in lines:
                token = line.lstrip()
                if is_windows():
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
        if json_type == 'json':
            print(json.dumps(self.to_dict()))
        else:
            print(json.dumps(self.to_dict(), indent=2))

    def _output_raw(self):
        print(self.to_dict())

    def _output_csv(self):
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
        print('                                          Packets         RTT (ms)')
        print('Source          Target                Sent Recv Lost   Min  Max  Avg  Error Msg')
        print('--------------- --------------------  ---- ---- ----  ---- ---- ----  --------------------------------------')
        for target_host, r_entry in self.results.items():
            print(f'{self.source_host:15} {target_host:20}  ' +
                    f'{r_entry.packets[0]:4d} ' +
                    f'{r_entry.packets[1]:4d} ' +
                    f'{r_entry.packets[2]:4d}  ' +
                    f'{r_entry.rtt[0]:4d} ' +
                    f'{r_entry.rtt[1]:4d} ' +
                    f'{r_entry.rtt[2]:4d}  ' +
                    f'{r_entry.error}')




# == Module Functions ============================================================================
def setup_logger(log_level: int = logging.INFO):
    format = DEFAULTS.CONSOLE_FORMAT if log_level == logging.INFO else DEFAULTS.DEBUG_FORMAT
    logging.basicConfig(format=format, level=log_level)

def is_windows() -> bool:
    return (platform.system() == "Windows")

def eprint(*args, **kwargs):
    if LOGGER.getEffectiveLevel() != logging.DEBUG:
        # Only print if not in verbose (debug) mode
        print(*args, file=sys.stderr, **kwargs)

def abort_msg(parser: ArgumentParser, msg: str):
    parser.print_usage()
    print(msg)

# ===================================================================================================================
def main() -> int:
    wait_token = 'milliseconds' if is_windows() else 'seconds'
    wait_time = DEFAULTS.REQUEST_TIMEOUT_WINDOWS if is_windows() else DEFAULTS.REQUEST_TIMEOUT_LINUX
    description  = 'Ping one or more hosts, output packet and rtt data in json, csv or text format.'
    epilog = 'Either host OR -i/--input parameter is REQUIRED.'
    parser = ArgumentParser(description=description, epilog=epilog)
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
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logger(log_level)

    # Validate parameters
    if len(args.host) == 0 and args.input is None:
        abort_msg(parser, 'Must supply either host(s) or --input arguments.')
        return -1
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
    # # Output
    # if 'json' in args.output:
    #     output_json(pinger, args.output)
    # elif args.output == 'csv':
    #     output_csv(pinger)
    # else:
    #     # default to text
    #     output_text(pinger)

    LOGGER.info('')
    LOGGER.info(f'{len(pinger.results)} hosts processed in {pinger.elapsed_seconds}.')
    return 0

if __name__ == "__main__":
    sys.exit(main())