#!/usr/bin/env python3
"""
Compares CDIS Data Client and Gen3 SDK download-multiple functionality
Performs REAL downloads using provided GUIDs and shows detailed performance metrics
"""

import json
import logging
import os
import subprocess
import time
import threading
import asyncio
import sys
import argparse
import shutil
import webbrowser
import math
import cProfile
import pstats
import io
import zipfile
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from statistics import mean, stdev

from contextlib import contextmanager
from jinja2 import Environment, FileSystemLoader

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available. Install with: pip install psutil")

try:
    from gen3.file import Gen3File

    if hasattr(Gen3File, "async_download_multiple"):
        GEN3_SDK_AVAILABLE = True
        print("✅ Gen3 SDK successfully imported")
        print("✅ Gen3File.async_download_multiple method available")
    else:
        GEN3_SDK_AVAILABLE = False
        print("❌ Gen3File.async_download_multiple method not found")
        available_methods = [m for m in dir(Gen3File) if not m.startswith("_")]
        print(f"Available methods: {available_methods}")

except ImportError as e:
    GEN3_SDK_AVAILABLE = False
    print(f"Warning: Gen3 SDK not available: {e}")
    print("Will skip Gen3 SDK async testing")
    print("To test a specific branch of gen3sdk, update pyproject.toml with:")
    print('gen3 = {git = "https://github.com/Dhiren-Mhatre/gen3sdk-python", branch = "feat/multiple-download-performance-testing"}')
    print("Then run: poetry lock && poetry install")
except Exception as e:
    GEN3_SDK_AVAILABLE = False
    print(f"Error importing Gen3 SDK: {e}")
    print("Will skip Gen3 SDK async testing")


class PerformanceTimer:
    def __init__(self):
        self.timings = {}

    @contextmanager
    def time_operation(self, operation_name: str):
        """Context manager to time an operation."""
        start_time = time.time()
        print(f"⏱️  Starting: {operation_name}")
        try:
            yield self
        finally:
            end_time = time.time()
            duration = end_time - start_time
            if operation_name not in self.timings:
                self.timings[operation_name] = []
            self.timings[operation_name].append(duration)
            print(f"⏱️  Completed: {operation_name} - {duration:.3f}s")

    def get_timing_summary(self) -> Dict[str, Dict[str, float]]:
        """Get summary statistics for all timed operations."""
        summary = {}
        for operation, times in self.timings.items():
            if times:
                summary[operation] = {
                    "total_time": sum(times),
                    "avg_time": mean(times),
                    "min_time": min(times),
                    "max_time": max(times),
                    "count": len(times),
                    "std_dev": stdev(times) if len(times) > 1 else 0.0,
                }
        return summary

    def print_summary(self):
        """Print timing summary to console."""
        print("\n" + "=" * 60)
        print("📊 DETAILED PERFORMANCE TIMING BREAKDOWN")
        print("=" * 60)

        summary = self.get_timing_summary()
        for operation, stats in summary.items():
            print(f"\n🔹 {operation}:")
            print(f"   Total Time: {stats['total_time']:.3f}s")
            print(f"   Average: {stats['avg_time']:.3f}s")
            print(f"   Min/Max: {stats['min_time']:.3f}s / {stats['max_time']:.3f}s")
            if stats["count"] > 1:
                print(f"   Std Dev: {stats['std_dev']:.3f}s")
            print(f"   Executions: {stats['count']}")


@dataclass
class TestConfiguration:
    num_runs: int = 2
    enable_profiling: bool = True
    enable_real_time_monitoring: bool = True
    monitoring_interval: float = 1.0
    filter_medium_files: bool = False
    force_uncompressed_cdis: bool = True
    auto_extract_cdis: bool = True
    show_detailed_timing: bool = True

    max_concurrent_requests_async: int = 100
    num_workers_cdis: int = 4

    test_methods: List[str] = field(
        default_factory=lambda: [
            "async",
            "cdis",
        ]
    )

    gen3_client_path: str = "gen3-client"
    credentials_path: str = "credentials.json"
    endpoint: str = "https://data.example.org"
    download_dir: str = "downloads"
    results_dir: str = "download_performance_results"

    AVAILABLE_METHODS = ["async", "cdis"]


@dataclass
class PerformanceMetrics:
    tool_name: str
    run_number: int
    workers: int
    total_files: int
    successful_downloads: int
    success_rate: float
    total_download_time: float
    total_size_mb: float
    average_throughput_mbps: float
    files_per_second: float
    peak_memory_mb: float = 0
    avg_memory_mb: float = 0
    peak_cpu_percent: float = 0
    avg_cpu_percent: float = 0
    setup_time: float = 0
    download_time: float = 0
    verification_time: float = 0
    return_code: int = 0
    error_count: int = 0
    error_details: List[str] = field(default_factory=list)
    file_details: List[Dict[str, Any]] = field(default_factory=list)
    profiling_stats: Optional[str] = None
    profiling_analysis: Optional[str] = None


