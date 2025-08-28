# Download Performance Testing Script

A comprehensive Python script that compares CDIS Data Client and Gen3 SDK download-multiple-async functionality with profiling and monitoring capabilities.

## Features

- **Performance Testing**: Comprehensive async and CDIS performance comparison
- **Profiling**: Built-in cProfile integration with detailed bottleneck analysis
- **Real-time Monitoring**: CPU, memory, and resource usage tracking during downloads
- **HTML Reports**: Interactive HTML reports with charts and detailed metrics
- **Multiple Test Runs**: Configurable number of runs per method for statistical analysis
- **Detailed Timing**: Breakdown of setup, download, and verification phases
- **File Matching**: Intelligent file matching with GUID verification

## Requirements

- Python 3.9+
- Poetry for dependency management
- Local `gen3sdk-python` directory for Gen3 SDK testing
- `gen3-client` executable for CDIS testing

## Installation

1. Install Poetry (if not already installed):

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Install dependencies using Poetry:

```bash
poetry install
```

3. Activate the virtual environment:

```bash
poetry shell
```

## Configuration

Before running the tests, update the following paths in the script or use command line arguments:

1. **Gen3 SDK Path**: Update `gen3sdk_path` in the script or use `--gen3sdk-path ~/path/to/gen3sdk-python`
2. **Credentials**: Update `credentials_path` or use `--credentials ~/path/to/credentials.json`
3. **Gen3 Client**: Ensure `gen3-client` is in your PATH or specify with `--gen3-client-path`

## Usage

### Basic Usage

```bash
python download_performance_test.py --manifest test_data/sample_manifest.json
```

### Command Line Options

```bash
python download_performance_test.py \
  --manifest manifest.json \
  --num-runs 2 \
  --max-concurrent-async 100 \
  --num-workers-cdis 4 \
  --test-methods "async,cdis" \
  --endpoint "https://data.midrc.org" \
  --credentials "~/path/to/credentials.json" \
  --gen3-client-path "gen3-client" \
  --gen3sdk-path "~/path/to/gen3sdk-python" \
  --download-dir "downloads" \
  --results-dir "download_performance_results" \
  --disable-profiling \
  --disable-monitoring \
  --disable-detailed-timing
```

### Available Arguments

| Argument                    | Default                          | Description                         |
| --------------------------- | -------------------------------- | ----------------------------------- |
| `--manifest`                | `test_data/sample_manifest.json` | Path to manifest JSON file          |
| `--num-runs`                | `2`                              | Number of test runs per method      |
| `--max-concurrent-async`    | `100` (configurable)             | Max concurrent requests for async   |
| `--num-workers-cdis`        | `4` (configurable)               | Number of CDIS workers              |
| `--test-methods`            | `"async,cdis"`                   | Comma-separated test methods        |
| `--endpoint`                | `https://data.midrc.org`         | Gen3 endpoint URL                   |
| `--credentials`             | `~/path/to/credentials.json`     | Path to credentials file            |
| `--gen3-client-path`        | `gen3-client`                    | Path to gen3-client executable      |
| `--gen3sdk-path`            | `~/path/to/gen3sdk-python`       | Path to local gen3sdk-python        |
| `--download-dir`            | `downloads`                      | Directory to store downloaded files |
| `--results-dir`             | `download_performance_results`   | Directory to store results          |
| `--disable-profiling`       | `False`                          | Disable performance profiling       |
| `--disable-monitoring`      | `False`                          | Disable real-time monitoring        |
| `--disable-detailed-timing` | `False`                          | Disable detailed timing breakdown   |

### Test Methods

- **`cdis`**: Tests CDIS Data Client with worker-based concurrency
- **`async`**: Tests Gen3 SDK with async/await and semaphore control

## Output

Results are saved to `download_performance_results/`:

- **HTML Report**: Interactive report with charts (`download_performance_report_YYYYMMDD_HHMMSS.html`)
- **JSON Results**: Detailed metrics (`enhanced_results_YYYYMMDD_HHMMSS.json`)
- **Log Files**: Comprehensive test logs (`test_run.log`)
- **Downloaded Files**: Test files in method-specific directories

## Example Usage

```bash
# Test both methods with 2 runs each (default)
python download_performance_test.py \
  --manifest test_data/sample_manifest.json

# Test only async method with high concurrency
python download_performance_test.py \
  --manifest manifest.json \
  --test-methods "async" \
  --max-concurrent-async 500

# Quick test with profiling disabled
python download_performance_test.py \
  --manifest manifest.json \
  --num-runs 1 \
  --disable-profiling \
  --disable-monitoring
```

## What Gets Tested

- **Download Success Rates**: File-by-file success tracking with GUID verification
- **Performance Metrics**: Throughput (MB/s), timing breakdown, concurrency efficiency
- **Resource Usage**: Real-time memory, CPU, and I/O monitoring
- **Profiling Analysis**: Function-level performance bottlenecks and optimization insights
- **Scalability**: Performance under different concurrency levels
- **Error Handling**: Comprehensive error tracking and failure analysis

## Performance Insights

The script provides detailed performance analysis including:

- Top performance bottlenecks by cumulative time
- Function call efficiency metrics
- I/O and network operation analysis
- Memory and CPU usage patterns
- Optimization recommendations
