# Download Performance Testing Script

A comprehensive Python script that compares CDIS Data Client and Gen3 SDK download-multiple-async functionality with profiling and monitoring capabilities.

## Features

- **Performance Testing**: Comprehensive Gen3 Python SDK/CLI and Golang Client performance comparison
- **Profiling**: Built-in cProfile integration with detailed bottleneck analysis
- **Real-time Monitoring**: CPU, memory, and resource usage tracking during downloads
- **HTML Reports**: Interactive HTML reports with charts and detailed metrics
- **Multiple Test Runs**: Configurable number of runs per method for statistical analysis
- **Detailed Timing**: Breakdown of setup, download, and verification phases
- **File Matching**: Intelligent file matching with GUID verification

## Requirements

- Python 3.9+
- Poetry for dependency management
- Gen3 SDK installed via pyproject.toml (see Configuration section)
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

### Testing a Specific Gen3 SDK Branch

To test a specific branch of the Gen3 SDK (e.g., a development branch with new features), update your `pyproject.toml` file to install from the desired branch:

```toml
[tool.poetry.dependencies]
gen3 = {git = "https://github.com/Dhiren-Mhatre/gen3sdk-python", branch = "feat/multiple-download-performance-testing"}
```

Then update your dependencies:

```bash
poetry lock
poetry install
```

### Other Configuration

Before running the tests, configure the following:

1. **Credentials**: Specify credentials file with `--credentials path/to/credentials.json`
2. **Gen3 Client**: Ensure `gen3-client` is in your PATH or specify with `--gen3-client-path`

## Usage

### Basic Usage

```bash
poetry run python download_performance_test.py \
  --manifest ../test_data/sample_manifest.json \
  --num-runs 3 \
  --max-concurrent-async 32 \
  --num-workers-cdis 4 \
  --test-methods "async,cdis" \
  --endpoint "https://data.midrc.org" \
  --credentials "~/.gen3/MIDRC_prod.json" \
  --gen3-client-path "gen3-client" \
  --download-dir "downloads" \
  --results-dir "download_performance_results"
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
  --credentials "credentials.json" \
  --gen3-client-path "gen3-client" \
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
| `--credentials`             | `credentials.json`               | Path to credentials file            |
| `--gen3-client-path`        | `gen3-client`                    | Path to gen3-client executable      |
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