@dataclass
class TestResult:
    method_name: str
    metrics: PerformanceMetrics
    timing_breakdown: Dict[str, Dict[str, float]] = field(default_factory=dict)


def update_status(
    status: str,
    current_tool: str = "",
    progress: float = 0.0,
    results_dir: str = "download_performance_results",
):
    """Update status file for monitoring."""
    status_file = os.path.join(results_dir, "test_status.json")
    status_data = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "current_tool": current_tool,
        "progress_percent": progress,
        "pid": os.getpid(),
    }
    try:
        os.makedirs(results_dir, exist_ok=True)
        with open(status_file, "w") as f:
            json.dump(status_data, f, indent=2)
    except Exception as e:
        logging.warning(f"Failed to update status file: {e}")


class RealTimeMonitor:
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.monitoring = False
        self.metrics = []
        self.thread = None

    def start_monitoring(self):
        """Start real-time monitoring."""
        self.monitoring = True
        self.metrics = []
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop_monitoring(self) -> Dict[str, Any]:
        """Stop monitoring and return aggregated metrics."""
        self.monitoring = False
        if self.thread:
            self.thread.join(timeout=2.0)

        if not self.metrics:
            return {}

        cpu_values = [m["cpu_percent"] for m in self.metrics]
        memory_values = [m["memory_mb"] for m in self.metrics]

        return {
            "peak_memory_mb": max(memory_values),
            "avg_memory_mb": mean(memory_values),
            "peak_cpu_percent": max(cpu_values),
            "avg_cpu_percent": mean(cpu_values),
            "sample_count": len(self.metrics),
            "duration": len(self.metrics) * self.interval,
        }

    def _monitor_loop(self):
        """Internal monitoring loop."""
        while self.monitoring:
            try:
                if PSUTIL_AVAILABLE:
                    import psutil

                    memory_info = psutil.virtual_memory()
                    cpu_percent = psutil.cpu_percent()
                else:
                    # Fallback values if psutil not available
                    memory_info = type("obj", (object,), {"used": 0})()
                    cpu_percent = 0

                self.metrics.append(
                    {
                        "timestamp": time.time(),
                        "cpu_percent": cpu_percent,
                        "memory_mb": memory_info.used / (1024 * 1024)
                        if hasattr(memory_info, "used")
                        else 0,
                        "memory_percent": getattr(memory_info, "percent", 0),
                    }
                )

                time.sleep(self.interval)
            except Exception:
                break


def analyze_profiling_stats(
    profiler: cProfile.Profile, tool_name: str, run_number: int, logger: logging.Logger
) -> str:
    """Analyze profiling statistics and return detailed breakdown."""
    if not profiler:
        return ""

    # Get stats
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)

    # Get total stats
    total_calls = ps.total_calls
    total_time = ps.total_tt

    # Get top functions by cumulative time
    ps.sort_stats("cumulative")
    ps.print_stats(15)  # Top 15 by cumulative time
    cumulative_output = s.getvalue()

    # Reset and get top functions by total time
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    ps.sort_stats("tottime")
    ps.print_stats(15)  # Top 15 by total time
    tottime_output = s.getvalue()

    # Parse the output to extract key bottlenecks with better formatting
    analysis = f"""
{tool_name} Profiling (Run {run_number})
Total Function Calls: {total_calls:,} in {total_time:.3f} seconds

Top Performance Bottlenecks (Cumulative Time):"""

    # Extract key lines from cumulative stats with improved parsing
    cumulative_lines = cumulative_output.split("\n")
    bottleneck_count = 0
    for line in cumulative_lines:
        # Look for significant bottlenecks
        if any(
            keyword in line.lower()
            for keyword in [
                "subprocess.py",
                "selectors.py",
                "time.sleep",
                "select.poll",
                "psutil",
                "communicate",
                "socket",
                "ssl",
                "urllib",
                "requests",
                "threading",
                "asyncio",
                "concurrent.futures",
            ]
        ):
            if any(char.isdigit() for char in line) and bottleneck_count < 10:
                # Clean up the line and extract timing info
                cleaned_line = " ".join(line.split())
                if "seconds" in cleaned_line or any(
                    c.isdigit() for c in cleaned_line.split()[:3]
                ):
                    analysis += f"\n  {cleaned_line}"
                    bottleneck_count += 1

    # Add top time consumers
    analysis += "\n\nTop Time Consumers (Total Time):"
    tottime_lines = tottime_output.split("\n")
    time_count = 0
    for line in tottime_lines:
        if any(char.isdigit() for char in line) and time_count < 5:
            # Look for lines with significant time consumption
            parts = line.split()
            if len(parts) >= 4:
                try:
                    time_val = float(parts[3]) if len(parts) > 3 else 0
                    if time_val > 0.1:  # Only show functions taking > 0.1s
                        cleaned_line = " ".join(line.split())
                        analysis += f"\n  {cleaned_line}"
                        time_count += 1
                except (ValueError, IndexError):
                    continue

    # Add performance insights
    analysis += "\n\nPerformance Insights:"
    if "subprocess" in cumulative_output.lower():
        analysis += "\n  • High subprocess overhead detected - consider optimizing external calls"
    if "time.sleep" in cumulative_output.lower():
        analysis += (
            "\n  • Sleep/wait operations found - potential for async optimization"
        )
    if (
        "selectors" in cumulative_output.lower()
        or "select" in cumulative_output.lower()
    ):
        analysis += (
            "\n  • I/O blocking detected - async operations could improve performance"
        )
    if "psutil" in cumulative_output.lower():
        analysis += (
            "\n  • System monitoring overhead - consider reducing monitoring frequency"
        )

    # Calculate efficiency metrics
    if total_time > 0:
        calls_per_second = total_calls / total_time
        analysis += (
            f"\n  • Function calls efficiency: {calls_per_second:,.0f} calls/second"
        )

    return analysis


