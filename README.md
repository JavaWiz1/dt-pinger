# dt-pinger

**dt-pinger** is a Python script for gathering ping statistics for one or more target hosts.
It can be imported into python project, or used as a cli.  

**dt-pinger** can be used to:
- identify devices that are up or down on the network
- identify and trouble shoot network issues (dropped packets, network congestion, ...)

**dt-pinger** 
- Only uses standard python modules
- Tested on Windows and Linux
- Provides output in multiple formats (csv, json, text)
- Is a single python file, not requiring any additional resources

Statistics captured for each host are:
- ping timestamp
- Source hostname
- Target hostname
- Packet information (sent, received, lost)
- Round Trip Time ms (minimum, maximum, average)

---
---

## Installation

To install/use **dt-pinger**, you may: 

| Use | Command |
| ------------- | --------------------------|
| github [source](https://github.com/JavaWiz1/dt-pinger) | git clone https://github.com/JavaWiz1/dt-pinger.git |
| [pip ](https://pip.pypa.io/en/stable/) | pip install dt-pinger [--user] |
| [pipx](https://pipx.pypa.io/stable/) | pipx install dt-pinger | 

---
---

## CLI Usage

```
usage: dt_pinger.py [-h] [-i FILENAME] [-o {raw,csv,json,jsonf,text}] [-c COUNT] [-w WAIT] [-v] [host ...]

Ping one or more hosts, output packet and rtt data in json, csv or text format.

positional arguments:
  host                  List of one or more hosts to ping

options:
  -h, --help            show this help message and exit
  -i FILENAME, --input FILENAME
                        Input file with hostnames 1 per line
  -o {raw,csv,json,jsonf,text}, --output {raw,csv,json,jsonf,text}
                        Output format (default text)
  -c COUNT, --count COUNT
                        number of requests to send (default 4)
  -w WAIT, --wait WAIT  milliseconds to wait before timeout (default 2000)
  -v, --verbose

Either host OR -i/--input parameter is REQUIRED.
```

### Parameters

You must supply **EITHER** host(s) or the -i/--input parameter **NOT BOTH**.

| parameter | Req/Opt | description |
| ------------ | ------- | -------------------------------------------------------|
| host | req | one or more host names seperated by space (i.e. host1 host2 host3 ...) |
| -i / --input | req | text file containing hostnames <ul><li>1 host per line<li>Any lines beginning with # will be ignored and treated as a comment line</li></ul> |
| -o / --output | opt | output type <ul><li>**text** default if omitted<li>**raw** will output results as raw dictionary</li<li>**json** will output an unformatted json string</li><li>**jsonf** will output a formatted json string</li><li>**csv** will create a csv for use in excel</li></ul> |
| -c / --count | opt | Number of echo packets to send, default 4 |
| -w / --wait  | opt | Wait time for response (ms windows, secs linux), default 2 seconds |


#### Running from python source

When running from the source code, cd to the source directory, then run by using one of the following commands...
<ul><ul>
  <li><code>python dt_pinger.py <i>host1 [[host2][host3]...]</i></code></li>
  <li><code>python dt_pinger.py -i <i>hostlist.txt</i></code></li>
</ul></ul>


#### If installed via pip or pipx

The install creates an [entrypoint](https://packaging.python.org/en/latest/specifications/entry-points/) so that
the script can be called like an executable. 
<ul><ul>
  <li><code>dt-pinger <i>host1 [[host2][host3]...]</i></code></li>
  <li><code>dt-pinger -i <i>hostlist.txt</i></code></li>
</ul></ul>

**NOTE:**   
&nbsp;&nbsp;&nbsp;&nbsp;`python dt_pinger.py host1` and `dt-pinger host1` are identical.

---
---

## Examples

### CLI
Run ping statistics against 6 hosts and output in text format to the console...
```
python dt_pinger.py pc1 pc2 pc3 pc4 pc5 google.com

----------------------------------------
dt-pinger parameters
----------------------------------------
  Source host    : my-laptop
  Target hosts   :     6
  Worker threads :     6
  Req per host   :     4
  Wait timeout   :  2000 (ms)

                                          Packets           RTT
Source          Target                Sent Recv Lost   Min  Max  Avg  Error Msg
--------------- --------------------  ---- ---- ----  ---- ---- ----  --------------------------------------
my-laptop       pc1                      4    4    0     2    6    3
my-laptop       pc2                      4    4    0     6    9    8
my-laptop       pc3                      4    4    0     4    5    4
my-laptop       pc4                      0    0    0     0    0    0  (1) offline?
my-laptop       pc5                      4    4    0     6   18   11  
my-laptop       google.com               4    4    0    29   32   31

6 hosts processed in 7.2 seconds.
```

Run ping statistics against 5 hosts and output as csv into a file...
```
python dt_pinger.py  pc1 pc2 pc3 pc4 google.com -o csv > pinger.csv

----------------------------------------
dt-pinger parameters
----------------------------------------
  Source host    : my-laptop
  Target hosts   :     5
  Worker threads :     5
  Req per host   :     4
  Wait timeout   :  2000 (ms)


5 hosts processed in 3.5 seconds.
```
output file contains:
```
timestamp,source,target,pkt_sent,pkt_recv,pkt_lost,rtt_min,rtt_max,rtt_avg,error
08/01/2024 10:31:58,my-laptop,pc1, 4,4,0,3,4,3,
08/01/2024 10:31:58,my-laptop,pc2, 4,4,0,4,5,4,
08/01/2024 10:31:58,my-laptop,pc3, 4,4,0,4,12,6,
08/01/2024 10:31:58,my-laptop,pc4, 0,0,0,0,0,0,(1) offline?
08/01/2024 10:31:58,my-laptop,google.com, 4,4,0,29,32,30,
```


### Used as an imported class

```python
from dt_pinger import Pinger

pinger = Pinger('google.com')
pinger.ping_targets()
print(pinger.results) # Output raw results object

pinger = Pinger(['google.com', 'pc1', 'msn.com'])
pinger.ping_targets()
pinger.output()  # Output formatted text
```

the program can print formated results as follows:

```python
pinger.output()         # defaults to formatted text output
pinger.output()         # raw - dictionary format
pinger.output('csv')    # csv - comma seperated
pinger.output('json')   # json string
pinger.output('jsonf')  # formatted json string
pinger.output('text')   # formatted text (default)
```

```pinger.results``` is a dictionary keyed by hostname.  For each host, packet and round trip time statistics are captured.

| Key | Value |
| --- | ----- |
| hostname | target hostname of device being pinged |
| hostname['packets'] | dictionary of packet statistics |
| hostname['packets']['sent'] | ping echo requests sent |
| hostname['packets']['received'] | request responses received |
| hostname['packets']['lost'] | requests lost/dropped |
| hostname['rtt_ms']      | dictionary of rtt statistics |
| hostname['rtt_ms']['min'] | round trip time minimum |
| hostname['rtt_ms']['max'] | round trip time maximum |
| hostname['rtt_ms']['avg'] | round trip time average |
| hostname['error'] | Error if ping was unsuccessful |

ex.
```
{'google.com': 
  {
    'packets': {'sent': 4, 'received': 4, 'lost': 0}, 
    'rtt_ms': {'min': 27, 'max': 34, 'avg': 30}, 
    'error': ''
  }
}
```

---
---
## Tips
1. Console messages are sent to stderr, output data to stdout.  You can redirect stdout, to create a file with just 
the csv (or json) as follows:
```
python dt_pinger.py pc1 pc2 pc3 -o csv > pinger.csv
```
or
```
python dt_pinger.py pc1 pc2 pc3 -o json > pinger.json
```

2. If installed via pip or pipx, an [entrypoint](https://packaging.python.org/en/latest/specifications/entry-points/) was created (i.e. dt-pinger.exe), 
   so as long as you have the proper path, you can run dt-pinger (instead of cd to proper directory and running python dt_pinger.py).<br>
   **Note:** dt_pinger.py vs. dt-pinger.exe (underscore vs. hyphen)