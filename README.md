# py-pinger

**py-pinger** is a Python script for gathering ping statistics for one or more target hosts.  

py-pinger can be used to:
- identify devices that are up or down on the network
- trouble shoot network issues (dropped packets, network congestion, ...)

**py-pinger** 
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

## Installation

To install/use py-pinger, you may: 

| Use | Command |
| ------------- | --------------------------|
| github [source](https://github.com/JavaWiz1/py-pinger) | git clone https://github.com/javawiz1/py-pinger.git |
| [pip ](https://pip.pypa.io/en/stable/) | pip install py-pinger [--user] |
| [pipx](https://pipx.pypa.io/stable/) | pipx install py-pinger | 

## Usage
```
usage: py-pinger.py [-h] [-i FILENAME] [-o {csv,json,jsonf,text}] [-c COUNT] [-w WAIT] [-v] [host ...]

positional arguments:
  host                  List of one or more hosts to ping

options:
  -h, --help            show this help message and exit
  -i FILENAME, --input FILENAME
                        Input file with hostnames 1 per line
  -o {csv,json,jsonf,text}, --output {csv,json,jsonf,text}
                        Output format (default text)
  -c COUNT, --count COUNT
                        number of requests to send (default 4)
  -w WAIT, --wait WAIT  milliseconds to wait before timeout (default 2000)
  -v, --verbose
```

#### Parameters
- You must supply **either** hostname(s) or the -i/--input parameter **not both**.

| parameter | Req/Opt | description |
| ------------ | ------- | -------------------------------------------------------|
| host | req | one or more host names seperated by space (i.e. host1 host2 host3 ...) |
| -i / --input | req | text file containing hostnames <ul><li>1 host per line<li>Any lines beginning with # will be ignored and treated as a comment line</li></ul> |
| -o / --output | opt | output type <ul><li>**text** default if omitted<li>**json** will output an unformatted json string</li><li>**jsonf** will output a formatted json string</li><li>**csv** will create a csv for use in excel</li></ul> |
| -c / --count | opt | Number of echo packets to send, default 4 |
| -w / --wait  | opt | Wait time for response (ms windows, secs linux), default 2 seconds |

### Running from python source

When running from the source code
- cd to the source directory
- run the following command
``` python py-pinger.py host1 ```


### If installed via pip or pipx

The install creates an [entrypoint](https://packaging.python.org/en/latest/specifications/entry-points/) so that
the script can be called like an executable. 

``` py-pinger host1 ```

**Note:**
   
&nbsp;&nbsp;&nbsp;&nbsp;```python py-pinger.py host1``` and ```py-pinger host1``` are identical.

## Example
```bash
python py-pinger.py pc1 pc2 pc3 pc4 pc5
Parameters -
     5 Target hosts
     4 Requests per host
  2000 Response timeout (ms)

  Processing ......

                                          Packets           RTT
Source          Target                Sent Recv Lost   Min  Max  Avg  Error Msg
--------------- --------------------  ---- ---- ----  ---- ---- ----  --------------------------------------
my-laptop       pc1                      4    4    0     2    6    3
my-laptop       pc2                      4    4    0     6    9    8
my-laptop       pc3                      4    4    0     4    5    4
my-laptop       pc4                      0    0    0     0    0    0  (1) offline?
my-laptop       pc5                      4    4    0     6   18   11  

5 hosts output in 7.2 seconds.
```

## Tips
1. Console messages are sent to stderr, output data to stdout.  You can redirect stdout, to create a file with just 
the csv as follows:
```
python py-pinger.py pc1 pc2 pc3 -o csv > pinger.csv
```

2. If installed via pip or pipx, an entrypoint was created, so as long as you have the proper path, 
   you can run py-pinger (instead of cd to proper directory and running python py-pinger.py)