def calculate_aggregated_metrics(
    metrics_list: List[PerformanceMetrics],
) -> Dict[str, Any]:
    """Calculate aggregated statistics from multiple test runs."""
    if not metrics_list:
        return {
            "total_runs": 0,
            "successful_runs": 0,
            "overall_success_rate": 0,
            "avg_throughput": 0,
            "std_throughput": 0,
            "min_throughput": 0,
            "max_throughput": 0,
            "avg_download_time": 0,
            "std_download_time": 0,
            "avg_peak_memory": 0,
            "avg_peak_cpu": 0,
            "total_files_attempted": 0,
            "total_files_successful": 0,
        }

    successful_runs = [m for m in metrics_list if m.success_rate > 0]

    if not successful_runs:
        return {
            "total_runs": len(metrics_list),
            "successful_runs": 0,
            "overall_success_rate": 0,
            "avg_throughput": 0,
            "std_throughput": 0,
            "min_throughput": 0,
            "max_throughput": 0,
            "avg_download_time": 0,
            "std_download_time": 0,
            "avg_peak_memory": 0,
            "avg_peak_cpu": 0,
            "total_files_attempted": sum(m.total_files for m in metrics_list),
            "total_files_successful": sum(m.successful_downloads for m in metrics_list),
        }

    throughputs = [
        m.average_throughput_mbps
        for m in successful_runs
        if m.average_throughput_mbps > 0
    ]
    download_times = [m.download_time for m in successful_runs if m.download_time > 0]
    success_rates = [m.success_rate for m in metrics_list]
    memory_values = [m.peak_memory_mb for m in successful_runs if m.peak_memory_mb > 0]
    cpu_values = [m.peak_cpu_percent for m in successful_runs if m.peak_cpu_percent > 0]

    return {
        "total_runs": len(metrics_list),
        "successful_runs": len(successful_runs),
        "overall_success_rate": mean(success_rates) if success_rates else 0,
        "avg_throughput": mean(throughputs) if throughputs else 0,
        "std_throughput": stdev(throughputs) if len(throughputs) > 1 else 0,
        "min_throughput": min(throughputs) if throughputs else 0,
        "max_throughput": max(throughputs) if throughputs else 0,
        "avg_download_time": mean(download_times) if download_times else 0,
        "std_download_time": stdev(download_times) if len(download_times) > 1 else 0,
        "avg_peak_memory": mean(memory_values) if memory_values else 0,
        "avg_peak_cpu": mean(cpu_values) if cpu_values else 0,
        "total_files_attempted": sum(m.total_files for m in metrics_list),
        "total_files_successful": sum(m.successful_downloads for m in metrics_list),
    }


