#!/usr/bin/env python3
"""
Compares CDIS Data Client and Gen3 SDK download-multiple-async functionality
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
import html
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

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available. Install with: pip install psutil")

try:
    import sys
    import subprocess
    import os

    gen3sdk_path = os.path.expanduser(
        "~/path/to/gen3sdk-python"
    )  # TODO: Update this path
    venv_path = os.path.join(gen3sdk_path, "venv", "lib", "python3.12", "site-packages")

    modules_to_remove = [key for key in sys.modules.keys() if key.startswith("gen3")]
    for module in modules_to_remove:
        del sys.modules[module]

    if gen3sdk_path in sys.path:
        sys.path.remove(gen3sdk_path)
    if venv_path in sys.path:
        sys.path.remove(venv_path)

    sys.path.insert(0, venv_path)
    sys.path.insert(0, gen3sdk_path)

    from gen3.auth import Gen3Auth
    from gen3.file import Gen3File

    if hasattr(Gen3File, "async_download_multiple"):
        GEN3_SDK_AVAILABLE = True
        print("✅ Gen3 SDK successfully imported from local gen3sdk-python")
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
    gen3sdk_path: str = "~/path/to/gen3sdk-python"  # TODO: Update this path
    credentials_path: str = "~/path/to/credentials.json"  # TODO: Update this path
    endpoint: str = "https://data.midrc.org"
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
    """Improved file matching that handles CDIS client's nested directory structure and Gen3 SDK GUID-based files."""
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

        # Look for the best match using improved GUID-based scoring
        best_match = None
        best_score = 0

        for file_path in all_files:
            file_basename = os.path.basename(file_path)
            score = 0

            # Strategy 1: Exact GUID match (highest priority for verification)
            if guid and guid.lower() == file_basename.lower():
                score += 1000  # Very high priority for exact GUID match
                logger.debug(f"Exact GUID match found: {file_basename}")
            elif guid and guid.lower() in file_basename.lower():
                score += 800  # GUID appears in filename
                logger.debug(f"GUID in filename: {file_basename}")

            # Strategy 2: Exact filename match
            if expected_filename and expected_filename.lower() == file_basename.lower():
                score += 500
                logger.debug(f"Exact filename match: {file_basename}")
            elif (
                expected_filename and expected_filename.lower() in file_basename.lower()
            ):
                score += 300
            elif (
                expected_filename and file_basename.lower() in expected_filename.lower()
            ):
                score += 200

            # Strategy 3: GUID in path (for Gen3 SDK directory structure)
            if guid and guid.lower() in file_path.lower():
                score += 100
                logger.debug(f"GUID in path: {file_path}")

            # Strategy 4: Object ID matching (for Gen3 SDK directory structure)
            if object_id and object_id.lower() in file_path.lower():
                score += 80

            # Strategy 5: Size match (exact or close)
            try:
                file_size = os.path.getsize(file_path)
                if file_size == expected_size:
                    score += 50
                    logger.debug(f"Exact size match: {file_size} bytes")
                elif abs(file_size - expected_size) < max(
                    1024 * 1024, expected_size * 0.1
                ):
                    score += 20  # Within 1MB or 10% of expected size
                    logger.debug(
                        f"Close size match: {file_size} vs {expected_size} bytes"
                    )
            except (OSError, IOError):
                pass

            # Strategy 6: Prefer extracted files over zip files for fair comparison
            if "_extracted" in file_path and not file_path.endswith(".zip"):
                score += 10

            # Strategy 7: Handle Gen3 SDK directory structure (dg.MD1R/)
            if "dg.MD1R" in file_path and guid:
                if guid.lower() in file_path.lower():
                    score += 30

            # Strategy 8: Check for common MIDRC file patterns
            if expected_filename and any(
                ext in expected_filename.lower() for ext in [".nii.gz", ".nii", ".dcm"]
            ):
                if any(
                    ext in file_basename.lower() for ext in [".nii.gz", ".nii", ".dcm"]
                ):
                    score += 15

            if score > best_score:
                best_score = score
                best_match = file_path

        # Accept matches with score >= 50 (increased threshold for better matching)
        if best_match and best_score >= 50:
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
                    "match_type": "improved_guid_scoring",
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
        """Generate comprehensive HTML report with enhanced performance metrics and interactive charts."""

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

        try:
            with open(manifest_path, "r") as f:
                manifest_data = json.load(f)
        except Exception:
            manifest_data = []

        tool_groups = {}
        for metric in all_metrics:
            if metric.tool_name not in tool_groups:
                tool_groups[metric.tool_name] = []
            tool_groups[metric.tool_name].append(metric)

        tool_aggregates = {}
        for tool_name, tool_metrics in tool_groups.items():
            tool_aggregates[tool_name] = calculate_aggregated_metrics(tool_metrics)

        best_throughput = 0
        best_method = "None"
        for tool_name, agg_data in tool_aggregates.items():
            if agg_data.get("avg_throughput", 0) > best_throughput:
                best_throughput = agg_data.get("avg_throughput", 0)
                best_method = tool_name

        tested_methods = list(set(m.tool_name for m in all_metrics))

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced Download Performance Test Results</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f7fa;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5rem;
        }}
        .header .subtitle {{
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 1.1rem;
        }}
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8fafc;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            border-left: 4px solid #667eea;
        }}
        .card h3 {{
            margin: 0 0 10px 0;
            color: #667eea;
            font-size: 1.1rem;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            margin: 8px 0;
        }}
        .metric .label {{
            color: #666;
        }}
        .metric .value {{
            font-weight: bold;
            color: #333;
        }}
        .charts-section {{
            padding: 30px;
        }}
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            margin-bottom: 30px;
        }}
        .chart-container {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            height: 400px;
            position: relative;
        }}
        .chart-container h3 {{
            margin: 0 0 20px 0;
            color: #333;
            text-align: center;
            height: 40px;
        }}
        .chart-wrapper {{
            position: relative;
            height: 320px;
            width: 100%;
        }}
        .tables-section {{
            padding: 30px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #667eea;
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f5f7fa;
        }}
        .success-high {{ color: #10b981; font-weight: bold; }}
        .success-medium {{ color: #f59e0b; font-weight: bold; }}
        .success-low {{ color: #ef4444; font-weight: bold; }}
        .timing-section {{
            background: #f8fafc;
            padding: 30px;
            margin: 20px 0;
        }}
        .timing-breakdown {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}
        .winner-badge {{
            background: #10b981;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.9rem;
        }}
        .file-details {{
            max-height: 400px;
            overflow-y: auto;
        }}
        .mb {{ color: #666; font-size: 0.9rem; }}
        .config-note {{
            background-color: #e8f5e8;
            border-left: 4px solid #4caf50;
            padding: 15px;
            margin: 20px;
            border-radius: 4px;
        }}
        .performance-note {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px;
            border-radius: 4px;
        }}
        .profiling-section {{
            padding: 30px;
            background: #f8fafc;
        }}
        .profiling-method-card {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            margin: 20px 0;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            border-left: 4px solid #667eea;
        }}
        .profiling-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 25px;
            margin: 20px 0;
        }}
        .profiling-summary, .profiling-breakdown {{
            background: #f8fafc;
            padding: 20px;
            border-radius: 8px;
        }}
        .metric-row {{
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 8px 0;
            border-bottom: 1px solid #e2e8f0;
        }}
        .metric-row .label {{
            color: #64748b;
            font-weight: 500;
        }}
        .metric-row .value {{
            color: #1e293b;
            font-weight: 600;
        }}
        .profiling-output {{
            background: #1e293b;
            color: #e2e8f0;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            line-height: 1.4;
            max-height: 400px;
            overflow-y: auto;
        }}
        .recommendations-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .recommendation-card {{
            background: white;
            border-radius: 8px;
            padding: 15px;
            border-left: 4px solid #64748b;
            display: flex;
            align-items: flex-start;
            gap: 12px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }}
        .recommendation-card.priority-high {{
            border-left-color: #ef4444;
            background: #fef2f2;
        }}
        .recommendation-card.priority-medium {{
            border-left-color: #f59e0b;
            background: #fffbeb;
        }}
        .recommendation-card.priority-low {{
            border-left-color: #10b981;
            background: #f0fdf4;
        }}
        .rec-icon {{
            font-size: 1.5em;
            flex-shrink: 0;
        }}
        .rec-content h5 {{
            margin: 0 0 8px 0;
            color: #1e293b;
            font-size: 1em;
        }}
        .rec-content p {{
            margin: 0 0 8px 0;
            color: #64748b;
            font-size: 0.9em;
            line-height: 1.4;
        }}
        .priority-badge {{
            font-size: 0.75em;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .priority-badge.priority-high {{
            background: #ef4444;
            color: white;
        }}
        .priority-badge.priority-medium {{
            background: #f59e0b;
            color: white;
        }}
        .priority-badge.priority-low {{
            background: #10b981;
            color: white;
        }}
        .comparison-analysis {{
            padding: 30px;
            background: white;
        }}
        .comparison-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .comparison-card {{
            background: #f8fafc;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            border: 2px solid #e2e8f0;
        }}
        .comparison-card.winner {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
        }}
        .winner-method {{
            font-size: 1.2em;
            font-weight: 600;
            margin: 10px 0;
        }}
        .winner-value {{
            font-size: 1.5em;
            font-weight: 700;
        }}
        .strategy-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .strategy-card {{
            background: #f8fafc;
            border-radius: 8px;
            padding: 20px;
            border-left: 4px solid #667eea;
        }}
        .strategy-card h5 {{
            margin: 0 0 12px 0;
            color: #1e293b;
            font-size: 1.1em;
        }}
        .strategy-card p {{
            margin: 0;
            color: #64748b;
            line-height: 1.5;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Enhanced Download Performance Test Results</h1>
            <div class="subtitle">Testing Methods: {html.escape(", ".join(tested_methods))}</div>
            <div class="subtitle">Generated on {timestamp}</div>
            <div class="subtitle">Manifest: {html.escape(manifest_path)}</div>
        </div>
        
        <div class="config-note">
            <strong>⚡ Test Configuration:</strong>
            <ul>
                <li><strong>Runs per method:</strong> {self.config.num_runs}</li>
                <li><strong>Async concurrency:</strong> {self.config.max_concurrent_requests_async}</li>
                <li><strong>CDIS workers:</strong> {self.config.num_workers_cdis}</li>
                <li><strong>Real-time monitoring:</strong> {"Enabled" if self.config.enable_real_time_monitoring else "Disabled"}</li>
                <li><strong>Profiling:</strong> {"Enabled" if self.config.enable_profiling else "Disabled"}</li>
                <li><strong>Results directory:</strong> {html.escape(self.config.results_dir)}</li>
            </ul>
        </div>

        <div class="summary-cards">"""

        for tool_name in tested_methods:
            agg = tool_aggregates.get(tool_name, {})
            throughput = safe_value(agg.get("avg_throughput", 0))
            success = safe_value(agg.get("overall_success_rate", 0))

            success_class = (
                "success-high"
                if success >= 80
                else "success-medium"
                if success >= 50
                else "success-low"
            )

            html_content += f"""
            <div class="card">
                <h3>{html.escape(tool_name)}</h3>
                <div class="metric">
                    <span class="label">Avg Throughput:</span>
                    <span class="value">{throughput:.2f} MB/s</span>
                </div>
                <div class="metric">
                    <span class="label">Success Rate:</span>
                    <span class="value {success_class}">{success:.1f}%</span>
                </div>
                <div class="metric">
                    <span class="label">Runs:</span>
                    <span class="value">{agg.get("total_runs", 0)}</span>
                </div>
                <div class="metric">
                    <span class="label">Avg Time:</span>
                    <span class="value">{safe_value(agg.get("avg_download_time", 0)):.1f}s</span>
                </div>
            </div>"""

        html_content += f"""
        </div>

        <div style="text-align: center; padding: 20px; background: white; margin: 0 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);">
            <h2 style="margin: 0; color: #333;">🏆 Performance Winner</h2>
            <p><strong>Best Performing Method:</strong> <span class="winner-badge">{best_method}</span> with {best_throughput:.2f} MB/s average throughput</p>
        </div>

        <div class="charts-section">
            <h2>📈 Performance Charts</h2>
            <div class="charts-grid">
                <div class="chart-container">
                    <h3>Throughput Comparison (MB/s)</h3>
                    <div class="chart-wrapper">
                    <canvas id="throughputChart"></canvas>
                    </div>
                </div>
                <div class="chart-container">
                    <h3>Success Rate Comparison (%)</h3>
                    <div class="chart-wrapper">
                    <canvas id="successChart"></canvas>
                    </div>
                </div>
                <div class="chart-container">
                    <h3>Download Time Comparison (seconds)</h3>
                    <div class="chart-wrapper">
                    <canvas id="timeChart"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <div class="timing-section">
            <h2>⏱️ Detailed Performance Data</h2>"""

        html_content += """
        </div>
        
        <div class="profiling-section">
            <h2>🔍 Detailed Performance Profiling & Optimization Insights</h2>"""

        for metric in all_metrics:
            if metric.profiling_analysis:
                html_content += f"""
                <div class="profiling-method-card">
                    <h3>📊 {html.escape(metric.tool_name)} - Run {metric.run_number} Profiling Analysis</h3>
                    
                    <div class="profiling-grid">
                        <div class="profiling-summary">
                            <h4>⚡ Performance Summary</h4>
                            <div class="metric-row">
                                <span class="label">Total Runtime:</span>
                                <span class="value">{metric.total_download_time:.2f}s</span>
                            </div>
                            <div class="metric-row">
                                <span class="label">Throughput:</span>
                                <span class="value">{metric.average_throughput_mbps:.2f} MB/s</span>
                            </div>
                            <div class="metric-row">
                                <span class="label">Success Rate:</span>
                                <span class="value">{metric.success_rate:.1f}%</span>
                            </div>
                            <div class="metric-row">
                                <span class="label">Peak Memory:</span>
                                <span class="value">{metric.peak_memory_mb:.1f} MB</span>
                            </div>
                            <div class="metric-row">
                                <span class="label">Peak CPU:</span>
                                <span class="value">{metric.peak_cpu_percent:.1f}%</span>
                            </div>
                        </div>
                        
                        <div class="profiling-breakdown">
                            <h4>🎯 Time Breakdown</h4>
                            <div class="metric-row">
                                <span class="label">Setup Time:</span>
                                <span class="value">{metric.setup_time:.2f}s ({metric.setup_time / metric.total_download_time * 100:.1f}%)</span>
                            </div>
                            <div class="metric-row">
                                <span class="label">Download Time:</span>
                                <span class="value">{metric.download_time:.2f}s ({metric.download_time / metric.total_download_time * 100:.1f}%)</span>
                            </div>
                            <div class="metric-row">
                                <span class="label">Verification Time:</span>
                                <span class="value">{metric.verification_time:.2f}s ({metric.verification_time / metric.total_download_time * 100:.1f}%)</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="profiling-details">
                        <h4>🔧 Function-Level Performance Analysis</h4>
                        <pre class="profiling-output">{html.escape(metric.profiling_analysis)}</pre>
                    </div>
                </div>"""

        html_content += """
        </div>
        
        <div class="comparison-analysis">
            <h2>🏁 Performance Comparison & Optimization Analysis</h2>"""

        if len(tested_methods) > 1:
            best_throughput_method = max(
                tested_methods,
                key=lambda x: tool_aggregates.get(x, {}).get("avg_throughput", 0),
            )
            best_success_method = max(
                tested_methods,
                key=lambda x: tool_aggregates.get(x, {}).get("overall_success_rate", 0),
            )
            fastest_method = min(
                tested_methods,
                key=lambda x: tool_aggregates.get(x, {}).get(
                    "avg_download_time", float("inf")
                ),
            )

            html_content += f"""
            <div class="comparison-grid">
                <div class="comparison-card winner">
                    <h4>🏆 Best Throughput</h4>
                    <div class="winner-method">{html.escape(best_throughput_method)}</div>
                    <div class="winner-value">{tool_aggregates.get(best_throughput_method, {}).get("avg_throughput", 0):.2f} MB/s</div>
                </div>
                <div class="comparison-card winner">
                    <h4>🎯 Best Success Rate</h4>
                    <div class="winner-method">{html.escape(best_success_method)}</div>
                    <div class="winner-value">{tool_aggregates.get(best_success_method, {}).get("overall_success_rate", 0):.1f}%</div>
                </div>
                <div class="comparison-card winner">
                    <h4>⚡ Fastest Method</h4>
                    <div class="winner-method">{html.escape(fastest_method)}</div>
                    <div class="winner-value">{tool_aggregates.get(fastest_method, {}).get("avg_download_time", 0):.1f}s</div>
                </div>
            </div>
            
"""

        html_content += """
        </div>

        <div class="tables-section">
            <h2>📊 Aggregated Performance Summary</h2>
                    <table>
                        <thead>
                            <tr>
                        <th>Method</th>
                        <th>Runs</th>
                        <th>Overall Success</th>
                        <th>Avg Throughput</th>
                        <th>Std Dev</th>
                        <th>Min-Max Throughput</th>
                        <th>Avg Download Time</th>
                        <th>Total Files</th>
                            </tr>
                        </thead>
                        <tbody>"""

        for tool_name, agg_data in tool_aggregates.items():
            if agg_data and agg_data.get("total_runs", 0) > 0:
                success_class = (
                    "success-high"
                    if agg_data.get("overall_success_rate", 0) >= 90
                    else "success-medium"
                    if agg_data.get("overall_success_rate", 0) >= 70
                    else "success-low"
                )

                min_max_throughput = f"{safe_value(agg_data.get('min_throughput', 0)):.2f} - {safe_value(agg_data.get('max_throughput', 0)):.2f}"

                html_content += f"""
                            <tr>
                            <td><strong>{html.escape(tool_name)}</strong></td>
                            <td>{safe_value(agg_data.get("total_runs", 0))}</td>
                            <td class="{success_class}">{safe_value(agg_data.get("overall_success_rate", 0)):.1f}%</td>
                            <td>{safe_value(agg_data.get("avg_throughput", 0)):.2f} MB/s</td>
                            <td>±{safe_value(agg_data.get("std_throughput", 0)):.2f}</td>
                            <td>{min_max_throughput} MB/s</td>
                            <td>{safe_value(agg_data.get("avg_download_time", 0)):.1f}s</td>
                            <td>{safe_value(agg_data.get("total_files_successful", 0))}/{safe_value(agg_data.get("total_files_attempted", 0))}</td>
                            </tr>"""

        html_content += """
                        </tbody>
                    </table>

            <h2>📋 Detailed Performance Data</h2>
            <table>
                <thead>
                    <tr>
                        <th>Method</th>
                        <th>Run</th>
                        <th>Success Rate</th>
                        <th>Throughput (MB/s)</th>
                        <th>Download Time (s)</th>
                        <th>Files</th>
                        <th>Total Size (MB)</th>
                        <th>Peak Memory (MB)</th>
                        <th>Peak CPU (%)</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>"""

        for metric in all_metrics:
            success_class = (
                "success-high"
                if metric.success_rate >= 90
                else "success-medium"
                if metric.success_rate >= 70
                else "success-low"
            )
            status = (
                "✅ Success"
                if metric.success_rate > 80
                else "⚠️ Issues"
                if metric.success_rate > 50
                else "❌ Failed"
            )

            html_content += f"""
                    <tr>
                        <td><strong>{html.escape(metric.tool_name)}</strong></td>
                        <td>{metric.run_number}</td>
                        <td class="{success_class}">{metric.success_rate:.1f}%</td>
                        <td>{metric.average_throughput_mbps:.2f}</td>
                        <td>{metric.download_time:.1f}</td>
                        <td>{metric.successful_downloads}/{metric.total_files}</td>
                        <td>{metric.total_size_mb:.1f}</td>
                        <td>{metric.peak_memory_mb:.1f}</td>
                        <td>{metric.peak_cpu_percent:.1f}</td>
                        <td class="{success_class}">{html.escape(status)}</td>
                    </tr>"""

        html_content += """
                </tbody>
            </table>

            <h2>📁 File Details from Manifest</h2>
            <div class="file-details">
                <table>
                    <thead>
                        <tr>
                            <th>GUID</th>
                            <th>Object ID</th>
                            <th>File Name</th>
                            <th>File Size (bytes)</th>
                            <th>Size (MB)</th>
                        </tr>
                    </thead>
                    <tbody>"""

        for item in manifest_data:
            guid = (
                item.get("object_id", "").split("/")[-1]
                if item.get("object_id")
                else ""
            )
            file_size = item.get("file_size", 0)
            size_mb = item.get("size_mb", file_size / (1024 * 1024) if file_size else 0)

            safe_guid = html.escape(str(guid))
            safe_object_id = html.escape(str(item.get("object_id", "")))
            safe_file_name = html.escape(str(item.get("file_name", "N/A")))

            html_content += f"""
                        <tr>
                            <td><code>{safe_guid}</code></td>
                            <td><code>{safe_object_id}</code></td>
                            <td>{safe_file_name}</td>
                            <td>{file_size:,}</td>
                            <td class="mb">{size_mb:.2f}</td>
                        </tr>"""

        html_content += """
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        // Prepare data for charts
        const methods = ["""

        chart_labels = list(tested_methods)
        chart_throughputs = [
            safe_value(tool_aggregates.get(tool, {}).get("avg_throughput", 0))
            for tool in chart_labels
        ]
        chart_success = [
            safe_value(tool_aggregates.get(tool, {}).get("overall_success_rate", 0))
            for tool in chart_labels
        ]
        chart_times = [
            safe_value(tool_aggregates.get(tool, {}).get("avg_download_time", 0))
            for tool in chart_labels
        ]

        method_names = [f'"{method}"' for method in chart_labels]
        throughput_data = [f"{t:.2f}" for t in chart_throughputs]
        success_data = [f"{s:.1f}" for s in chart_success]
        time_data = [f"{t:.2f}" for t in chart_times]

        if not chart_labels:
            method_names = ['"No Data"']
            throughput_data = ["0"]
            success_data = ["0"]
            time_data = ["0"]

        html_content += f"""
        {", ".join(method_names)}];
        const throughputData = [{", ".join(throughput_data)}];
        const successData = [{", ".join(success_data)}];
        const timeData = [{", ".join(time_data)}];

        // Chart colors
        const colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe'];

        // Throughput Chart
        new Chart(document.getElementById('throughputChart'), {{
            type: 'bar',
            data: {{
                labels: methods,
                datasets: [{{
                    label: 'Throughput (MB/s)',
                    data: throughputData,
                    backgroundColor: colors.slice(0, methods.length),
                    borderWidth: 1,
                    borderColor: colors.slice(0, methods.length),
                    borderRadius: 4,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{
                    intersect: false,
                }},
                plugins: {{
                    legend: {{ 
                        display: false 
                    }},
                    title: {{
                        display: true,
                        text: 'Higher is Better',
                        font: {{ size: 12 }}
                    }}
                }},
                scales: {{
                    y: {{ 
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'MB/s'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Download Method'
                        }}
                    }}
                }}
            }}
        }});

        // Success Rate Chart
        new Chart(document.getElementById('successChart'), {{
            type: 'doughnut',
            data: {{
                labels: methods,
                datasets: [{{
                    data: successData,
                    backgroundColor: colors.slice(0, methods.length),
                    borderWidth: 2,
                    borderColor: '#ffffff',
                    hoverOffset: 4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{
                    intersect: false,
                }},
                plugins: {{
                    legend: {{ 
                        position: 'bottom',
                        labels: {{
                            padding: 20,
                            usePointStyle: true
                        }}
                    }},
                    title: {{
                        display: true,
                        text: 'Success Rate Percentage',
                        font: {{ size: 12 }}
                    }}
                }}
            }}
        }});

        // Time Chart
        new Chart(document.getElementById('timeChart'), {{
            type: 'line',
            data: {{
                labels: methods,
                datasets: [{{
                    label: 'Download Time (s)',
                    data: timeData,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: '#667eea',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    pointRadius: 6,
                    pointHoverRadius: 8
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{
                    intersect: false,
                }},
                plugins: {{
                    legend: {{ 
                        display: false 
                    }},
                    title: {{
                        display: true,
                        text: 'Lower is Better',
                        font: {{ size: 12 }}
                    }}
                }},
                scales: {{
                    y: {{ 
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Seconds'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Download Method'
                        }}
                    }}
                }}
            }}
        }});

        // Ensure charts render properly and handle resizing
        window.addEventListener('DOMContentLoaded', function() {{
            // Ensure chart containers maintain proper sizing
            const chartContainers = document.querySelectorAll('.chart-wrapper');
            chartContainers.forEach(container => {{
                container.style.position = 'relative';
                container.style.height = '320px';
                container.style.width = '100%';
            }});
        }});
        
        // Handle window resize for responsive charts
        window.addEventListener('resize', function() {{
            Chart.helpers.each(Chart.instances, function(instance) {{
                instance.resize();
            }});
        }});
    </script>
</body>
</html>"""

        # Save HTML report
        os.makedirs(self.config.results_dir, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_filename = f"{self.config.results_dir}/download_performance_report_{timestamp_str}.html"

        with open(html_filename, "w") as f:
            f.write(html_content)

        # Open in browser
        try:
            webbrowser.open(f"file://{os.path.abspath(html_filename)}")
            print("🌐 Report opened in browser automatically!")
        except Exception as e:
            print(f"⚠️ Could not open browser: {e}")

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
            "--profile=midrc",
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
                f"stderr='{result.stderr[:500]}...'"
                if len(result.stderr) > 500
                else f"stderr='{result.stderr}'"
            )

        if result.stdout and "Failed" in result.stdout:
            logger.warning(
                f"⚠️ {tool_name} Run {run_number} stdout indicates failures: "
                f"'{result.stdout[:500]}...'"
                if len(result.stdout) > 500
                else f"'{result.stdout}'"
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
            "midrc",
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
        """Test Gen3 SDK download-multiple-async functionality with enhanced monitoring."""
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
            "python",
            "-m",
            "gen3.cli",
            "--auth",
            os.path.abspath(self.config.credentials_path),
            "--endpoint",
            self.config.endpoint,
            "download-multiple-async",
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
            working_dir=self.config.gen3sdk_path,
            env={"PYTHONPATH": self.config.gen3sdk_path},
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
        "--endpoint", default="https://data.midrc.org", help="Gen3 endpoint URL"
    )
    parser.add_argument(
        "--credentials",
        default="~/path/to/credentials.json",
        help="Path to credentials file",
    )
    parser.add_argument(
        "--gen3-client-path",
        default="gen3-client",
        help="Path to gen3-client executable",
    )
    parser.add_argument(
        "--gen3sdk-path",
        default="~/path/to/gen3sdk-python",
        help="Path to local gen3sdk-python directory",
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
        gen3sdk_path=args.gen3sdk_path,
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
    logger.info(f"🐍 Gen3 SDK Path: {config.gen3sdk_path}")
    logger.info(f"📁 Download directory: {config.download_dir}")
    logger.info(f"📂 Results directory: {config.results_dir}")

    update_status("Initializing", "", 0.0, config.results_dir)

    all_metrics = []

    test_configs = []

    if "cdis" in config.test_methods:
        test_configs.append(
            {
                "name": "CDIS Data Client",
                "tester_class": CDISDataClientTester,
                "method": "test_download_multiple",
            }
        )

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