def find_matching_files_improved(
    download_dir: str,
    manifest_data: List[Dict],
    logger: logging.Logger,
    config: TestConfiguration = None,
) -> Tuple[List[str], List[Dict]]:
    """
    File matching that handles different naming conventions between tools.

    This function is necessary because:
    1. Gen3 SDK can use GUID-based filenames when --filename-format=guid is specified
    2. CDIS client uses original filenames and nested directory structures
    3. Both tools may handle compressed files differently

    The matching strategy prioritizes exact GUID matches first, then GUID in filename,
    then exact filename matches to ensure accurate file verification across both tools.
    """
    if not os.path.exists(download_dir):
        logger.warning(f"Download directory does not exist: {download_dir}")
        return [], []

    # Get all files recursively, including in nested directories
    all_files = []

    for root, dirs, files in os.walk(download_dir):
        for file in files:
            file_path = os.path.join(root, file)
            all_files.append(file_path)

    logger.debug(f"Found {len(all_files)} total files in download directory")

    matched_files = []
    file_details = []

    for entry in manifest_data:
        object_id = entry.get("object_id", "")
        expected_filename = entry.get("file_name", "")
        expected_size = entry.get("file_size", 0)

        # Extract GUID from object_id (more robust extraction)
        if "/" in object_id:
            guid = object_id.split("/")[-1]
        else:
            guid = object_id

        logger.debug(
            f"Looking for file with GUID: {guid}, expected filename: {expected_filename}"
        )

        # Simple file matching assuming consistent naming convention
        # Priority order: exact GUID match -> GUID in filename -> expected filename
        best_match = None
        best_score = 0
        match_type = "no_match"

        for file_path in all_files:
            file_basename = os.path.basename(file_path)

            # Check for exact GUID match first (highest priority)
            if guid and guid.lower() == file_basename.lower():
                best_match = file_path
                best_score = 100
                match_type = "exact_guid_match"
                logger.debug(f"Exact GUID match found: {file_basename}")
                break

            # Check if GUID appears in filename
            if guid and guid.lower() in file_basename.lower():
                best_match = file_path
                best_score = 80
                match_type = "guid_in_filename"
                logger.debug(f"GUID in filename: {file_basename}")
                break

            # Check for expected filename match
            if expected_filename and expected_filename.lower() == file_basename.lower():
                best_match = file_path
                best_score = 60
                match_type = "exact_filename_match"
                logger.debug(f"Exact filename match: {file_basename}")
                break

        if best_match:
            matched_files.append(best_match)

            try:
                actual_size = os.path.getsize(best_match)
                size_match_percent = (
                    (min(actual_size, expected_size) / max(actual_size, expected_size))
                    * 100
                    if max(actual_size, expected_size) > 0
                    else 0
                )

                # Verify GUID presence for additional validation
                guid_verified = guid and guid.lower() in best_match.lower()

            except (OSError, IOError):
                actual_size = 0
                size_match_percent = 0
                guid_verified = False

            file_details.append(
                {
                    "object_id": object_id,
                    "guid": guid,
                    "expected_filename": expected_filename,
                    "actual_path": os.path.relpath(best_match, download_dir),
                    "expected_size": expected_size,
                    "actual_size": actual_size,
                    "size_match_percent": size_match_percent,
                    "match_score": best_score,
                    "match_type": match_type,
                    "guid_verified": guid_verified,
                }
            )

            logger.debug(
                f"✅ Matched (score={best_score}, GUID verified={guid_verified}): {expected_filename} -> {os.path.relpath(best_match, download_dir)}"
            )
        else:
            logger.warning(
                f"❌ No match found for: {expected_filename} (object_id: {object_id}, guid: {guid}) - best score: {best_score}"
            )

            # Add failed match entry for tracking
            file_details.append(
                {
                    "object_id": object_id,
                    "guid": guid,
                    "expected_filename": expected_filename,
                    "actual_path": "NOT_FOUND",
                    "expected_size": expected_size,
                    "actual_size": 0,
                    "size_match_percent": 0,
                    "match_score": best_score,
                    "match_type": "failed_match",
                    "guid_verified": False,
                }
            )

    # Summary logging
    guid_verified_count = sum(
        1 for detail in file_details if detail.get("guid_verified", False)
    )
    logger.info(
        f"✅ Successfully matched {len(matched_files)}/{len(manifest_data)} files, "
        f"GUID verified: {guid_verified_count}/{len(manifest_data)}"
    )

    return matched_files, file_details


def extract_cdis_files(
    download_dir: str, config: TestConfiguration, logger: logging.Logger
) -> int:
    """Extract CDIS zip files for fair comparison and return total extracted size."""
    if not config.auto_extract_cdis or not os.path.exists(download_dir):
        return 0

    total_extracted_size = 0
    zip_files = []

    # Find all zip files
    for root, dirs, files in os.walk(download_dir):
        for file in files:
            if file.endswith(".zip"):
                zip_files.append(os.path.join(root, file))

    logger.info(f"🗜️ Extracting {len(zip_files)} CDIS zip files for fair comparison...")

    for zip_path in zip_files:
        try:
            # Create extraction directory next to zip file
            extract_dir = zip_path.replace(".zip", "_extracted")
            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

                # Calculate extracted size
                for extracted_file in zip_ref.namelist():
                    extracted_path = os.path.join(extract_dir, extracted_file)
                    if os.path.isfile(extracted_path):
                        total_extracted_size += os.path.getsize(extracted_path)

            logger.debug(f"✅ Extracted: {os.path.basename(zip_path)}")

        except Exception as e:
            logger.warning(f"⚠️ Failed to extract {os.path.basename(zip_path)}: {e}")

    logger.info(
        f"📊 CDIS extraction complete - Total uncompressed size: {total_extracted_size / 1024 / 1024:.2f}MB"
    )
    return total_extracted_size


class PerformanceTestRunner:
    """Enhanced test runner with comprehensive HTML report generation."""

    def __init__(self, config: TestConfiguration):
        self.config = config
        os.makedirs(config.results_dir, exist_ok=True)

    def _generate_html_report(
        self, all_metrics: List[PerformanceMetrics], manifest_path: str
    ) -> str:
        """Generate comprehensive HTML report using Jinja2 template."""

        def safe_value(value, default=0, precision=2):
            """Safely format a value, handling NaN, inf, None, and missing values."""
            if value is None or (
                isinstance(value, (int, float))
                and (math.isnan(value) or math.isinf(value))
            ):
                return default
            try:
                if isinstance(value, (int, float)):
                    return round(float(value), precision)
                return value
            except (ValueError, TypeError):
                return default

        # Load and validate manifest data
        try:
            with open(manifest_path, "r") as f:
                manifest_data = json.load(f)
                if isinstance(manifest_data, dict) and "files" in manifest_data:
                    manifest_data = manifest_data["files"]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            manifest_data = []

        # Calculate aggregated data for each tool
        tool_metrics = {}
        for metric in all_metrics:
            tool_name = metric.tool_name
            if tool_name not in tool_metrics:
                tool_metrics[tool_name] = []
            tool_metrics[tool_name].append(metric)

        tool_aggregates = {}
        for tool_name, metrics_list in tool_metrics.items():
            tool_aggregates[tool_name] = calculate_aggregated_metrics(metrics_list)

        tested_methods = list(tool_aggregates.keys())
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Set up Jinja2 environment
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("performance_report.html")

        # Prepare template context
        context = {
            "timestamp": timestamp,
            "tested_methods": tested_methods,
            "tool_aggregates": tool_aggregates,
            "all_metrics": all_metrics,
            "manifest_data": manifest_data,
            "safe_value": safe_value,
        }

        # Render template
        html_content = template.render(context)

        # Save HTML report
        os.makedirs(self.config.results_dir, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_filename = f"{self.config.results_dir}/download_performance_report_{timestamp_str}.html"

        with open(html_filename, "w") as f:
            f.write(html_content)

        # Open in browser
        try:
            webbrowser.open(f"file://{os.path.abspath(html_filename)}")
        except Exception as e:
            print(f"Could not open browser: {e}")

        print(f"📊 HTML report generated: {html_filename}")
        return html_filename


# Test implementations with enhanced timing
def run_tool_with_profiling(
    cmd: List[str],
    download_dir: str,
    manifest_path: str,
    tool_name: str,
    config: TestConfiguration,
    run_number: int,
    logger: logging.Logger,
    working_dir: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> PerformanceMetrics:
    """Run a tool with detailed performance metrics and profiling."""

    monitor = (
        RealTimeMonitor(config.monitoring_interval)
        if config.enable_real_time_monitoring
        else None
    )
    profiler = cProfile.Profile() if config.enable_profiling else None

    total_start_time = time.time()

    with open(manifest_path, "r") as f:
        manifest_data = json.load(f)

    setup_start_time = time.time()

    if os.path.exists(download_dir):
        shutil.rmtree(download_dir)
    os.makedirs(download_dir, exist_ok=True)

    if "gen3-client" in cmd[0]:
        configure_cmd = [
            config.gen3_client_path,
            "configure",
            "--profile=default",
            f"--cred={config.credentials_path}",
            f"--apiendpoint={config.endpoint}",
        ]
        try:
            subprocess.run(configure_cmd, capture_output=True, text=True, timeout=30)
        except Exception as e:
            logger.warning(f"Configuration warning: {e}")

    setup_time = time.time() - setup_start_time

    logger.info(
        f"🔧 {tool_name} Run {run_number}: Starting download of {len(manifest_data)} files..."
    )

    update_status("Running tests", tool_name, 0.0, config.results_dir)

    if monitor:
        monitor.start_monitoring()

    download_start_time = time.time()

    try:
        if profiler:
            profiler.enable()

        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=working_dir, env=run_env
        )

        if profiler:
            profiler.disable()

        download_end_time = time.time()

        monitoring_stats = monitor.stop_monitoring() if monitor else {}

        if result.returncode != 0 or result.stderr:
            logger.warning(
                f"⚠️ {tool_name} Run {run_number} had issues: "
                f"return_code={result.returncode}, "
                f"stderr='{result.stderr}'"
            )

        if result.stdout and "Failed" in result.stdout:
            logger.warning(
                f"⚠️ {tool_name} Run {run_number} stdout indicates failures: "
                f"'{result.stdout}'"
            )

        verification_start_time = time.time()

        if "gen3-client" in cmd[0] and config.auto_extract_cdis:
            extract_cdis_files(download_dir, config, logger)

        matched_files, file_details = find_matching_files_improved(
            download_dir, manifest_data, logger, config=config
        )
        verification_time = time.time() - verification_start_time

        if file_details:
            total_size_mb = sum(
                d.get("actual_size_for_calc", d.get("actual_size", 0))
                for d in file_details
            ) / (1024 * 1024)
        else:
            total_size_mb = sum(
                os.path.getsize(f) for f in matched_files if os.path.exists(f)
            ) / (1024 * 1024)

        download_time = download_end_time - download_start_time
        total_time = time.time() - total_start_time
        throughput = total_size_mb / download_time if download_time > 0 else 0
        files_per_second = (
            len(matched_files) / download_time if download_time > 0 else 0
        )
        success_rate = (len(matched_files) / len(manifest_data)) * 100

        profiling_stats = None
        profiling_analysis = ""
        if profiler:
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s)
            ps.sort_stats("cumulative").print_stats(20)
            profiling_stats = s.getvalue()

            profiling_analysis = analyze_profiling_stats(
                profiler, tool_name, run_number, logger
            )
            if profiling_analysis:
                logger.info(f"📊 {profiling_analysis}")

        logger.info(
            f"📊 {tool_name} Run {run_number}: {len(matched_files)}/{len(manifest_data)} files, "
            f"{success_rate:.1f}% success, {throughput:.2f} MB/s, {download_time:.1f}s"
        )

        return PerformanceMetrics(
            tool_name=tool_name,
            run_number=run_number,
            workers=config.max_concurrent_requests_async
            if "async" in tool_name.lower()
            else config.num_workers_cdis,
            total_files=len(manifest_data),
            successful_downloads=len(matched_files),
            success_rate=success_rate,
            total_download_time=total_time,
            total_size_mb=total_size_mb,
            average_throughput_mbps=throughput,
            files_per_second=files_per_second,
            peak_memory_mb=monitoring_stats.get("peak_memory_mb", 0),
            avg_memory_mb=monitoring_stats.get("avg_memory_mb", 0),
            peak_cpu_percent=monitoring_stats.get("peak_cpu_percent", 0),
            avg_cpu_percent=monitoring_stats.get("avg_cpu_percent", 0),
            setup_time=setup_time,
            download_time=download_time,
            verification_time=verification_time,
            return_code=result.returncode,
            file_details=file_details,
            profiling_stats=profiling_stats,
            profiling_analysis=profiling_analysis,
        )

    except Exception as e:
        logger.error(f"❌ {tool_name} Run {run_number} failed: {e}")
        if monitor:
            monitor.stop_monitoring()
        return PerformanceMetrics(
            tool_name=tool_name,
            run_number=run_number,
            workers=config.max_concurrent_requests_async
            if "async" in tool_name.lower()
            else config.num_workers_cdis,
            total_files=len(manifest_data),
            successful_downloads=0,
            success_rate=0,
            total_download_time=0,
            total_size_mb=0,
            average_throughput_mbps=0,
            files_per_second=0,
            peak_memory_mb=0,
            avg_memory_mb=0,
            peak_cpu_percent=0,
            avg_cpu_percent=0,
            setup_time=setup_time,
            download_time=0,
            verification_time=0,
            return_code=-1,
            error_details=[str(e)],
        )


class CDISDataClientTester:
    """Enhanced CDIS Data Client tester with profiling and monitoring."""

    def __init__(self, config: TestConfiguration):
        self.config = config
        self.timer = PerformanceTimer()

    def test_download_multiple(
        self, manifest_path: str, run_number: int = 1
    ) -> PerformanceMetrics:
        """Test CDIS data client download-multiple functionality with enhanced monitoring."""
        download_dir = os.path.join(
            self.config.results_dir, f"cdis_run_{int(time.time())}"
        )

        cmd = [
            self.config.gen3_client_path,
            "download-multiple",
            "--manifest",
            manifest_path,
            "--numparallel",
            str(self.config.num_workers_cdis),
            "--download-path",
            download_dir,
            "--no-prompt",
            "--profile",
            "default",
        ]

        logger = logging.getLogger(__name__)
        return run_tool_with_profiling(
            cmd,
            download_dir,
            manifest_path,
            "CDIS Data Client",
            self.config,
            run_number,
            logger,
        )


class Gen3SDKTester:
    """Enhanced Gen3 SDK tester with async and sync support, profiling and monitoring."""

    def __init__(self, config: TestConfiguration):
        self.config = config
        self.timer = PerformanceTimer()

    async def test_download_multiple_async(
        self, manifest_path: str, run_number: int = 1
    ) -> PerformanceMetrics:
        """Test Gen3 SDK download-multiple functionality with enhanced monitoring."""
        if not GEN3_SDK_AVAILABLE:
            print("  ⚠️  Gen3 SDK not available - skipping async test")
            return self._create_error_metrics(
                "Gen3 SDK Async",
                self.config.max_concurrent_requests_async,
                "Gen3 SDK not available - check import errors above",
            )

        download_dir = os.path.join(
            self.config.results_dir, f"gen3sdk_async_run_{int(time.time())}"
        )

        cmd = [
            "poetry",
            "run",
            "gen3",
            "--auth",
            os.path.abspath(self.config.credentials_path),
            "--endpoint",
            self.config.endpoint,
            "download-multiple",
            "--manifest",
            os.path.abspath(manifest_path),
            "--download-path",
            os.path.abspath(download_dir),
            "--max-concurrent-requests",
            str(self.config.max_concurrent_requests_async),
            "--filename-format",
            "guid",
            "--no-prompt",
        ]

        logger = logging.getLogger(__name__)
        return run_tool_with_profiling(
            cmd,
            download_dir,
            manifest_path,
            "Gen3 SDK Async",
            self.config,
            run_number,
            logger,
        )

    def _create_error_metrics(
        self, tool_name: str, workers: int, error_msg: str
    ) -> PerformanceMetrics:
        """Create metrics for failed test."""
        return PerformanceMetrics(
            tool_name=tool_name,
            run_number=1,
            workers=workers,
            total_files=0,
            successful_downloads=0,
            success_rate=0.0,
            total_download_time=0.0,
            total_size_mb=0.0,
            average_throughput_mbps=0.0,
            files_per_second=0.0,
            error_count=1,
            error_details=[error_msg],
            file_details=[],
        )


# Enhanced main function with comprehensive performance testing
async def main():
    """Enhanced main function with comprehensive performance testing, multiple runs, and detailed analysis."""
    parser = argparse.ArgumentParser(
        description="Enhanced Download Performance Testing for Async and CDIS Methods with Profiling and Detailed Analysis"
    )
    parser.add_argument(
        "--manifest",
        default="test_data/sample_manifest.json",
        help="Path to manifest file",
    )
    parser.add_argument(
        "--num-runs", type=int, default=2, help="Number of test runs per method"
    )
    parser.add_argument(
        "--max-concurrent-async",
        type=int,
        default=100,
        help="Max concurrent requests for async",
    )

    parser.add_argument(
        "--num-workers-cdis", type=int, default=4, help="Number of CDIS workers"
    )
    parser.add_argument(
        "--test-methods",
        default="async,cdis",
        help="Comma-separated test methods (async,cdis)",
    )
    parser.add_argument(
        "--endpoint", default="https://data.example.org", help="Gen3 endpoint URL"
    )
    parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Path to credentials file",
    )
    parser.add_argument(
        "--gen3-client-path",
        default="gen3-client",
        help="Path to gen3-client executable",
    )
    parser.add_argument(
        "--download-dir",
        default="downloads",
        help="Directory to store downloaded files",
    )
    parser.add_argument(
        "--results-dir",
        default="download_performance_results",
        help="Directory to store results and reports",
    )
    parser.add_argument(
        "--disable-profiling",
        action="store_true",
        help="Disable performance profiling (enabled by default)",
    )
    parser.add_argument(
        "--disable-monitoring",
        action="store_true",
        help="Disable real-time system monitoring (enabled by default)",
    )
    parser.add_argument(
        "--disable-detailed-timing",
        action="store_true",
        help="Disable detailed timing breakdown (enabled by default)",
    )

    args = parser.parse_args()

    # Ensure results directory exists before setting up logging
    os.makedirs(f"{args.results_dir}", exist_ok=True)

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(f"{args.results_dir}/test_run.log"),
            logging.StreamHandler(),
        ],
    )
    logger = logging.getLogger(__name__)

    # Create enhanced configuration
    config = TestConfiguration(
        num_runs=args.num_runs,
        enable_profiling=not args.disable_profiling,  # Enabled by default
        enable_real_time_monitoring=not args.disable_monitoring,  # Enabled by default
        show_detailed_timing=not args.disable_detailed_timing,  # Enabled by default
        max_concurrent_requests_async=args.max_concurrent_async,
        num_workers_cdis=args.num_workers_cdis,
        test_methods=[method.strip() for method in args.test_methods.split(",")],
        endpoint=args.endpoint,
        credentials_path=args.credentials,
        gen3_client_path=args.gen3_client_path,
        download_dir=args.download_dir,
        results_dir=args.results_dir,
    )

    logger.info(
        "🚀 Enhanced Download Performance Testing - Async & CDIS Focus with Profiling Enabled"
    )
    logger.info("=" * 70)
    logger.info(f"📝 Manifest: {args.manifest}")
    logger.info(f"🔍 Test methods: {config.test_methods}")
    logger.info(f"🔁 Number of runs per method: {config.num_runs}")
    logger.info(f"⚡ Async concurrency: {config.max_concurrent_requests_async}")
    logger.info(f"⚡ CDIS workers: {config.num_workers_cdis}")
    logger.info(f"📊 Profiling: {'Enabled' if config.enable_profiling else 'Disabled'}")
    logger.info(
        f"📊 Monitoring: {'Enabled' if config.enable_real_time_monitoring else 'Disabled'}"
    )
    logger.info(
        f"⏱️ Detailed timing: {'Enabled' if config.show_detailed_timing else 'Disabled'}"
    )
    logger.info(f"🌐 Endpoint: {config.endpoint}")
    logger.info(f"🔑 Credentials: {config.credentials_path}")
    logger.info(f"🛠️ Gen3 Client: {config.gen3_client_path}")
    logger.info(f"📁 Download directory: {config.download_dir}")
    logger.info(f"📂 Results directory: {config.results_dir}")

    update_status("Initializing", "", 0.0, config.results_dir)

    all_metrics = []

    test_configs = []

    # Test async first for faster failure detection when testing branches
    if "async" in config.test_methods and GEN3_SDK_AVAILABLE:
        test_configs.append(
            {
                "name": "Gen3 SDK Async",
                "tester_class": Gen3SDKTester,
                "method": "test_download_multiple_async",
            }
        )
    elif "async" in config.test_methods:
        logger.warning("⚠️  Skipping Gen3 SDK Async test - not available")

    if "cdis" in config.test_methods:
        test_configs.append(
            {
                "name": "CDIS Data Client",
                "tester_class": CDISDataClientTester,
                "method": "test_download_multiple",
            }
        )

    total_tests = len(test_configs) * config.num_runs
    current_test = 0

    for test_config in test_configs:
        logger.info(
            f"\n🔧 Testing {test_config['name']} with {config.num_runs} runs..."
        )

        tester = test_config["tester_class"](config)
        method = getattr(tester, test_config["method"])

        for run in range(1, config.num_runs + 1):
            current_test += 1
            progress = (current_test / total_tests) * 100

            logger.info(
                f"  🏃 Run {run}/{config.num_runs} for {test_config['name']}..."
            )
            update_status(
                "Running tests", test_config["name"], progress, config.results_dir
            )

            if "async" in test_config["method"]:
                metrics = await method(args.manifest, run_number=run)
            else:
                metrics = method(args.manifest, run_number=run)

            all_metrics.append(metrics)

            logger.info(
                f"    ✅ Run {run} completed: {metrics.success_rate:.1f}% success, "
                f"{metrics.average_throughput_mbps:.2f} MB/s, {metrics.download_time:.1f}s"
            )

    update_status("Generating report", "", 95.0, config.results_dir)
    logger.info("\n📊 Generating enhanced performance comparison report...")

    runner = PerformanceTestRunner(config)
    html_filename = runner._generate_html_report(all_metrics, args.manifest)

    logger.info("\n" + "=" * 70)
    logger.info("📊 ENHANCED PERFORMANCE RESULTS SUMMARY")
    logger.info("=" * 70)

    tested_methods = list(set(m.tool_name for m in all_metrics))
    for tool_name in tested_methods:
        tool_metrics = [m for m in all_metrics if m.tool_name == tool_name]
        if tool_metrics:
            agg = calculate_aggregated_metrics(tool_metrics)
            logger.info(f"\n🔹 {tool_name}:")
            logger.info(
                f"   Runs: {agg.get('total_runs', 0)} (successful: {agg.get('successful_runs', 0)})"
            )
            logger.info(
                f"   Avg Success Rate: {agg.get('overall_success_rate', 0):.1f}%"
            )
            logger.info(
                f"   Avg Throughput: {agg.get('avg_throughput', 0):.2f} ± {agg.get('std_throughput', 0):.2f} MB/s"
            )
            logger.info(
                f"   Throughput Range: {agg.get('min_throughput', 0):.2f} - {agg.get('max_throughput', 0):.2f} MB/s"
            )
            logger.info(
                f"   Avg Download Time: {agg.get('avg_download_time', 0):.1f} ± {agg.get('std_download_time', 0):.1f}s"
            )
            logger.info(
                f"   Total Files: {agg.get('total_files_successful', 0)}/{agg.get('total_files_attempted', 0)}"
            )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"{config.results_dir}/enhanced_results_{timestamp}.json"

    results_data = {
        "timestamp": timestamp,
        "config": {
            "num_runs": config.num_runs,
            "test_methods": config.test_methods,
            "max_concurrent_requests_async": config.max_concurrent_requests_async,
            "num_workers_cdis": config.num_workers_cdis,
            "enable_profiling": config.enable_profiling,
            "enable_real_time_monitoring": config.enable_real_time_monitoring,
        },
        "test_focus": "Enhanced async and CDIS performance testing with profiling and detailed analysis",
        "metrics": [
            {
                "tool_name": m.tool_name,
                "run_number": m.run_number,
                "success_rate": m.success_rate,
                "throughput": m.average_throughput_mbps,
                "download_time": m.download_time,
                "files_downloaded": m.successful_downloads,
                "total_files": m.total_files,
                "total_size_mb": m.total_size_mb,
                "peak_memory_mb": m.peak_memory_mb,
                "peak_cpu_percent": m.peak_cpu_percent,
                "return_code": m.return_code,
                "error_details": m.error_details,
            }
            for m in all_metrics
        ],
    }

    with open(results_file, "w") as f:
        json.dump(results_data, f, indent=2)

    update_status("Completed", "", 100.0, config.results_dir)

    logger.info(f"\n💾 Detailed results saved to: {results_file}")
    logger.info(f"📊 HTML report generated: {html_filename}")
    logger.info(f"📁 Downloaded files are in: {config.download_dir}/")
    logger.info("🎉 Enhanced performance testing completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        logging.exception("Test execution failed")
        sys.exit(1)
